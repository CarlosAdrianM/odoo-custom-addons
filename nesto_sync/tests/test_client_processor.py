from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from ..models.client_processor import ClientProcessor
from ..models.client_processor import RequirePrincipalClientError
from ..models.cargos import cargos_funciones

class TestClientProcessor(TransactionCase):

    def setUp(self):
        super(TestClientProcessor, self).setUp()
        self.processor = ClientProcessor(self.env)

    def test_process_client_with_valid_data(self):
        # Datos de prueba
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'ClientePrincipal': True,
            'Nombre': 'John Doe',
            'Direccion': '123 Main St',
            'Telefono': '915551234 / 615555678'
        }

        # Procesar el mensaje
        values = self.processor.process_client(message)

        # Verificar que los valores son correctos
        self.assertEqual(values['parent']['cliente_externo'], '123')
        self.assertEqual(values['parent']['contacto_externo'], '456')
        self.assertEqual(values['parent']['name'], 'John Doe')
        self.assertEqual(values['parent']['street'], '123 Main St')
        self.assertEqual(values['parent']['phone'], '915551234')
        self.assertEqual(values['parent']['mobile'], '615555678')
        self.assertEqual(values['parent']['comment'], None)
        self.assertEqual(values['parent']['parent_id'], None)
        self.assertEqual(values['parent']['company_id'], self.env.user.company_id.id)

    def test_process_client_with_missing_required_fields(self):
        # Datos de prueba con campos obligatorios faltantes
        message = {
            'Nombre': 'John Doe',
            'Direccion': '123 Main St',
            'Telefono': '555-1234 / 555-5678'
        }

        # Verificar que se lanza una excepción
        with self.assertRaises(ValueError) as context:
            self.processor.process_client(message)
        self.assertIn("Faltan datos obligatorios: Cliente o Contacto", str(context.exception))

    def test_process_client_with_cliente_principal(self):
        # Datos de prueba con ClientePrincipal=True
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'Nombre': 'John Doe',
            'Direccion': '123 Main St',
            'Telefono': '555-1234 / 555-5678',
            'ClientePrincipal': True
        }

        # Procesar el mensaje
        values = self.processor.process_client(message)

        # Verificar que parent_id es None cuando ClientePrincipal=True
        self.assertIsNone(values['parent']['parent_id'])

    def test_process_client_with_multiple_phone_numbers(self):
        # Datos de prueba con múltiples números de teléfono
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'ClientePrincipal': True,
            'Nombre': 'John Doe',
            'Direccion': '123 Main St',
            'Telefono': '915551234 / 655567811 / 915559999'
        }

        # Procesar el mensaje
        values = self.processor.process_client(message)

        # Verificar que los números de teléfono se procesan correctamente
        self.assertEqual(values['parent']['phone'], '915551234')
        self.assertEqual(values['parent']['mobile'], '655567811')
        self.assertEqual(values['parent']['comment'], '[Teléfonos extra] 915559999')

    def test_process_client_with_no_phone_numbers(self):
        # Datos de prueba sin números de teléfono
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'ClientePrincipal': True,
            'Nombre': 'John Doe',
            'Direccion': '123 Main St'
        }

        # Procesar el mensaje
        values = self.processor.process_client(message)

        # Verificar que los campos de teléfono son None
        self.assertIsNone(values['parent']['phone'])
        self.assertIsNone(values['parent']['mobile'])
        self.assertIsNone(values['parent']['comment'])
    
    def test_get_or_create_state_existing_state(self):
        """
        Test que verifica que se devuelve el ID de una provincia existente.
        """
        self.processor.country_manager.env = MagicMock()

        # Configurar el mock para simular España
        mock_spain = MagicMock()
        mock_spain.id = 1  # Simular el ID de España
        self.processor.country_manager.env['res.country'].search = MagicMock(return_value=mock_spain)

        # Configurar el mock para simular una provincia existente
        mock_state_madrid = MagicMock()
        mock_state_madrid.id = 2  # Simular el ID de la provincia de Madrid
        mock_state_madrid.name = "Madrid"  # Nombre de la provincia

        self.processor.country_manager.env['res.country.state'].search.return_value = [mock_state_madrid]

        # Llamar al método
        state_id = self.processor.country_manager.get_or_create_state("Madrid")

        # Verificar que se devuelve el ID correcto
        self.assertEqual(state_id, 2)

    def test_get_or_create_state_spain_not_found(self):
        """
        Test que verifica que se lanza una excepción si España no está en la base de datos.
        """
        self.processor.country_manager.env = MagicMock()
    
        # Configurar el mock para simular que España no existe
        self.processor.country_manager.env['res.country'].search.return_value = False

        # Llamar al método y verificar que se lanza una excepción
        with self.assertRaises(ValueError) as context:
            self.processor.country_manager.get_or_create_state("Madrid")
        self.assertIn("El país España no está configurado en la base de datos", str(context.exception))

    def test_process_client_with_is_company_and_type(self):
        """
        Test para verificar que los campos is_company y type se asignan correctamente
        basándose en ClientePrincipal.
        """
        # Caso 1: Cliente Principal (is_company = True, type = 'invoice')
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'ClientePrincipal': True,
            'Nombre': 'EMPRESA TEST, S.L.',
            'Direccion': 'Calle Test 123',
            'Telefono': '915551234'
        }

        values = self.processor.process_client(message)
        
        self.assertTrue(values['parent']['is_company'])
        self.assertEqual(values['parent']['type'], 'invoice')

        # Caso 2: Cliente Secundario (is_company = False, type = 'delivery')
        message['ClientePrincipal'] = False

        with patch('odoo.models.BaseModel.search') as mock_search:
            # Mockeamos el resultado de search para devolver un objeto simulado
            mock_partner = MagicMock()
            mock_partner.id = 999  # Un ID ficticio
            mock_search.return_value = mock_partner

            values = self.processor.process_client(message)

            self.assertFalse(values['parent']['is_company'])
            self.assertEqual(values['parent']['type'], 'delivery')

    def test_process_client_with_single_contact_email(self):
        """
        Test para verificar que cuando hay un solo contacto, el email se asigna
        directamente al registro principal.
        """
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'ClientePrincipal': True,
            'Nombre': 'EMPRESA TEST, S.L.',
            'PersonasContacto': [{
                'Id': '1',
                'Nombre': 'Juan Pérez',
                'CorreoElectronico': 'juan@test.com',
                'Telefonos': None
            }]
        }

        values = self.processor.process_client(message)
        
        self.assertEqual(values['parent']['email'], 'juan@test.com')

    def test_process_client_main_contact(self):
        """
        Test caso 1: Cliente principal (contacto 0)
        Verifica que se crea correctamente sin parent_id
        """
        message = {
            'Cliente': '1',
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'EMPRESA PRINCIPAL',
            'Direccion': 'Calle Roja, 1'
        }

        values = self.processor.process_client(message)
        
        self.assertIsNone(values['parent']['parent_id'])
        self.assertTrue(values['parent']['is_company'])
        self.assertEqual(values['parent']['type'], 'invoice')


    def test_process_client_secondary_with_existing_main(self):
        """
        Test caso 2: Contacto secundario cuando ya existe el principal
        Verifica que se asocia correctamente al parent existente
        """
        # Mock del entorno para simular que existe el cliente principal
        self.processor.env = MagicMock()
        mock_parent = MagicMock()
        mock_parent.id = 1
        self.processor.env['res.partner'].sudo().search.return_value = mock_parent

        message = {
            'Cliente': '1',
            'Contacto': '1',
            'ClientePrincipal': False,
            'Nombre': 'DIRECCIÓN ENTREGA',
            'Direccion': 'Calle Verde, 23'
        }

        values = self.processor.process_client(message)
        
        self.assertEqual(values['parent']['parent_id'], 1)
        self.assertFalse(values['parent']['is_company'])
        self.assertEqual(values['parent']['type'], 'delivery')

    def test_process_client_secondary_without_main(self):
        """
        Test caso 3: Contacto secundario sin existir el principal
        Da error de RequirePrincipalClientError
        """
        # Mock del entorno para simular que NO existe el cliente principal
        self.processor.env = MagicMock()
        self.processor.env['res.partner'].sudo().search.return_value = False

        message = {
            'Cliente': '1',
            'Contacto': '1',
            'ClientePrincipal': False,
            'Nombre': 'DIRECCIÓN ENTREGA',
            'Direccion': 'Calle Verde, 23'
        }
        
        with self.assertRaises(RequirePrincipalClientError) as context:
            self.processor.process_client(message)

    def test_process_client_with_multiple_contacts(self):
        """
        Test para verificar que se crean tres contactos correctamente:
        1. Contacto principal.
        2. Contacto asociado con persona_contacto_externa = 1 (cargo 22).
        3. Contacto asociado con persona_contacto_externa = 2.
        """
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'ClientePrincipal': True,
            'Nombre': 'EMPRESA TEST, S.L.',
            'PersonasContacto': [
                {
                    'Id': '1',
                    'Nombre': 'Juan Pérez',
                    'CorreoElectronico': 'juan@test.com',
                    'Telefono': '623456789',
                    'Cargo': 22
                },
                {
                    'Id': '2',
                    'Nombre': 'Ana López',
                    'CorreoElectronico': 'ana@test.com',
                    'Telefono': '987654321'
                }
            ]
        }

        values = self.processor.process_client(message)

        # Verificar que se crea el contacto principal
        self.assertIn('parent', values)
        self.assertIn('children', values)

        contacto_principal = values['parent']
        children = values['children']

        self.assertEqual(contacto_principal['cliente_externo'], '123')
        self.assertEqual(contacto_principal['contacto_externo'], '456')
        self.assertIsNone(contacto_principal.get('parent_id'))

        # Asegurar que hay exactamente 2 contactos en 'children'
        self.assertEqual(len(children), 2)

        # Tomar el primer contacto y asegurarnos de que su email se asigna a `parent`
        primer_contacto_email = children[0]['email']
        self.assertEqual(contacto_principal['email'], primer_contacto_email)

        # Verificar el contacto con persona_contacto_externa = '1' (Juan Pérez)
        contacto_1 = next(c for c in children if c['persona_contacto_externa'] == '1')
        self.assertEqual(contacto_1['email'], 'juan@test.com')
        self.assertEqual(contacto_1['type'], 'contact')
        self.assertEqual(contacto_1['function'], cargos_funciones.get(22))
        self.assertEqual(contacto_1['name'], 'Juan Pérez')
        self.assertEqual(contacto_1['mobile'], '623456789')

        # Verificar el contacto con persona_contacto_externa = '2' (Ana López)
        contacto_2 = next(c for c in children if c['persona_contacto_externa'] == '2')
        self.assertEqual(contacto_2['email'], 'ana@test.com')
        self.assertEqual(contacto_2['type'], 'contact')
        self.assertEqual(contacto_2['name'], 'Ana López')
        self.assertEqual(contacto_2['phone'], '987654321')

    def test_process_client_with_estado(self):
        """
        Test para verificar que el campo 'active' se establece correctamente
        basándose en el valor del campo 'estado' del JSON de entrada.
        """
        # Caso 1: estado >= 0, active debe ser True
        message = {
            'Cliente': '123',
            'Contacto': '456',
            'ClientePrincipal': True,
            'Nombre': 'John Doe',
            'Direccion': '123 Main St',
            'Telefono': '915551234',
            'Estado': 1  # Estado positivo
        }

        values = self.processor.process_client(message)
        self.assertTrue(values['parent']['active'])

        # Caso 2: estado < 0, active debe ser False
        message['Estado'] = -1  # Estado negativo

        values = self.processor.process_client(message)
        self.assertFalse(values['parent']['active'])

if __name__ == '__main__':
    unittest.main()