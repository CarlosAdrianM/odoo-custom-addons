"""Bloques de reactivación: clientes de Nesto que no compran y entran en el embudo.

Reparto con NestoAPI (endpoint api/Clientes/Sync/Republicar):

- Nesto ELIGE a quién mandar (vendedor, estados, tiempo sin comprar, con correo y sin baja
  de boletín), en bloques pequeños, y lleva un registro permanente de los ya enviados.
  Cada cliente del bloque llega por nesto_sync con `bloque_embudo` y el responsable que le
  corresponde por código postal (`responsable_embudo_email` / `_tipo`).
- Odoo decide la ENTRADA: una oportunidad por cliente, a un ritmo diario, y solo si ni el
  cliente ni ninguno de sus correos ha pasado ya por el embudo por cualquier puerta. Cada
  cliente hace el embudo una sola vez: la marca `nv_embudo_bloque` no se borra nunca.

La entrada es silenciosa: la oportunidad nace sin vendedor y sin equipo, y nadie recibe
nada. Solo se avisa al responsable (con copia a Dirección) cuando el cliente contesta a
un correo o hace un pedido posterior a su entrada.
"""
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models, tools

from .crm_lead import DOMINIO_PROPIO
from .origen_cliente import NOMBRES_EMBUDO_GENERAL

_logger = logging.getLogger(__name__)

# Oportunidades de reactivación que se crean al día como mucho (parámetro del sistema)
PARAM_POR_DIA = 'nv_crm_embudo.reactivacion_por_dia'
POR_DIA_POR_DEFECTO = 25
# Nesto publica un mensaje por contacto: se espera a que el cliente lleve este rato sin
# recibir nada antes de mirarlo, para tener todas sus personas y sus correos.
MINUTOS_REPOSO = 15
PREFIJO_CAMPANA = 'REACTIVACION-'

RESULTADOS = [
    ('oportunidad', 'Ha entrado en el embudo'),
    ('repetido', 'Ya estaba en el embudo por otra puerta'),
    ('baja', 'Todos sus correos están de baja'),
    ('sin_correo', 'Sin ningún correo utilizable'),
    ('anulado', 'Ficha anulada en Nesto'),
]

# Quien tenga la baja del boletín en Nesto no recibe correos del embudo. El '!=' de Odoo
# incluye los vacíos (Nesto no lo ha mandado); ver el aviso de las rutas en origen_cliente.
EXCLUSION_BOLETIN = [
    '|', ('partner_id', '=', False), ('partner_id.enviar_boletin', '!=', 'no'),
]
# El embudo general espera 15 días desde el alta del lead. Los de un bloque no esperan:
# no son un alta nueva, entran el día que se decide escribirles.
CLAUSULA_ESPERA = "('create_date', '<='"
SIN_ESPERA_BLOQUES = "'|', ('nv_bloque_embudo', '!=', False), "


def _con_clausulas(dominio, clausulas):
    """El texto del dominio con las cláusulas al final, sin evaluarlo (idempotente)."""
    texto = (dominio or '[]').strip()
    anadido = ', '.join(repr(c) for c in clausulas)
    if anadido in texto:
        return texto
    if not (texto.startswith('[') and texto.endswith(']')):
        raise ValueError('Dominio con un formato inesperado, no se toca: %r' % texto)
    cuerpo = texto[1:-1].strip()
    return '[%s]' % (', '.join(p for p in (cuerpo, anadido) if p))


