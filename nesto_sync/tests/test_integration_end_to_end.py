"""
Test de Integración End-to-End

Valida el flujo completo: mensaje de Nesto → nueva arquitectura → BD Odoo
Compara con código legacy para verificar mismo comportamiento
"""

import json
import base64
from odoo.tests.common import TransactionCase
from ..models.google_pubsub_message_adapter import GooglePubSubMessageAdapter
from ..core.entity_registry import EntityRegistry

# Importar legacy desde el path correcto
import sys
import os
legacy_path = os.path.join(os.path.dirname(__file__), '..', 'legacy')
if legacy_path not in sys.path:
    sys.path.insert(0, legacy_path)

try:
    from client_processor import ClientProcessor as LegacyProcessor
    from client_service import ClientService as LegacyService
    LEGACY_AVAILABLE = True
except ImportError:
    LEGACY_AVAILABLE = False


class TestEndToEndIntegration(TransactionCase):
    """Test de integración completo del flujo de sincronización"""

    def setUp(self):
        super().setUp()

        # Mensaje real completo de Nesto (basado en estructura actual)
        self.nesto_message = {
            "Cliente": "TEST001",
            "Contacto": "1",
            "ClientePrincipal": True,
            "Nombre": "Empresa Test S.L.",
            "Direccion": "Calle Principal 123",
            "Telefono": "666123456/912345678/666999888",
            "Nif": "B12345678",
            "CodigoPostal": "28001",
            "Poblacion": "Madrid",
            "Provincia": "Madrid",
            "Comentarios": "Cliente importante para testing",
            "Estado": 1,
            "PersonasContacto": [
                {
                    "Id": "1",
                    "Nombre": "Juan Pérez",
                    "Telefono": "666111222",
                    "CorreoElectronico": "juan@empresatest.com",
                    "Cargo": 5,  # Gerente
                    "Comentarios": "Contacto principal"
                },
                {
                    "Id": "2",
                    "Nombre": "María García",
                    "Telefono": "666333444",
                    "CorreoElectronico": "maria@empresatest.com",
                    "Cargo": 8,  # Administración
                    "Comentarios": "Contacto secundario"
                }
            ]
        }

        # Nueva arquitectura
        self.registry = EntityRegistry()

        # Legacy (para comparar) - solo si está disponible
        if LEGACY_AVAILABLE:
            self.legacy_processor = LegacyProcessor(self.env)
            self.legacy_service = LegacyService(self.env, test_mode=True)
        else:
            self.legacy_processor = None
            self.legacy_service = None

    def test_full_flow_new_architecture(self):
        """Test: Flujo completo con nueva arquitectura"""

        # 1. Procesar con nueva arquitectura
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        processed_data = processor.process(self.nesto_message)

        # Verificar estructura procesada
        self.assertIn('parent', processed_data)
        self.assertIn('children', processed_data)

        parent = processed_data['parent']
        children = processed_data['children']

        # 2. Verificar parent
        self.assertEqual(parent['name'], 'Empresa Test S.L.')
        self.assertEqual(parent['cliente_externo'], 'TEST001')
        self.assertEqual(parent['contacto_externo'], '1')
        self.assertEqual(parent['vat'], 'B12345678')
        self.assertEqual(parent['zip'], '28001')
        self.assertEqual(parent['city'], 'Madrid')
        self.assertTrue(parent['is_company'])
        self.assertEqual(parent['type'], 'invoice')
        self.assertTrue(parent['active'])

        # Verificar teléfonos
        self.assertEqual(parent['mobile'], '666123456')
        self.assertEqual(parent['phone'], '912345678')

        # Verificar email (debe venir del primer contacto)
        self.assertEqual(parent['email'], 'juan@empresatest.com')

        # Verificar comentarios (incluye teléfonos extra)
        self.assertIn('666999888', parent['comment'])
        self.assertIn('Cliente importante', parent['comment'])

        # 3. Verificar children
        self.assertEqual(len(children), 2)

        child1 = children[0]
        self.assertEqual(child1['name'], 'Juan Pérez')
        self.assertEqual(child1['email'], 'juan@empresatest.com')
        self.assertEqual(child1['mobile'], '666111222')
        self.assertEqual(child1['function'], 'Gerente')
        self.assertEqual(child1['type'], 'contact')
        self.assertEqual(child1['persona_contacto_externa'], '1')

        child2 = children[1]
        self.assertEqual(child2['name'], 'María García')
        self.assertEqual(child2['email'], 'maria@empresatest.com')
        self.assertEqual(child2['mobile'], '666333444')
        self.assertEqual(child2['function'], 'Administración')

        # 4. Crear en BD
        response = service.create_or_update_contact(processed_data)
        self.assertEqual(response.status_code, 200)

        # 5. Verificar en BD
        partner = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('parent_id', '=', False)
        ])

        self.assertTrue(partner)
        self.assertEqual(partner.name, 'Empresa Test S.L.')
        self.assertEqual(partner.email, 'juan@empresatest.com')

        # Verificar hijos en BD
        children_records = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('parent_id', '=', partner.id)
        ])

        self.assertEqual(len(children_records), 2)

    def test_compare_new_vs_legacy(self):
        """Test: Comparar resultado nueva arquitectura vs legacy"""

        if not LEGACY_AVAILABLE:
            self.skipTest("Legacy code not available for comparison")

        # Procesar con nueva arquitectura
        new_processor = self.registry.get_processor('cliente', self.env)
        new_data = new_processor.process(self.nesto_message)

        # Procesar con legacy
        legacy_data = self.legacy_processor.process_client(self.nesto_message)

        # Comparar parent
        new_parent = new_data['parent']
        legacy_parent = legacy_data['parent']

        # Campos críticos deben ser iguales
        self.assertEqual(new_parent['name'], legacy_parent['name'])
        self.assertEqual(new_parent['cliente_externo'], legacy_parent['cliente_externo'])
        self.assertEqual(new_parent['vat'], legacy_parent['vat'])
        self.assertEqual(new_parent['mobile'], legacy_parent['mobile'])
        self.assertEqual(new_parent['phone'], legacy_parent['phone'])
        self.assertEqual(new_parent['email'], legacy_parent['email'])
        self.assertEqual(new_parent['is_company'], legacy_parent['is_company'])
        self.assertEqual(new_parent['type'], legacy_parent['type'])
        self.assertEqual(new_parent['active'], legacy_parent['active'])

        # Comparar children
        new_children = new_data['children']
        legacy_children = legacy_data['children']

        self.assertEqual(len(new_children), len(legacy_children))

        for i in range(len(new_children)):
            self.assertEqual(new_children[i]['name'], legacy_children[i]['name'])
            self.assertEqual(new_children[i]['email'], legacy_children[i]['email'])
            self.assertEqual(new_children[i]['function'], legacy_children[i]['function'])

    def test_pubsub_message_format(self):
        """Test: Decodificar mensaje PubSub real"""

        # Simular mensaje PubSub (base64 encoded)
        message_json = json.dumps(self.nesto_message)
        encoded_data = base64.b64encode(message_json.encode('utf-8')).decode('utf-8')

        pubsub_message = {
            "message": {
                "data": encoded_data,
                "messageId": "12345",
                "publishTime": "2025-11-07T10:00:00.000Z"
            }
        }

        # Decodificar
        adapter = GooglePubSubMessageAdapter()
        decoded = adapter.decode_message(json.dumps(pubsub_message))

        # Verificar que se decodificó correctamente
        self.assertEqual(decoded['Cliente'], 'TEST001')
        self.assertEqual(decoded['Nombre'], 'Empresa Test S.L.')

        # Procesar con nueva arquitectura
        processor = self.registry.get_processor('cliente', self.env)
        processed = processor.process(decoded)

        self.assertEqual(processed['parent']['name'], 'Empresa Test S.L.')

    def test_update_existing_cliente(self):
        """Test: Actualizar cliente existente (sin cambios = no actualizar)"""

        # 1. Crear cliente inicial
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        processed_data = processor.process(self.nesto_message)
        response = service.create_or_update_contact(processed_data)

        self.assertEqual(response.status_code, 200)

        # 2. Enviar mismo mensaje otra vez (simula bucle)
        processed_data_2 = processor.process(self.nesto_message)
        response_2 = service.create_or_update_contact(processed_data_2)

        # Debe retornar 200 pero sin actualizar (anti-bucle)
        self.assertEqual(response_2.status_code, 200)
        response_text = response_2.response[0].decode()
        self.assertIn('Sin cambios', response_text)

    def test_update_with_changes(self):
        """Test: Actualizar cliente con cambios reales"""

        # 1. Crear cliente inicial
        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        processed_data = processor.process(self.nesto_message)
        service.create_or_update_contact(processed_data)

        # 2. Modificar mensaje
        modified_message = self.nesto_message.copy()
        modified_message['Nombre'] = 'Empresa Test MODIFICADA S.L.'
        modified_message['Telefono'] = '666999999'  # Cambiar teléfono

        # 3. Procesar mensaje modificado
        processed_data_2 = processor.process(modified_message)
        response = service.create_or_update_contact(processed_data_2)

        # Debe actualizar
        self.assertEqual(response.status_code, 200)

        # Verificar que se actualizó
        partner = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST001'),
            ('parent_id', '=', False)
        ])

        self.assertEqual(partner.name, 'Empresa Test MODIFICADA S.L.')
        self.assertEqual(partner.mobile, '666999999')

    def test_inactive_cliente(self):
        """Test: Cliente con Estado negativo = active False"""

        # Mensaje con estado negativo
        inactive_message = self.nesto_message.copy()
        inactive_message['Estado'] = -1
        inactive_message['Cliente'] = 'TEST_INACTIVE'

        processor = self.registry.get_processor('cliente', self.env)
        service = self.registry.get_service('cliente', self.env, test_mode=True)

        processed_data = processor.process(inactive_message)

        # Verificar que active = False
        self.assertFalse(processed_data['parent']['active'])

        # Crear en BD
        service.create_or_update_contact(processed_data)

        # Verificar en BD (debe encontrarlo aunque esté inactivo)
        partner = self.env['res.partner'].search([
            ('cliente_externo', '=', 'TEST_INACTIVE'),
            ('active', '=', False)
        ])

        self.assertTrue(partner)
        self.assertFalse(partner.active)
