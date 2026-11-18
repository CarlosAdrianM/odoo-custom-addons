import logging
import re
from datetime import timedelta

from odoo import fields, models

_logger = logging.getLogger(__name__)

MAX_REINTENTOS = 3
ESPERA = timedelta(minutes=20)       # entre un intento y el siguiente
ANTIGUEDAD_MAXIMA = timedelta(days=2)  # un correo fallido más viejo ya no se reintenta solo

# Fallos del servidor o de la conexión, no del destinatario: merece la pena reintentar.
# Ejemplos reales de O365 (13/11/2026): «[Errno 104] Connection reset by peer»,
# «530 5.7.57 Client not authenticated ... 451 4.7.0 Temporary server error».
PASAJERO = re.compile(
    r'connection (reset|unexpectedly closed|refused|timed out)|timed? ?out|temporar|try again'
    r'|\b4\d\d\b|\b4\.\d{1,3}\.\d{1,3}\b|server ?disconnected|errno 10[34]|errno 110',
    re.IGNORECASE)


class MailMail(models.Model):
    _inherit = 'mail.mail'

    nv_reintentos = fields.Integer('Reintentos del embudo', default=0, readonly=True)

    def _nv_es_pasajero(self):
        self.ensure_one()
        if self.failure_type in ('mail_email_invalid', 'mail_email_missing', 'mail_bl', 'mail_optout', 'mail_dup'):
            return False
        return bool(PASAJERO.search(self.failure_reason or ''))

    def _nv_reintentar_correos_embudo(self):
        ahora = fields.Datetime.now()
        candidatos = self.sudo().search([
            ('state', '=', 'exception'),
            ('automation_record_step_id', '!=', False),
            ('nv_reintentos', '<', MAX_REINTENTOS),
            ('create_date', '>=', ahora - ANTIGUEDAD_MAXIMA),
            ('write_date', '<=', ahora - ESPERA),
        ])
        reintentar = self.browse()
        for correo in candidatos:
            hermanos = self.sudo().search([
                ('automation_record_step_id', '=', correo.automation_record_step_id.id), ('id', '!=', correo.id)])
            if hermanos.filtered(lambda m: m.state in ('outgoing', 'sent')):
                correo.state = 'cancel'  # el cliente ya lo tiene: este intento sobra
            elif correo._nv_es_pasajero():
                reintentar |= correo
        for correo in reintentar:
            _logger.info('Correo %s del embudo: reintento %s tras «%s»', correo.id, correo.nv_reintentos + 1,
                         (correo.failure_reason or '')[:120])
            correo.write({'state': 'outgoing', 'nv_reintentos': correo.nv_reintentos + 1,
                          'failure_reason': False, 'failure_type': False})
        return reintentar
