from odoo import fields, models


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    nv_sin_contactos = fields.Boolean(
        string='No crear contactos al enviar en masa', default=False,
        help='En un envío masivo (automation_oca, «Enviar mensaje» a varios registros) Odoo '
             'convierte cada dirección de «Para» en un contacto, creándolo si no existe. Con esta '
             'marca el correo sale a la dirección tal cual y no se crea ningún contacto. Para los '
             'correos del embudo: cada lead crearía un contacto basura con su email, y nesto_sync '
             'intentaría publicarlo.',
    )

    def generate_recipients(self, results, res_ids):
        """Envío masivo sin convertir los emails en contactos.

        El compositor en modo masivo renderiza con ``tpl_partners_only`` y entonces el estándar
        hace ``res.partner.find_or_create`` por cada dirección de email_to/email_cc
        (mail_template.generate_recipients). Para las plantillas marcadas se quita ese contexto:
        el correo se queda con ``email_to`` y el compositor lo envía igual (``_process_recipient_values``
        acepta email_to sin destinatarios).
        """
        if self.nv_sin_contactos and self.env.context.get('tpl_partners_only'):
            return super(MailTemplate, self.with_context(tpl_partners_only=False)).generate_recipients(results, res_ids)
        return super().generate_recipients(results, res_ids)
