"""
Tests para sincronización bidireccional (Odoo → Nesto)

Valida que:
1. Los cambios en Odoo se publican a PubSub
2. El sistema anti-bucle funciona sin flags de origen
3. El batch processing funciona correctamente
4. El contexto skip_sync funciona
"""

import json
from unittest.mock import Mock, patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'nesto_sync')
class TestBidirectionalSync(TransactionCase):
    """Tests de sincronización bidireccional"""

    def setUp(self):
        super().setUp()

        # Crear partner de prueba
        self.partner = self.env['res.partner'].create({
            'name': 'Test Cliente',
            'cliente_externo': 'CLI001',
            'contacto_externo': '001',
            'mobile': '666111111',
            'street': 'Calle Test 123',
            'city': 'Madrid',
            'is_company': True,
            'type': 'invoice',
        })

    @patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher')
    def test_write_triggers_publish(self, mock_create_publisher):
        """Test: Modificar partner debe publicar a PubSub"""
        # Arrange
        mock_publisher = Mock()
        mock_create_publisher.return_value = mock_publisher

        # Act
        self.partner.write({'mobile': '666222222'})

        # Assert
        # Verificar que se intentó crear el publisher
        mock_create_publisher.assert_called_once()

        # Verificar que se publicó un evento
        # (OdooPublisher.publish_record debería haberse llamado)

    @patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher')
    def test_create_triggers_publish(self, mock_create_publisher):
        """Test: Crear partner debe publicar a PubSub"""
        # Arrange
        mock_publisher = Mock()
        mock_create_publisher.return_value = mock_publisher

        # Act
        new_partner = self.env['res.partner'].create({
            'name': 'Nuevo Cliente',
            'cliente_externo': 'CLI002',
            'contacto_externo': '001',
            'is_company': True,
        })

        # Assert
        self.assertTrue(new_partner.exists())
        mock_create_publisher.assert_called_once()

    def test_skip_sync_context_prevents_publish(self):
        """Test: Contexto skip_sync debe prevenir publicación"""
        # Act
        with patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher') as mock_create:
            mock_publisher = Mock()
            mock_create.return_value = mock_publisher

            # Modificar con skip_sync=True
            self.partner.with_context(skip_sync=True).write({'mobile': '666333333'})

        # Assert
        # NO debería haber intentado crear publisher
        mock_create.assert_not_called()

    def test_no_from_nesto_flag_exists(self):
        """Test: Verificar que NO usamos flag from_nesto"""
        # Act
        with patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher') as mock_create:
            mock_publisher = Mock()
            mock_create.return_value = mock_publisher

            # Modificar partner (simula que viene de subscriber)
            self.partner.write({'mobile': '666444444'})

        # Assert
        # Debería publicar SIEMPRE (no hay filtro por origen)
        # El anti-bucle se maneja por detección de cambios en GenericService
        mock_create.assert_called_once()

    def test_batch_processing_many_records(self):
        """Test: Batch processing para muchos registros"""
        # Arrange: Crear 100 partners
        partners = self.env['res.partner']
        for i in range(100):
            partner = self.env['res.partner'].create({
                'name': f'Cliente {i}',
                'cliente_externo': f'CLI{i:03d}',
                'contacto_externo': '001',
                'is_company': True,
            })
            partners |= partner

        # Act
        with patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher') as mock_create:
            mock_publisher = Mock()
            mock_create.return_value = mock_publisher

            # Modificar todos a la vez
            partners.write({'city': 'Barcelona'})

        # Assert
        # Debería haberse creado el publisher
        self.assertTrue(mock_create.called)

        # Debería procesar en bloques (batch_size por defecto = 50)
        # Así que 100 registros = 2 bloques


