"""Ritmo automático del embudo: motivo de los rebotes, recomendación diaria y su lectura."""
import unittest
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.nv_crm_embudo.models.ritmo_embudo import PARAM_CLAVE, clasificar_rebote, decidir

GMAIL = """Reporting-MTA: dns;AM9P192MB1329.EURP192.PROD.OUTLOOK.COM
Final-Recipient: rfc822;nadie@example.com
Action: failed
Status: 5.1.1
Diagnostic-Code: smtp;550-5.1.1 The email account that you tried to reach does not exist.

Authentication-Results: spf=pass smtp.mailfrom=nuevavision.es; dkim=pass
"""
LIMPIA = dict(tandas=7, escalones=1, enviados=350, entregados=315, rebotes=35, rebotes_politica=0,
              fallos_envio=0, bajas=1, aperturas=100)


class TestClasificarRebote(unittest.TestCase):

    def test_por_codigo(self):
        self.assertEqual(clasificar_rebote(GMAIL), ('inexistente', '5.1.1'))
        self.assertEqual(clasificar_rebote('Status: 5.4.1\nRecipient address rejected: Access denied')[0], 'inexistente')
        self.assertEqual(clasificar_rebote('Status: 5.2.2\nmailbox full\nspf=pass dkim=pass'), ('temporal', '5.2.2'))
        self.assertEqual(clasificar_rebote('Status: 4.4.7\nmessage expired')[0], 'temporal')
        self.assertEqual(clasificar_rebote('Status: 5.7.1\nMessage rejected as spam by policy'), ('politica', '5.7.1'))
        self.assertEqual(clasificar_rebote('Status: 5.7.1\n550 5.7.1 user unknown')[0], 'inexistente')
        self.assertEqual(clasificar_rebote('Status: 5.0.0\nalgo raro')[0], 'otro')

    def test_sin_codigo(self):
        self.assertEqual(clasificar_rebote('Your message was blocked: poor reputation'), ('politica', ''))
        self.assertEqual(clasificar_rebote('No such user here'), ('inexistente', ''))
        self.assertEqual(clasificar_rebote(''), ('otro', ''))


