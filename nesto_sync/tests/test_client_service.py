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

    def test_reactivate_inactive_partner(self):
        # Crear un contacto inicialmente activo
        self.service._create_partner(self.test_data)
        
        # Buscar el contacto creado
        partner = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('contacto_externo', '=', 'CONTACT001')
        ], limit=1)
        
        # Verificar que el contacto se creó correctamente
        self.assertTrue(partner, "El contacto no se creó correctamente")
        original_id = partner.id  # Guardar el ID original del contacto
        
        # Desactivar el contacto
        partner.write({'active': False})
        
        # Verificar que el contacto está inactivo
        self.assertFalse(partner.active, "El contacto no se desactivó correctamente")
        
        # Intentar reactivar el contacto
        reactivate_data = {
            "cliente_externo": "TEST001",
            "contacto_externo": "CONTACT001",
            "name": "Test Cliente",  # Asegurarse de incluir el campo "name"
            "active": True
        }
        result = self.service._create_or_update_single_contact(reactivate_data)
        
        # Buscar el contacto nuevamente
        partner = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('contacto_externo', '=', 'CONTACT001')
        ], limit=1)
        
        # Verificar que el contacto se reactivó correctamente
        self.assertTrue(partner, "El contacto no se encontró después de reactivar")
        self.assertTrue(partner.active, "El contacto no se reactivó correctamente")
        
        # Verificar que no se creó un nuevo contacto
        self.assertEqual(partner.id, original_id, "Se creó un nuevo contacto en lugar de reactivar el existente")
        
        # Verificar que solo existe un contacto con estos datos
        partners = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('contacto_externo', '=', 'CONTACT001')
        ])
        self.assertEqual(len(partners), 1, "Se creó un nuevo contacto en lugar de reactivar el existente")