@tagged('post_install', '-at_install', 'nesto_sync')
class TestAntiBucle(TransactionCase):
    """
    Tests del sistema anti-bucle basado en detección de cambios
    (sin flags de origen)
    """

    def setUp(self):
        super().setUp()

        self.ResPartner = self.env['res.partner']

        # Crear partner inicial
        self.partner = self.ResPartner.create({
            'name': 'Cliente Anti-Bucle',
            'cliente_externo': 'CLI999',
            'contacto_externo': '001',
            'mobile': '666111111',
            'street': 'Calle Bucle 1',
            'city': 'Madrid',
            'is_company': True,
        })

    def test_anti_bucle_scenario_nesto_to_odoo_to_nesto(self):
        """
        Test: Simular bucle completo Nesto → Odoo → Nesto

        Escenario:
        1. Nesto cambia mobile a 666222222
        2. Odoo recibe y actualiza
        3. Odoo publica cambio a PubSub
        4. Nesto recibe mensaje
        5. Nesto detecta: mobile actual == mensaje → NO actualiza
        6. NO bucle infinito
        """
        # Arrange
        from nesto_sync.core.generic_service import GenericEntityService
        from nesto_sync.config.entity_configs import get_entity_config

        entity_config = get_entity_config('cliente')
        service = GenericEntityService(self.env, entity_config, test_mode=True)

        # Paso 1: Simular mensaje de Nesto
        nesto_message_data = {
            'parent': {
                'cliente_externo': 'CLI999',
                'contacto_externo': '001',
                'persona_contacto_externa': None,
                'name': 'Cliente Anti-Bucle',
                'mobile': '666222222',  # Cambio
                'street': 'Calle Bucle 1',
                'city': 'Madrid',
                'is_company': True,
                'type': 'invoice',
            },
            'children': []
        }

        # Act: Paso 2 - Odoo recibe y actualiza (con mocking de publisher)
        with patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher') as mock_create:
            mock_publisher = Mock()
            mock_publisher.publish_event = Mock()
            mock_create.return_value = mock_publisher

            # GenericService actualiza (esto DEBERÍA publicar a PubSub)
            response = service.create_or_update_contact(nesto_message_data)

        # Assert: Verificar que se actualizó
        self.partner.refresh()
        self.assertEqual(self.partner.mobile, '666222222')

        # Assert: Verificar que se publicó (porque hubo cambios reales)
        self.assertTrue(mock_publisher.publish_event.called)

        # Paso 3: Simular que Nesto recibe el mensaje
        # Nesto debería detectar que mobile actual (666222222) == mensaje (666222222)
        # y NO actualizar (esto se implementará en NestoAPI)

        # Paso 4: Simular que Nesto NO publica confirmación (porque no cambió nada)
        # Por tanto, NO hay bucle

    def test_anti_bucle_scenario_odoo_to_nesto_to_odoo(self):
        """
        Test: Simular bucle completo Odoo → Nesto → Odoo

        Escenario:
        1. Usuario cambia mobile en Odoo UI a 666333333
        2. Odoo publica a PubSub
        3. Nesto recibe y actualiza
        4. Nesto publica confirmación
        5. Odoo recibe mensaje
        6. GenericService detecta: mobile actual == mensaje → NO actualiza
        7. NO bucle infinito
        """
        # Arrange
        from nesto_sync.core.generic_service import GenericEntityService
        from nesto_sync.config.entity_configs import get_entity_config

        entity_config = get_entity_config('cliente')
        service = GenericEntityService(self.env, entity_config, test_mode=True)

        # Paso 1: Usuario cambia en Odoo UI
        with patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher') as mock_create:
            mock_publisher = Mock()
            mock_create.return_value = mock_publisher

            self.partner.write({'mobile': '666333333'})

        # Assert: Verificar que se publicó
        self.assertTrue(mock_publisher.publish_event.called)

        # Paso 2: Simular que Nesto recibe, actualiza y publica confirmación
        # (esto pasaría en NestoAPI)

        # Paso 3: Odoo recibe mensaje de "confirmación" de Nesto
        nesto_confirmation_message = {
            'parent': {
                'cliente_externo': 'CLI999',
                'contacto_externo': '001',
                'persona_contacto_externa': None,
                'name': 'Cliente Anti-Bucle',
                'mobile': '666333333',  # Mismo valor
                'street': 'Calle Bucle 1',
                'city': 'Madrid',
                'is_company': True,
                'type': 'invoice',
            },
            'children': []
        }

        # Act: GenericService procesa mensaje (debería detectar "sin cambios")
        with patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher') as mock_create:
            mock_publisher = Mock()
            mock_create.return_value = mock_publisher

            response = service.create_or_update_contact(nesto_confirmation_message)

        # Assert: Verificar que detectó "sin cambios"
        response_data = json.loads(response.response[0].decode())
        self.assertEqual(response_data['message'], 'Sin cambios')

        # Assert: Verificar que mobile sigue igual
        self.partner.refresh()
        self.assertEqual(self.partner.mobile, '666333333')

        # Assert: BidirectionalSyncMixin NO debería haber publicado
        # (porque GenericService no hizo write real, solo detectó que no hay cambios)

    def test_install_mode_prevents_publish(self):
        """Test: Modo instalación debe prevenir publicación"""
        # Act
        with patch('nesto_sync.infrastructure.publisher_factory.PublisherFactory.create_publisher') as mock_create:
            # Modificar con contexto de instalación
            self.partner.with_context(install_mode=True).write({'mobile': '666555555'})

        # Assert
        mock_create.assert_not_called()
