"""Clientes que entran en Nesto por un origen con embudo propio (issue #43).

El importador de leads de Meta de Nesto (NestoAPI#623) da de alta un cliente por lead,
con el origen META-HARMONIA-0926 y el consentimiento de comunicaciones. Aquí:

1. Esos clientes y los que no aceptan comunicaciones quedan fuera del «Embudo de
   conversión» (el general), cuyo dominio vive en la base de datos.
2. Por cada cliente de Meta se crea una oportunidad con la campaña de Odoo del mismo
   código, para su comercial. Pasa a Ganado con el primer pedido, como cualquier lead
   enlazado con un cliente de Nesto (_nv_avanzar_por_fechas).
3. La secuencia de correos de Harmonia queda creada en borrador, solo para quien acepta.
"""
import logging

from markupsafe import Markup

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

CAMPANA_HARMONIA = 'META-HARMONIA-0926'

# Código de origen de Nesto -> nombre corto para el título de la oportunidad.
# La campaña de Odoo (utm.campaign) se llama igual que el código de Nesto.
ORIGENES_CON_OPORTUNIDAD = {
    CAMPANA_HARMONIA: 'Harmonia',
}

# Embudos generales de los que hay que sacar a quien no acepta comunicaciones y a los
# leads de orígenes con secuencia propia. Se buscan por nombre porque son datos, no código.
NOMBRES_EMBUDO_GENERAL = ('Embudo de conversión',)
NOMBRE_SECUENCIA_HARMONIA = 'Secuencia Harmonia (Meta)'

# Cláusulas que se añaden al final del dominio guardado, como TEXTO: evaluarlo y volver a
# escribirlo congelaría el «hace 15 días» del embudo en la fecha de hoy.
# Cada una lleva su «o no tiene cliente / campaña»: en Odoo 16 una condición sobre una ruta
# (partner_id.…) solo encuentra registros que SÍ tienen ese partner, y un '!' delante se
# convierte en '!=' dentro de la ruta, así que también dejaría fuera a los leads sin
# cliente. El '!=' de Odoo sí incluye los vacíos (acepta_comunicaciones sin dato).
EXCLUSION_EMBUDO_GENERAL = [
    '|', ('partner_id', '=', False),
    ('partner_id.commercial_partner_id.acepta_comunicaciones', '!=', 'no'),
    '|', ('partner_id', '=', False),
    ('partner_id.commercial_partner_id.origen_cliente', '!=', CAMPANA_HARMONIA),
    '|', ('campaign_id', '=', False), ('campaign_id.name', '!=', CAMPANA_HARMONIA),
]

DOMINIO_SECUENCIA_HARMONIA = repr([
    ('type', '=', 'opportunity'),
    ('active', '=', True),
    ('stage_id.is_won', '=', False),
    ('email_from', '!=', False),
    ('campaign_id.name', '=', CAMPANA_HARMONIA),
    ('partner_id.commercial_partner_id.acepta_comunicaciones', '=', 'si'),
])


def _con_exclusion(dominio):
    """El texto del dominio con las cláusulas de exclusión al final (idempotente)."""
    texto = (dominio or '[]').strip()
    clausulas = ', '.join(repr(c) for c in EXCLUSION_EMBUDO_GENERAL)
    if clausulas in texto:
        return texto
    if not (texto.startswith('[') and texto.endswith(']')):
        raise ValueError('Dominio con un formato inesperado, no se toca: %r' % texto)
    cuerpo = texto[1:-1].strip()
    return '[%s]' % (', '.join(p for p in (cuerpo, clausulas) if p))


