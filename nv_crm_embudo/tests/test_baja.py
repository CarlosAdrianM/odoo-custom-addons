from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'nv_crm_embudo')
class TestBaja(TransactionCase):

    def test_token_depende_del_lead_y_del_email(self):
        l1 = self.env['crm.lead'].create({'name': 'a', 'email_from': 'a@ejemplo.test'})
        l2 = self.env['crm.lead'].create({'name': 'b', 'email_from': 'a@ejemplo.test'})
        self.assertNotEqual(l1._nv_baja_token(), l2._nv_baja_token())
        token = l1._nv_baja_token()
        l1.email_from = 'otro@ejemplo.test'
        self.assertNotEqual(l1._nv_baja_token(), token, 'Si cambia el email, el enlace anterior deja de valer')
        self.assertIn('/nv/baja/%s/' % l1.id, l1.nv_url_baja())
