import hmac as hmac_lib
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_SECRETO = 'nv_crm_embudo.mailchimp_secreto'


class NvMailchimpWebhook(http.Controller):
    """t15: Mailchimp avisa a Odoo de las bajas para no seguir escribiendo desde aqui.

    URL a configurar en Mailchimp (Audience > Settings > Webhooks):
        https://<odoo>/nv/mailchimp/<secreto>
    con los eventos "Unsubscribes" y "Cleaned address". El secreto es el parametro de sistema
    nv_crm_embudo.mailchimp_secreto; si esta vacio, el webhook no hace nada.
    """

    def _secreto_ok(self, secreto):
        esperado = request.env['ir.config_parameter'].sudo().get_param(PARAM_SECRETO) or ''
        return bool(esperado) and hmac_lib.compare_digest(esperado, secreto or '')

    @http.route('/nv/mailchimp/<string:secreto>', type='http', auth='public', methods=['GET'], sitemap=False)
    def validar(self, secreto, **kw):
        # Mailchimp hace un GET para comprobar que la URL existe antes de guardarla
        if not self._secreto_ok(secreto):
            return request.make_response('', status=404)
        return request.make_response('ok')

    @http.route('/nv/mailchimp/<string:secreto>', type='http', auth='public', methods=['POST'], csrf=False, sitemap=False)
    def evento(self, secreto, **post):
        if not self._secreto_ok(secreto):
            return request.make_response('', status=404)
        tipo = post.get('type')
        email = post.get('data[email]') or ''
        if tipo in ('unsubscribe', 'cleaned') and email:
            request.env['mail.blacklist'].sudo()._add(email)
            _logger.info('Mailchimp %s: %s añadido a la lista negra (lista %s)', tipo, email, post.get('data[list_id]'))
        else:
            _logger.info('Mailchimp: evento %s ignorado', tipo)
        return request.make_response('ok')
