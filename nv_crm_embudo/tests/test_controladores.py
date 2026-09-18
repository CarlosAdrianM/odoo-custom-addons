"""Tests de las rutas públicas: baja del embudo y webhook de bajas de Mailchimp.

Van sin autenticación y de cara a internet, así que conviene tenerlas cubiertas.
"""
from odoo.tests import tagged
from odoo.tests.common import HttpCase

PARAM_SECRETO = 'nv_crm_embudo.mailchimp_secreto'


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestBajaHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.lead = self.env['crm.lead'].create({
            'name': 'Lead baja', 'type': 'opportunity', 'email_from': 'baja@ejemplo.test'})
        self.url = '/nv/baja/%s/%s' % (self.lead.id, self.lead._nv_baja_token())

    def _en_lista_negra(self, email):
        return bool(self.env['mail.blacklist'].sudo().search([('email', '=', email), ('active', '=', True)]))

    def test_get_solo_pide_confirmacion(self):
        respuesta = self.url_open(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Confirmar la baja', respuesta.text)
        self.assertFalse(self._en_lista_negra('baja@ejemplo.test'),
                         'Los antivirus de correo abren los enlaces: un GET no da de baja a nadie')

    def test_token_invalido_da_404(self):
        respuesta = self.url_open('/nv/baja/%s/token_falso' % self.lead.id)
        self.assertEqual(respuesta.status_code, 404)

    def test_lead_inexistente_da_404(self):
        respuesta = self.url_open('/nv/baja/999999999/token_falso')
        self.assertEqual(respuesta.status_code, 404)

    def test_post_da_de_baja_y_deja_nota(self):
        respuesta = self.url_open(self.url, data={'confirmar': '1'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Baja confirmada', respuesta.text)
        self.assertTrue(self._en_lista_negra('baja@ejemplo.test'))
        self.assertTrue(self.lead.message_ids.filtered(lambda m: 'baja' in (m.body or '')))

    def test_el_token_de_un_lead_no_vale_para_otro(self):
        otro = self.env['crm.lead'].create({
            'name': 'Otro', 'type': 'opportunity', 'email_from': 'baja@ejemplo.test'})
        respuesta = self.url_open('/nv/baja/%s/%s' % (otro.id, self.lead._nv_baja_token()), data={'confirmar': '1'})
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(self._en_lista_negra('baja@ejemplo.test'))


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestMailchimpHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(PARAM_SECRETO, 'secreto-de-prueba')

    def _en_lista_negra(self, email):
        return bool(self.env['mail.blacklist'].sudo().search([('email', '=', email), ('active', '=', True)]))

    def test_get_de_validacion(self):
        self.assertEqual(self.url_open('/nv/mailchimp/secreto-de-prueba').status_code, 200)

    def test_secreto_incorrecto_da_404(self):
        self.assertEqual(self.url_open('/nv/mailchimp/otro-secreto').status_code, 404)

    def test_sin_secreto_configurado_da_404(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM_SECRETO, '')
        self.assertEqual(self.url_open('/nv/mailchimp/secreto-de-prueba').status_code, 404)

    def test_unsubscribe_mete_en_la_lista_negra(self):
        respuesta = self.url_open('/nv/mailchimp/secreto-de-prueba', data={
            'type': 'unsubscribe', 'data[email]': 'fuera@ejemplo.test', 'data[list_id]': 'abc'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(self._en_lista_negra('fuera@ejemplo.test'))

    def test_otros_eventos_se_ignoran(self):
        respuesta = self.url_open('/nv/mailchimp/secreto-de-prueba', data={
            'type': 'profile', 'data[email]': 'dentro@ejemplo.test'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self._en_lista_negra('dentro@ejemplo.test'))
