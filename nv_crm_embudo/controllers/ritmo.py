import hmac as hmac_lib
import json

from odoo import http
from odoo.http import request

from ..models.ritmo_embudo import PARAM_CLAVE


class NvEmbudoRitmo(http.Controller):
    """Recomendación de ritmo del embudo, de solo lectura, para el job diario de NestoAPI."""

    @http.route('/nv/embudo/recomendacion', type='http', auth='public', methods=['GET'], csrf=False, sitemap=False)
    def recomendacion(self, **kw):
        esperada = (request.env['ir.config_parameter'].sudo().get_param(PARAM_CLAVE) or '').strip()
        recibida = request.httprequest.headers.get('X-NV-Clave') or ''
        if not esperada or not hmac_lib.compare_digest(esperada.encode(), recibida.encode()):
            return request.make_response('', status=403)
        fila = request.env['nv.embudo.recomendacion'].sudo().search([], limit=1)
        if not fila:
            return request.make_response(json.dumps({'recomendacion': None}), status=404,
                                         headers=[('Content-Type', 'application/json')])
        return request.make_response(json.dumps(fila.nv_json()), headers=[('Content-Type', 'application/json')])
