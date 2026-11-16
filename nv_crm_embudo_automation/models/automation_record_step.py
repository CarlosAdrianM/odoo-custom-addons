import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Estados de mail.mail que significan «este correo ya ha salido o va a salir».
SALIDO = ('outgoing', 'sent')


class AutomationRecordStep(models.Model):
    _inherit = 'automation.record.step'

    def _nv_correos(self):
        return self.env['mail.mail'].sudo().search([('automation_record_step_id', '=', self.id)])

    def _run_mail(self):
        """No vuelve a mandar el correo de un paso que ya lo tiene en cola o enviado.

        automation_oca envía con auto_commit: el correo queda guardado y enviado antes de que el
        paso se marque como hecho. Si el cron muere entre medias (límite de tiempo, caída del
        servidor de correo), el paso sigue «programado» y en la siguiente pasada se mandaba otra
        vez. El 13/11/2026 seis clientes de NV-2026-11-04 recibieron el correo 01 dos veces.
        """
        correos = self._nv_correos()
        if correos.filtered(lambda m: m.state in SALIDO):
            _logger.info('Paso %s del embudo: el correo ya estaba en cola o enviado; no se repite', self.id)
            self.mail_status = 'sent'
            return True
        # Intentos anteriores que fallaron: el nuevo los sustituye, así no se acumulan ni se reintentan.
        correos.filtered(lambda m: m.state == 'exception').write({'state': 'cancel'})
        return super()._run_mail()

    def _check_to_execute(self):
        """No sigue la secuencia con quien no recibió el correo anterior.

        Si el correo del paso padre acabó en error (y ya no se va a reintentar), el siguiente
        correo llegaría sin el anterior: el paso se rechaza. Si no hay ningún correo guardado
        (plantilla con borrado automático, pasos de prueba) se sigue como siempre.
        """
        padre = self.parent_id
        if padre and padre.step_type == 'mail' and not padre.is_test:
            correos = padre._nv_correos()
            if correos and not correos.filtered(lambda m: m.state in SALIDO):
                _logger.info('Paso %s del embudo rechazado: el correo anterior (paso %s) no salió', self.id, padre.id)
                return False
        return super()._check_to_execute()
