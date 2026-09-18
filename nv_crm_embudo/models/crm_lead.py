import logging
import re
from datetime import timedelta

import werkzeug.urls
from markupsafe import Markup

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

DOMINIO_PROPIO = '@nuevavision.es'

# Margen para no adelantarnos a una sincronización que aún no ha terminado
MINUTOS_MARGEN = 2
# Nesto manda un mensaje por contacto y el cliente principal llega el primero: las personas
# de contacto (que son quienes traen el email) pueden tardar. Mientras el cliente no llegue
# a esta edad se reintenta en cada pasada; después se da por revisado aunque no haya salido nada.
HORAS_REINTENTO = 24
# Tope de la consulta: un cliente más viejo que esto ya no se mira aunque quedara sin marcar
# (con HORAS_REINTENTO todos acaban marcados, esto es solo una red por si hubo una parada larga)
DIAS_VENTANA = 30


def _ultimos9(numero):
    digitos = re.sub(r'\D', '', numero or '')
    return digitos[-9:] if len(digitos) >= 9 else False


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ---------------------------------------------------------------- baja

    def _nv_baja_token(self):
        self.ensure_one()
        return tools.hmac(self.env(su=True), 'nv_embudo_baja', (self.id, self.email_normalized or ''))

    def nv_url_baja(self):
        """URL de baja para usar en las plantillas de correo del embudo."""
        self.ensure_one()
        return werkzeug.urls.url_join(self.get_base_url(), '/nv/baja/%s/%s' % (self.id, self._nv_baja_token()))

    # ------------------------------------------- enlace con clientes de Nesto

    @api.model
    def _nv_cron_enlazar_clientes_nesto(self, limite=100):
        """Busca el lead de origen de cada cliente creado en Nesto desde la última pasada.

        Va aparte de la sincronización a propósito: si algo falla aquí, el mensaje de Nesto
        ya está guardado y no se reintenta ni acaba en la DLQ.

        Cada cliente se marca con `nv_lead_revisado` cuando se resuelve, en vez de llevar un
        marcador de «último id visto»: el cliente principal se crea antes que sus personas de
        contacto (validate_cliente_principal_exists lo exige), así que un cliente sin emails
        todavía puede tenerlos dentro de un rato y hay que volver a mirarlo. Los clientes que
        ya existían al instalar el módulo quedan marcados por el post_init_hook.
        """
        ahora = fields.Datetime.now()
        clientes = self.env['res.partner'].sudo().with_context(active_test=False).search([
            ('cliente_externo', '!=', False),
            ('parent_id', '=', False),
            ('nv_lead_revisado', '=', False),
            ('create_date', '>', ahora - timedelta(days=DIAS_VENTANA)),
            ('create_date', '<=', ahora - timedelta(minutes=MINUTOS_MARGEN)),
        ], order='create_date', limit=limite)
        if not clientes:
            return

        # Una sola lectura de leads por pasada, no una por cliente
        leads = self._nv_leads_abiertos()
        for cliente in clientes:
            agotado = cliente.create_date <= ahora - timedelta(hours=HORAS_REINTENTO)
            try:
                with self.env.cr.savepoint():
                    resuelto = self._nv_enlazar_cliente_nesto(cliente, leads)
            except Exception:
                _logger.exception('No se ha podido enlazar el cliente %s de Nesto con su lead',
                                  cliente.cliente_externo)
                resuelto = False
            if resuelto:
                cliente._nv_marcar_lead_revisado()
            elif agotado:
                _logger.info('Cliente %s de Nesto: sin lead de origen tras %s horas, se deja de buscar',
                             cliente.cliente_externo, HORAS_REINTENTO)
                cliente._nv_marcar_lead_revisado()

    @api.model
    def _nv_datos_contacto_cliente(self, cliente):
        familia = cliente | cliente.with_context(active_test=False).child_ids
        emails = {
            p.email_normalized for p in familia
            if p.email_normalized and not p.email_normalized.endswith(DOMINIO_PROPIO)
        }
        telefonos = {t for p in familia for t in (_ultimos9(p.phone), _ultimos9(p.mobile)) if t}
        return emails, telefonos

    @api.model
    def _nv_leads_abiertos(self):
        """Leads abiertos y sin cliente de Nesto, leídos una sola vez por pasada.

        Se leen con search_read (solo las tres columnas que hacen falta, sin recordsets) y se
        comparan en Python: el criterio son los últimos 9 dígitos del teléfono y en la base de
        datos están con espacios, prefijos y guiones, así que un LIKE sobre la columna no vale.
        """
        return self.sudo().search_read([
            # En producción no se usan leads sin convertir: los 198 registros son oportunidades
            ('type', '=', 'opportunity'),
            ('stage_id.is_won', '=', False),
            '|', ('partner_id', '=', False),
            ('partner_id.commercial_partner_id.cliente_externo', '=', False),
        ], ['email_normalized', 'phone', 'mobile'])

    @api.model
    def _nv_leads_candidatos(self, emails, telefonos, leads):
        """De los leads leídos, los de este cliente: {lead: 'email y teléfono'}."""
        candidatos = {}
        for lead in leads:
            coincide = []
            if lead['email_normalized'] and lead['email_normalized'] in emails:
                coincide.append('email')
            if {_ultimos9(lead['phone']), _ultimos9(lead['mobile'])} & telefonos:
                coincide.append('teléfono')
            if coincide:
                candidatos[self.browse(lead['id'])] = ' y '.join(coincide)
        return candidatos

    @api.model
    def _nv_enlazar_cliente_nesto(self, cliente, leads):
        """Devuelve True si el cliente queda resuelto (enlazado o pasado a la vendedora)."""
        emails, telefonos = self._nv_datos_contacto_cliente(cliente)
        if not emails and not telefonos:
            return False
        candidatos = self._nv_leads_candidatos(emails, telefonos, leads)
        if not candidatos:
            return False
        if len(candidatos) == 1:
            lead, motivo = next(iter(candidatos.items()))
            etapa = self.env.ref('nv_crm_embudo.stage_cliente_nesto', raise_if_not_found=False)
            lead._nv_enlazar_con_cliente(cliente, motivo, etapa)
            return True

        # No elegimos por la vendedora: que lo decida ella
        for lead in candidatos:
            responsable = self._nv_responsable_tarea(lead, cliente)
            if not responsable:
                _logger.warning('Lead %s del cliente %s de Nesto: sin responsable activo, no se crea la tarea',
                                lead.id, cliente.cliente_externo)
                continue
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                summary='¿Este lead es el cliente %s de Nesto?' % cliente.cliente_externo,
                note=Markup('<p>Se ha creado en Nesto el cliente <b>%s %s</b>, que coincide con %s leads abiertos. '
                            'Enlaza el que corresponda poniéndole ese cliente.</p>')
                % (cliente.cliente_externo, cliente.name, len(candidatos)),
                user_id=responsable.id,
            )
        _logger.info('Cliente %s de Nesto: %s leads candidatos, se pide a la vendedora que elija',
                     cliente.cliente_externo, len(candidatos))
        return True

    @api.model
    def _nv_responsable_tarea(self, lead, cliente):
        """Primer usuario activo entre la vendedora del lead y la del cliente.

        En el cron `env.user` es OdooBot, así que no sirve de recambio: una tarea suya no la
        ve nadie. Si no hay vendedora activa se avisa por log y no se crea la tarea.
        """
        for usuario in (lead.user_id, cliente.user_id):
            if usuario and usuario.active:
                return usuario
        return self.env['res.users'].browse()

    def _nv_enlazar_con_cliente(self, cliente, motivo='email o teléfono', etapa=None):
        self.ensure_one()
        antes = [
            (etiqueta, self[campo]) for etiqueta, campo in (
                ('Empresa', 'partner_name'), ('Contacto', 'contact_name'), ('Email', 'email_from'),
                ('Teléfono', 'phone'), ('Móvil', 'mobile'), ('Dirección', 'street'),
                ('Población', 'city'), ('C.P.', 'zip'))
            if self[campo]
        ]
        if self.partner_id:
            antes.append(('Cliente anterior', self.partner_id.display_name))
        vals = {'partner_id': cliente.id}
        if etapa and self.stage_id.sequence < etapa.sequence:
            vals['stage_id'] = etapa.id
        # Al poner el cliente, Odoo copia al lead los datos de la ficha de Nesto (nombre, dirección...).
        # La ficha del cliente no se toca, así que no se publica nada hacia Nesto.
        self.write(vals)
        filas = Markup('').join(Markup('<li>%s: %s</li>') % (e, v) for e, v in antes)
        self.message_post(
            body=Markup('<p>Enlazado automáticamente con el cliente <b>%s</b> de Nesto (coincide por %s).</p>'
                        '<p>Datos que tenía el lead antes del enlace:</p><ul>%s</ul>')
            % (cliente.cliente_externo, motivo, filas),
            message_type='comment', subtype_xmlid='mail.mt_note',
        )
        _logger.info('Lead %s enlazado con el cliente %s de Nesto', self.id, cliente.cliente_externo)
