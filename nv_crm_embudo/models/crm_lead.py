import logging
import re
from datetime import timedelta

import werkzeug.urls
from markupsafe import Markup

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

PARAM_ULTIMO_CLIENTE = 'nv_crm_embudo.ultimo_cliente_nesto_revisado'
DOMINIO_PROPIO = '@nuevavision.es'


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
    def _nv_cron_enlazar_clientes_nesto(self, limite=500):
        """Busca el lead de origen de cada cliente creado en Nesto desde la última pasada.

        Va aparte de la sincronización a propósito: si algo falla aquí, el mensaje de Nesto
        ya está guardado y no se reintenta ni acaba en la DLQ.
        """
        icp = self.env['ir.config_parameter'].sudo()
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        ultimo = icp.get_param(PARAM_ULTIMO_CLIENTE)
        if not ultimo:
            # Primera ejecución: solo nos interesan los clientes que se creen a partir de ahora
            icp.set_param(PARAM_ULTIMO_CLIENTE, Partner.search([], order='id desc', limit=1).id or 0)
            return
        # Margen de 2 minutos para no adelantarnos a una sincronización que aún no ha terminado
        clientes = Partner.search([
            ('id', '>', int(ultimo)),
            ('cliente_externo', '!=', False),
            ('parent_id', '=', False),
            ('create_date', '<=', fields.Datetime.now() - timedelta(minutes=2)),
        ], order='id', limit=limite)
        for cliente in clientes:
            try:
                with self.env.cr.savepoint():
                    self._nv_enlazar_cliente_nesto(cliente)
            except Exception:
                _logger.exception('No se ha podido enlazar el cliente %s de Nesto con su lead', cliente.cliente_externo)
        if clientes:
            icp.set_param(PARAM_ULTIMO_CLIENTE, clientes[-1].id)

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
    def _nv_leads_candidatos(self, emails, telefonos):
        """Leads abiertos, sin cliente de Nesto, con el mismo email o teléfono: {lead: 'email y teléfono'}."""
        leads = self.sudo().search([
            ('stage_id.is_won', '=', False),
            '|', ('partner_id', '=', False), ('partner_id.commercial_partner_id.cliente_externo', '=', False),
        ])
        candidatos = {}
        for lead in leads:
            coincide = []
            if lead.email_normalized and lead.email_normalized in emails:
                coincide.append('email')
            if {_ultimos9(lead.phone), _ultimos9(lead.mobile)} & telefonos:
                coincide.append('teléfono')
            if coincide:
                candidatos[lead] = ' y '.join(coincide)
        return candidatos

    @api.model
    def _nv_enlazar_cliente_nesto(self, cliente):
        emails, telefonos = self._nv_datos_contacto_cliente(cliente)
        if not emails and not telefonos:
            return
        candidatos = self._nv_leads_candidatos(emails, telefonos)
        if len(candidatos) == 1:
            lead, motivo = next(iter(candidatos.items()))
            lead._nv_enlazar_con_cliente(cliente, motivo)
        elif len(candidatos) > 1:
            # No elegimos por la vendedora: que lo decida ella
            for lead in candidatos:
                lead.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary='¿Este lead es el cliente %s de Nesto?' % cliente.cliente_externo,
                    note=Markup('<p>Se ha creado en Nesto el cliente <b>%s %s</b>, que coincide con %s leads abiertos. '
                                'Enlaza el que corresponda poniéndole ese cliente.</p>')
                    % (cliente.cliente_externo, cliente.name, len(candidatos)),
                    user_id=lead.user_id.id or cliente.user_id.id or self.env.uid,
                )
            _logger.info('Cliente %s de Nesto: %s leads candidatos, se pide a la vendedora que elija',
                         cliente.cliente_externo, len(candidatos))

    def _nv_enlazar_con_cliente(self, cliente, motivo='email o teléfono'):
        self.ensure_one()
        antes = [
            (etiqueta, self[campo]) for etiqueta, campo in (
                ('Empresa', 'partner_name'), ('Contacto', 'contact_name'), ('Email', 'email_from'),
                ('Teléfono', 'phone'), ('Móvil', 'mobile'), ('Dirección', 'street'),
                ('Población', 'city'), ('C.P.', 'zip'))
            if self[campo]
        ]
        vals = {'partner_id': cliente.id}
        etapa = self.env.ref('nv_crm_embudo.stage_cliente_nesto', raise_if_not_found=False)
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
