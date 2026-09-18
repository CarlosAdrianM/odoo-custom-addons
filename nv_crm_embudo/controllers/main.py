import hmac as hmac_lib
from markupsafe import Markup, escape

from odoo import http
from odoo.http import request

PAGINA = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Nueva Visión</title>
<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f6f4;color:#222;margin:0;padding:48px 20px}
main{max-width:480px;margin:0 auto;background:#fff;border:1px solid #ddd;border-radius:6px;padding:28px}
h1{font-size:20px;margin:0 0 12px}p{line-height:1.5}button{font-size:15px;padding:10px 18px;border-radius:4px;
border:1px solid #146b5e;background:#146b5e;color:#fff;cursor:pointer}</style></head><body><main>%s</main></body></html>"""


class NvEmbudoBaja(http.Controller):

    def _lead(self, lead_id, token):
        lead = request.env['crm.lead'].sudo().with_context(active_test=False).browse(lead_id).exists()
        if not lead or not lead.email_normalized:
            return None
        if not hmac_lib.compare_digest(lead._nv_baja_token(), token or ''):
            return None
        return lead

    def _pagina(self, cuerpo, status=200):
        return request.make_response(PAGINA % cuerpo, headers=[('Content-Type', 'text/html; charset=utf-8')], status=status)

    @http.route('/nv/baja/<int:lead_id>/<string:token>', type='http', auth='public', methods=['GET'], sitemap=False)
    def baja_confirmar(self, lead_id, token, **kw):
        # Solo muestra la confirmacion: los antivirus de correo abren los enlaces y no deben dar de baja a nadie.
        lead = self._lead(lead_id, token)
        if not lead:
            return self._pagina('<h1>Enlace no válido</h1><p>Este enlace de baja no es válido o ha caducado.</p>', 404)
        return self._pagina(
            '<h1>Darte de baja</h1><p>No volveremos a enviar correos comerciales a <b>%s</b>.</p>'
            '<form method="post"><button type="submit">Confirmar la baja</button></form>' % escape(lead.email_normalized))

    # csrf=False porque el formulario lo ve un destinatario anonimo desde su correo:
    # quien protege la accion es el HMAC del token, que solo conoce quien recibio el enlace.
    @http.route('/nv/baja/<int:lead_id>/<string:token>', type='http', auth='public', methods=['POST'], csrf=False, sitemap=False)
    def baja_aplicar(self, lead_id, token, **kw):
        lead = self._lead(lead_id, token)
        if not lead:
            return self._pagina('<h1>Enlace no válido</h1><p>Este enlace de baja no es válido o ha caducado.</p>', 404)
        request.env['mail.blacklist'].sudo()._add(lead.email_normalized)
        lead.message_post(body=Markup('<p>El cliente se ha dado de baja de los correos comerciales desde el enlace del correo.</p>'),
                          message_type='comment', subtype_xmlid='mail.mt_note')
        return self._pagina('<h1>Baja confirmada</h1><p>Hecho. No recibirás más correos comerciales nuestros en <b>%s</b>.</p>'
                            % escape(lead.email_normalized))
