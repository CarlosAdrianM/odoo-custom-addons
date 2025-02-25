from odoo.tests import TransactionCase, tagged
from ..models.client_service import ClientService

@tagged('post_install', '-at_install', 'nesto_sync')
class TestClientService(TransactionCase):
    def setUp(self):
        super().setUp()
        self.service = ClientService(self.env, test_mode=True)
        self.test_data = {
            "cliente_externo": "TEST001",
            "contacto_externo": "CONTACT001",
            "name": "Test Cliente",
            "street": "Calle Test 123",
            "phone": "912345678",
            "mobile": "666777888",
            "comment": "699888777"
        }

    def test_create_partner(self):
        result = self.service._create_partner(self.test_data)
        self.assertTrue(result)
        
        partner = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('contacto_externo', '=', 'CONTACT001')
        ])
        self.assertTrue(partner)

    def test_update_client(self):
        self.service._create_partner(self.test_data)
        
        partner = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('contacto_externo', '=', 'CONTACT001')
        ], limit=1)  # Asegurarse de obtener un solo registro
        
        self.assertTrue(partner, "El cliente no se creó correctamente")

        updated_data = {"name": "Updated Name"}
        result = self.service._update_partner(partner, updated_data)

        partner.invalidate_model()  # Asegurarse de obtener los últimos cambios de la BD
        self.assertEqual(partner.name, "Updated Name")