class ResPartner(models.Model):
    _inherit = 'res.partner'

    nv_oportunidad_origen = fields.Boolean(
        string='Oportunidad de origen creada', default=False, copy=False, index=True,
        help='Marca que ya se ha creado la oportunidad del origen del cliente (p. ej. leads '
             'de Meta). Evita duplicarla si Nesto vuelve a publicar el cliente.',
    )


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ------------------------------------------------ oportunidades por origen

    @api.model
    def _nv_crear_oportunidades_origen(self, limite=100):
        """Una oportunidad por cada cliente de Nesto con un origen de ORIGENES_CON_OPORTUNIDAD.

        Va en la tarea programada y no en la sincronización, como el enlace con clientes:
        si algo falla aquí, el mensaje de Nesto ya está guardado y no acaba en la DLQ.
        """
        clientes = self.env['res.partner'].sudo().search([
            ('origen_cliente', 'in', list(ORIGENES_CON_OPORTUNIDAD)),
            ('parent_id', '=', False),
            ('nv_oportunidad_origen', '=', False),
        ], order='id', limit=limite)
        for cliente in clientes:
            try:
                with self.env.cr.savepoint():
                    self._nv_oportunidad_origen(cliente)
                    cliente.with_context(skip_sync=True).write({'nv_oportunidad_origen': True})
            except Exception:
                _logger.exception('No se ha podido crear la oportunidad del cliente %s de Nesto '
                                  '(origen %s)', cliente.cliente_externo, cliente.origen_cliente)

    @api.model
    def _nv_campana(self, codigo):
        Campana = self.env['utm.campaign'].sudo()
        return Campana.search([('name', '=', codigo)], limit=1) or Campana.create({'name': codigo})

    @api.model
    def _nv_oportunidad_origen(self, cliente):
        campana = self._nv_campana(cliente.origen_cliente)
        Lead = self.sudo().with_context(active_test=False)
        lead = Lead.search([('partner_id.commercial_partner_id', '=', cliente.id),
                            ('campaign_id', '=', campana.id)], limit=1)
        if lead:
            _logger.info('Cliente %s de Nesto: ya tenía la oportunidad %s de %s',
                         cliente.cliente_externo, lead.id, campana.name)
            return lead

        comercial = cliente.user_id if cliente.user_id.active else self.env['res.users']
        if not comercial:
            _logger.warning('Cliente %s de Nesto (origen %s) sin comercial activo en Odoo: la '
                            'oportunidad queda sin asignar', cliente.cliente_externo, campana.name)
        # Sin email_from ni teléfonos en los valores: Odoo los copia de la ficha. Si se
        # pasaran, el inverso los escribiría en el cliente y se publicarían hacia Nesto.
        vals = {
            'name': '%s · %s' % (ORIGENES_CON_OPORTUNIDAD[cliente.origen_cliente], cliente.name),
            'type': 'opportunity',
            'partner_id': cliente.id,
            'campaign_id': campana.id,
            'user_id': comercial.id,
            'description': tools.plaintext2html(cliente.comment) if cliente.comment else False,
        }
        # user_id va siempre explícito: sin él, create() pondría al usuario del cron (OdooBot)
        lead = self.sudo().with_context(mail_create_nosubscribe=True).create(vals)

        consentimiento = dict(cliente._fields['acepta_comunicaciones'].selection).get(
            cliente.acepta_comunicaciones, 'Nesto no lo ha mandado')
        fecha = (fields.Datetime.context_timestamp(lead.with_context(tz='Europe/Madrid'), cliente.fecha_origen)
                 .strftime('%d/%m/%Y %H:%M') if cliente.fecha_origen else '—')
        lead.message_post(
            body=Markup('<p>Oportunidad creada automáticamente: el cliente <b>%s</b> entró en Nesto '
                        'por <b>%s</b> el %s.</p><p>Comunicaciones comerciales: <b>%s</b>.</p>')
            % (cliente.cliente_externo, campana.name, fecha, consentimiento),
            message_type='comment', subtype_xmlid='mail.mt_note',
        )
        _logger.info('Cliente %s de Nesto: oportunidad %s creada (%s)',
                     cliente.cliente_externo, lead.id, campana.name)
        # Si ya hubiera comprado, se gana en el acto
        self._nv_avanzar_por_fechas(cliente)
        return lead

    # ------------------------------------------- embudos de automation_oca

    @api.model
    def _nv_preparar_embudos_origen(self):
        """Excluye del embudo general y crea la secuencia de Harmonia en borrador.

        Lo llama la migración 16.0.1.5.0 y se puede repetir sin daño. Si automation_oca no
        está instalado (el CI), no hace nada.
        """
        if 'automation.configuration' not in self.env:
            _logger.info('automation_oca no está instalado: no hay embudos que preparar')
            return
        Config = self.env['automation.configuration'].sudo().with_context(active_test=False)
        modelo = self.env['ir.model']._get('crm.lead')

        generales = Config.search([('name', 'in', NOMBRES_EMBUDO_GENERAL), ('model_id', '=', modelo.id)])
        if not generales:
            _logger.warning('No se encuentra ningún embudo general (%s): no se excluye a nadie',
                            ', '.join(NOMBRES_EMBUDO_GENERAL))
        for config in generales:
            config.editable_domain = _con_exclusion(config.editable_domain)
            # Los pasos que no heredan el dominio de la configuración llevan el suyo propio
            for paso in config.automation_step_ids.filtered(
                    lambda s: not s.apply_parent_domain and s.step_type == 'mail'):
                paso.domain = _con_exclusion(paso.domain)
            _logger.info('Embudo %s (%s): excluidos los que no aceptan comunicaciones y los de %s',
                         config.id, config.name, CAMPANA_HARMONIA)

        if not Config.search([('name', '=', NOMBRE_SECUENCIA_HARMONIA)], limit=1):
            config = Config.create({
                'name': NOMBRE_SECUENCIA_HARMONIA,
                'model_id': modelo.id,
                'editable_domain': DOMINIO_SECUENCIA_HARMONIA,
                'field_id': self.env['ir.model.fields']._get('crm.lead', 'email_normalized').id,
                'is_periodic': True,
            })
            _logger.info('Secuencia de Harmonia creada en borrador (configuración %s), sin pasos', config.id)