class TestDecidir(unittest.TestCase):

    def test_semana_limpia_sube_un_escalon(self):
        self.assertEqual(decidir(LIMPIA, {}, 50)[:2], ('subir', 75))
        self.assertEqual(decidir(LIMPIA, dict(LIMPIA), 75)[:2], ('subir', 100))
        self.assertEqual(decidir(LIMPIA, {}, 100)[:2], ('mantener', 100))

    def test_pocos_datos_o_escalones_mezclados_mantiene(self):
        self.assertEqual(decidir(dict(LIMPIA, tandas=4), {}, 50)[:2], ('mantener', 50))
        self.assertEqual(decidir(dict(LIMPIA, escalones=2), {}, 75)[:2], ('mantener', 75))
        self.assertEqual(decidir(dict(LIMPIA, enviados=0), {}, 50)[0], 'mantener')

    def test_frenos(self):
        peor = dict(LIMPIA, rebotes=70, entregados=280)
        self.assertEqual(decidir(peor, LIMPIA, 50)[0], 'mantener', 'El rebote sube respecto a la semana anterior')
        self.assertEqual(decidir(dict(LIMPIA, bajas=5), {}, 50)[0], 'mantener')
        self.assertEqual(decidir(dict(LIMPIA, aperturas=50), LIMPIA, 50)[0], 'mantener')

    def test_bajar_y_parar(self):
        self.assertEqual(decidir(dict(LIMPIA, rebotes_politica=1), {}, 75)[:2], ('bajar', 50))
        self.assertEqual(decidir(dict(LIMPIA, fallos_envio=2), {}, 100)[:2], ('bajar', 75))
        self.assertEqual(decidir(dict(LIMPIA, rebotes=100, entregados=250), {}, 75)[:2], ('bajar', 50))
        self.assertEqual(decidir(dict(LIMPIA, rebotes=100, entregados=250), {}, 50)[:2], ('mantener', 50))
        self.assertEqual(decidir(dict(LIMPIA, rebotes_politica=18), {}, 75)[0], 'parar')
        self.assertEqual(decidir(dict(LIMPIA, fallos_envio=40), {}, 50)[0], 'parar')


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestRecomendacion(TransactionCase):

    def test_sin_envios_mantiene_y_pone_el_techo(self):
        fila = self.env['nv.embudo.recomendacion']._nv_calcular(fields.Datetime.now() - timedelta(days=4000))
        self.assertEqual((fila.recomendacion, fila.escalon_actual, fila.techo), ('mantener', 50, 75))
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param('nv_crm_embudo.reactivacion_por_dia'), '75')
        self.assertEqual(fila.nv_json()['recomendacion'], 'mantener')
        self.assertTrue(fila.nv_json()['calculadoEl'].endswith('Z'))

    def test_el_rebote_guarda_su_motivo(self):
        lead = self.env['crm.lead'].create({'name': 'Rebota', 'type': 'opportunity', 'email_from': 'nadie@example.com'})
        mensaje = self.env['mail.message'].create({'model': 'crm.lead', 'res_id': lead.id, 'message_type': 'email',
                                                   'body': 'Correo 01'})
        import email
        self.env['mail.thread']._routing_handle_bounce(email.message_from_string(GMAIL), {
            'bounced_email': 'nadie@example.com', 'bounced_partner': self.env['res.partner'],
            'bounced_msg_id': [mensaje.message_id], 'bounced_message': mensaje,
            'email_from': 'postmaster@example.com', 'to': 'marketing@nuevavision.es', 'message_id': '<aviso@example.com>'})
        self.assertEqual((lead.nv_rebote_motivo, lead.nv_rebote_codigo), ('inexistente', '5.1.1'))
        self.assertTrue(lead.message_bounce)

    def test_el_rebote_sin_correo_original_tambien_guarda_su_motivo(self):
        # Aviso que no trae el identificador del correo original («no document found»)
        lead = self.env['crm.lead'].create({'name': 'Rebota', 'type': 'opportunity', 'email_from': 'nadie@example.com'})
        otro = self.env['crm.lead'].create({'name': 'No rebota', 'type': 'opportunity', 'email_from': 'alguien@example.com'})
        import email
        self.env['mail.thread']._routing_handle_bounce(email.message_from_string(GMAIL), {
            'bounced_email': 'nadie@example.com', 'bounced_partner': self.env['res.partner'],
            'bounced_msg_id': False, 'bounced_message': self.env['mail.message'],
            'email_from': 'mailer-daemon@example.com', 'to': 'marketing@nuevavision.es', 'message_id': '<aviso2@example.com>'})
        self.assertEqual((lead.nv_rebote_motivo, lead.nv_rebote_codigo, lead.message_bounce), ('inexistente', '5.1.1', 1))
        self.assertFalse(otro.nv_rebote_motivo or otro.message_bounce)


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestRecomendacionHttp(HttpCase):

    def test_solo_con_la_clave(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM_CLAVE, '')
        self.assertEqual(self.url_open('/nv/embudo/recomendacion', headers={'X-NV-Clave': ''}).status_code, 403)
        self.env['ir.config_parameter'].sudo().set_param(PARAM_CLAVE, 'clave-de-prueba')
        self.assertEqual(self.url_open('/nv/embudo/recomendacion').status_code, 403)
        self.assertEqual(self.url_open('/nv/embudo/recomendacion', headers={'X-NV-Clave': 'otra'}).status_code, 403)
        self.env['nv.embudo.recomendacion']._nv_calcular(fields.Datetime.now() - timedelta(days=4000))
        respuesta = self.url_open('/nv/embudo/recomendacion', headers={'X-NV-Clave': 'clave-de-prueba'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['recomendacion'], 'mantener')
        self.assertNotIn('email', respuesta.text.lower())