def _sin_espera_para_bloques(dominio):
    """Los leads de un bloque no esperan los 15 días del alta (idempotente).

    Si el dominio no tiene exactamente una condición de espera, se devuelve como está.
    """
    texto = (dominio or '').strip()
    if SIN_ESPERA_BLOQUES in texto or texto.count(CLAUSULA_ESPERA) != 1:
        return texto
    return texto.replace(CLAUSULA_ESPERA, SIN_ESPERA_BLOQUES + CLAUSULA_ESPERA)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    nv_embudo_bloque = fields.Char(
        string='Bloque con el que entró en el embudo', readonly=True, copy=False, index=True,
        help='Primer bloque de Nesto con el que se procesó este cliente para el embudo. No se '
             'borra ni se cambia: cada cliente hace el embudo una sola vez, aunque Nesto lo '
             'vuelva a mandar en otro bloque.')
    nv_embudo_fecha = fields.Datetime(string='Procesado para el embudo', readonly=True, copy=False)
    nv_embudo_resultado = fields.Selection(
        RESULTADOS, string='Resultado de la entrada en el embudo', readonly=True, copy=False)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    nv_bloque_embudo = fields.Char(
        string='Bloque del embudo', readonly=True, copy=False, index=True,
        help='Bloque de reactivación de Nesto por el que se creó esta oportunidad.')
    nv_responsable_embudo_email = fields.Char(
        string='Responsable si contesta', readonly=True, copy=False,
        help='A quién se avisa cuando el cliente contesta o hace un pedido. Lo calcula Nesto '
             'con el código postal del contacto.')
    nv_responsable_embudo_tipo = fields.Char(string='Tipo de responsable', readonly=True, copy=False)
    nv_ultimo_pedido_al_entrar = fields.Date(
        string='Último pedido al entrar', readonly=True, copy=False,
        help='Fecha del último pedido del cliente cuando entró en el embudo (vacío = no había '
             'comprado nunca). Se gana cuando Nesto manda una fecha posterior.')

    # ------------------------------------------------------------ poblador

    @api.model
    def _nv_reactivacion_por_dia(self):
        valor = self._nv_param(PARAM_POR_DIA)
        try:
            return max(int(valor), 0) if valor else POR_DIA_POR_DEFECTO
        except ValueError:
            _logger.warning('Parámetro %s con un valor que no es un número (%r): se usa %s',
                            PARAM_POR_DIA, valor, POR_DIA_POR_DEFECTO)
            return POR_DIA_POR_DEFECTO

    @api.model
    def _nv_poblar_embudo_bloques(self):
        """Mete en el embudo a los clientes de los bloques de Nesto, sin pasar del cupo diario.

        Va en la tarea programada, después del enlace de leads con clientes nuevos: así un
        lead antiguo de la misma persona ya está enlazado cuando se mira si está repetida.
        """
        Partner = self.env['res.partner'].sudo()
        ahora = fields.Datetime.now()
        hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        cupo = self._nv_reactivacion_por_dia() - self.sudo().with_context(active_test=False).search_count(
            [('nv_bloque_embudo', '!=', False), ('create_date', '>=', hoy)])

        contactos = Partner.with_context(active_test=False).search([
            ('bloque_embudo', '!=', False),
            ('commercial_partner_id.nv_embudo_bloque', '=', False),
        ])
        clientes = contactos.commercial_partner_id.sorted(lambda c: c.id)
        for cliente in clientes:
            familia = Partner.with_context(active_test=False).search([('id', 'child_of', cliente.id)])
            if any(p.write_date and p.write_date > ahora - timedelta(minutes=MINUTOS_REPOSO)
                   for p in familia):
                continue
            try:
                with self.env.cr.savepoint():
                    resultado = self._nv_entrada_de_bloque(cliente, familia, crear=cupo > 0)
            except Exception:
                _logger.exception('No se ha podido procesar el cliente %s de Nesto para el embudo',
                                  cliente.cliente_externo)
                continue
            if resultado == 'oportunidad':
                cupo -= 1

    @api.model
    def _nv_entrada_de_bloque(self, cliente, familia, crear=True):
        """Procesa un cliente de un bloque y devuelve el resultado (False = se deja para mañana)."""
        activos = familia.filtered('active')
        bloque = next((p.bloque_embudo for p in (cliente | familia) if p.bloque_embudo), False)
        emails = {p.email_normalized for p in activos
                  if p.email_normalized and not p.email_normalized.endswith(DOMINIO_PROPIO)}

        resultado, persona = 'oportunidad', self.env['res.partner']
        if not cliente.active:
            resultado = 'anulado'
        elif not emails:
            resultado = 'sin_correo'
        elif self._nv_ya_en_el_embudo(cliente, emails):
            resultado = 'repetido'
        else:
            persona = self._nv_persona_para_el_embudo(cliente, activos)
            if not persona:
                resultado = 'baja'

        if resultado == 'oportunidad':
            if not crear:
                return False
            self._nv_oportunidad_de_bloque(cliente, familia, persona, bloque)
        cliente.with_context(skip_sync=True).write({
            'nv_embudo_bloque': bloque, 'nv_embudo_fecha': fields.Datetime.now(),
            'nv_embudo_resultado': resultado,
        })
        _logger.info('Cliente %s de Nesto, bloque %s del embudo: %s',
                     cliente.cliente_externo, bloque, resultado)
        return resultado

    @api.model
    def _nv_ya_en_el_embudo(self, cliente, emails):
        """True si el cliente o alguno de sus correos tiene ya un lead, abierto, ganado o archivado."""
        return bool(self.sudo().with_context(active_test=False).search_count([
            '|', ('partner_id', 'child_of', cliente.id),
            ('email_normalized', 'in', list(emails)),
        ]))

    @api.model
    def _nv_persona_para_el_embudo(self, cliente, activos):
        """La persona a la que se escribe: con correo, sin baja de boletín y fuera de la lista negra.

        Primero las personas de contacto de Nesto; la ficha del cliente, que lleva copiado
        el correo de la primera persona, solo si no queda ninguna.
        """
        if cliente.acepta_comunicaciones == 'no':
            return self.env['res.partner']
        candidatas = activos.filtered(
            lambda p: p.email_normalized and not p.email_normalized.endswith(DOMINIO_PROPIO)
            and p.enviar_boletin != 'no')
        de_baja = set(self.env['mail.blacklist'].sudo().search(
            [('email', 'in', candidatas.mapped('email_normalized'))]).mapped('email'))
        # Una persona con la baja en Nesto arrastra su correo aunque esté repetido en otra ficha
        de_baja |= {p.email_normalized for p in activos if p.enviar_boletin == 'no'}
        candidatas = candidatas.filtered(lambda p: p.email_normalized not in de_baja)
        return candidatas.sorted(lambda p: (not p.persona_contacto_externa, p.id))[:1]

    @api.model
    def _nv_ultimo_pedido(self, familia):
        return max((p.fecha_ultimo_pedido for p in familia if p.fecha_ultimo_pedido), default=False)

    @api.model
    def _nv_oportunidad_de_bloque(self, cliente, familia, persona, bloque):
        contacto = persona
        while contacto and not contacto.responsable_embudo_email:
            contacto = contacto.parent_id
        contacto = contacto or familia.filtered('responsable_embudo_email')[:1]
        ultimo = self._nv_ultimo_pedido(familia)
        campana = self._nv_campana(PREFIJO_CAMPANA + (bloque or '').split('-')[0])
        # Sin email_from ni teléfonos: Odoo los copia de la ficha (ver _nv_oportunidad_origen).
        # Sin vendedor ni equipo: la entrada no le aparece ni le llega a nadie.
        lead = self.sudo().with_context(
            mail_create_nosubscribe=True, mail_auto_subscribe_no_notify=True).create({
                'name': 'Reactivación · %s' % cliente.name,
                'type': 'opportunity',
                'partner_id': persona.id,
                'campaign_id': campana.id,
                'user_id': False,
                'team_id': False,
                'nv_bloque_embudo': bloque,
                'nv_responsable_embudo_email': contacto.responsable_embudo_email,
                'nv_responsable_embudo_tipo': contacto.responsable_embudo_tipo,
                'nv_ultimo_pedido_al_entrar': ultimo,
            })
        lead.message_post(
            body=Markup('<p>Entra en el embudo por el bloque <b>%s</b> de Nesto (cliente <b>%s</b>, '
                        'estado %s, vendedor %s).</p><p>Último pedido: <b>%s</b>.</p>'
                        '<p>Si contesta o hace un pedido se avisa a <b>%s</b> (%s).</p>')
            % (bloque, cliente.cliente_externo, cliente.estado_nesto or '—',
               cliente.vendedor_nesto or '—',
               ultimo.strftime('%d/%m/%Y') if ultimo else 'no ha comprado nunca',
               contacto.responsable_embudo_email or 'nadie: Nesto no ha mandado responsable',
               contacto.responsable_embudo_tipo or '—'),
            message_type='comment', subtype_xmlid='mail.mt_note',
        )
        return lead

    # ------------------------------------------- ganar por un pedido nuevo

    def _nv_ha_comprado_tras_entrar(self, cliente=None):
        """True si Nesto ha mandado un pedido posterior al que tenía el cliente al entrar."""
        self.ensure_one()
        cliente = cliente or self.partner_id.sudo().commercial_partner_id
        if not cliente:
            return False
        familia = self.env['res.partner'].sudo().with_context(active_test=False).search(
            [('id', 'child_of', cliente.id)])
        ultimo = self._nv_ultimo_pedido(familia)
        return bool(ultimo and (not self.nv_ultimo_pedido_al_entrar
                                or ultimo > self.nv_ultimo_pedido_al_entrar))

    def _nv_avanzar_reactivacion(self, cliente):
        """Leads de bloque: se ganan con un pedido NUEVO, no con los de hace años."""
        for lead in self:
            if not lead._nv_ha_comprado_tras_entrar(cliente):
                continue
            lead.message_post(
                body=Markup('<p>Ganado automáticamente: el cliente <b>%s</b> ha vuelto a comprar '
                            'en Nesto después de entrar en el embudo.</p>')
                % (cliente.cliente_externo or cliente.display_name),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            lead._nv_asignar_responsable()
            lead.action_set_won()
            lead._nv_avisar_pedido(cliente)
            _logger.info('Lead %s del bloque %s ganado por un pedido nuevo del cliente %s',
                         lead.id, lead.nv_bloque_embudo, cliente.cliente_externo)

    # ----------------------------------------------- avisos al responsable

    def _nv_usuario_responsable(self):
        """El usuario de Odoo del responsable, si lo tiene (Tienda online no lo tiene)."""
        self.ensure_one()
        correo = tools.email_normalize(self.nv_responsable_embudo_email or '')
        if not correo:
            return self.env['res.users']
        return self.env['res.users'].sudo().search(
            ['|', ('login', '=ilike', correo), ('email', '=ilike', correo)], limit=1)

    def _nv_asignar_responsable(self):
        """Pone al responsable como vendedor cuando el cliente ya ha dado señales de vida.

        Sin el aviso «te han asignado» de Odoo: el aviso que recibe es el nuestro.
        """
        for lead in self.filtered(lambda l: l.nv_bloque_embudo and not l.user_id):
            usuario = lead._nv_usuario_responsable()
            if usuario:
                lead.sudo().with_context(mail_auto_subscribe_no_notify=True).write({'user_id': usuario.id})

    def message_update(self, msg_dict, update_vals=None):
        """Cuando el cliente contesta, el responsable pasa a ser el vendedor en el acto.

        Antes de que el embudo ejecute sus pasos de «ha contestado»: la tarea de ese paso
        se asigna al vendedor de la oportunidad, y las de un bloque nacen sin vendedor.
        Si el responsable no tiene usuario en Odoo (Tienda online) solo recibe el correo.
        """
        self._nv_asignar_responsable()
        return super().message_update(msg_dict, update_vals=update_vals)

    def _nv_avisar_pedido(self, cliente):
        """Correo al responsable, con copia a Dirección: el cliente ha hecho un pedido."""
        self.ensure_one()
        destino = self.nv_responsable_embudo_email or self.user_id.email
        copias = self.nv_cc_aviso_respuesta()
        if not destino:
            destino, copias = copias, False
        if not destino:
            _logger.warning('Lead %s ganado por un pedido, pero sin nadie a quien avisar', self.id)
            return
        nombre = self.contact_name or self.partner_name or self.email_from or self.name
        enlace = '%s/web#model=crm.lead&view_type=form&id=%s' % (self.get_base_url(), self.id)
        self.env['mail.mail'].sudo().create({
            'subject': 'Ha hecho un pedido %s (embudo, bloque %s)' % (nombre, self.nv_bloque_embudo),
            'email_from': self.nv_email_from_embudo(),
            'email_to': destino,
            'email_cc': copias or False,
            'auto_delete': True,
            'body_html': Markup(
                '<div style="font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:22px; color:#333333;">'
                '<p>Hola,</p><p><strong>%s</strong> (cliente %s de Nesto) ha hecho un pedido después de '
                'entrar en el embudo de correos. Llevaba tiempo sin comprar o no había comprado nunca: '
                'es buen momento para atenderle.</p>'
                '<p><a href="%s" style="color:#BD052B; font-weight:600;">Abrir la oportunidad en Odoo</a></p></div>')
            % (nombre, cliente.cliente_externo or '—', enlace),
        })

    # ----------------------------------------------------------- medición

    @api.model
    def nv_resumen_bloques(self):
        """Una fila por bloque: lo recibido de Nesto y lo que ha pasado con ello."""
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        Lead = self.sudo().with_context(active_test=False)
        filas = []
        bloques = sorted(set(Partner.search([('nv_embudo_bloque', '!=', False)]).mapped('nv_embudo_bloque'))
                         | set(Partner.search([('bloque_embudo', '!=', False)]).mapped('bloque_embudo')))
        for bloque in bloques:
            procesados = Partner.search([('nv_embudo_bloque', '=', bloque)])
            leads = Lead.search([('nv_bloque_embudo', '=', bloque)])
            pendientes = Partner.search([('bloque_embudo', '=', bloque)]).commercial_partner_id.filtered(
                lambda c: not c.nv_embudo_bloque)
            fila = {'bloque': bloque, 'pendientes': len(pendientes), 'oportunidades': len(leads)}
            for clave, _etiqueta in RESULTADOS:
                if clave != 'oportunidad':
                    fila[clave] = len(procesados.filtered(lambda c: c.nv_embudo_resultado == clave))
            fila.update({
                'rebotes': len(leads.filtered(lambda l: l.message_bounce > 0)),
                'bajas': len(leads.filtered('is_blacklisted')),
                'respuestas': len(leads.filtered(lambda l: l.nv_ultima_respuesta())),
                'ganados': len(leads.filtered(lambda l: l.stage_id.is_won)),
            })
            filas.append(fila)
        return filas

    # ------------------------------------------- embudo de automation_oca

    @api.model
    def _nv_preparar_embudo_bloques(self):
        """Adapta el embudo general a los bloques: sin espera de 15 días y sin bajas de boletín.

        Lo llama la migración 16.0.1.6.0 y se puede repetir sin daño. Sin automation_oca
        (el CI) no hace nada.
        """
        if 'automation.configuration' not in self.env:
            _logger.info('automation_oca no está instalado: no hay embudos que preparar')
            return
        Config = self.env['automation.configuration'].sudo().with_context(active_test=False)
        modelo = self.env['ir.model']._get('crm.lead')
        for config in Config.search([('name', 'in', NOMBRES_EMBUDO_GENERAL), ('model_id', '=', modelo.id)]):
            dominio = _sin_espera_para_bloques(_con_clausulas(config.editable_domain, EXCLUSION_BOLETIN))
            if SIN_ESPERA_BLOQUES not in dominio:
                _logger.warning('Embudo %s (%s): no se encuentra la espera del alta en el dominio; los '
                                'leads de bloque esperarán como los demás', config.id, config.name)
            config.editable_domain = dominio
            for paso in config.automation_step_ids.filtered(
                    lambda s: not s.apply_parent_domain and s.step_type == 'mail'):
                paso.domain = _con_clausulas(paso.domain, EXCLUSION_BOLETIN)
            _logger.info('Embudo %s (%s): preparado para los bloques de reactivación', config.id, config.name)
