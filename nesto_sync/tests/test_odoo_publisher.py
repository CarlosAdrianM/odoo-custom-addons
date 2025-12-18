"""
Tests para OdooPublisher - Publicación de cambios Odoo → Nesto

Incluye:
1. Tests de VendedorEmail (vacío y con valor)
2. Tests de construcción de mensajes
"""

import json
from unittest.mock import Mock, patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.addons.nesto_sync.core.odoo_publisher import OdooPublisher


@tagged('post_install', '-at_install', 'nesto_sync')
class TestOdooPublisherVendedor(TransactionCase):
    """Tests específicos para publicación de VendedorEmail"""

    def setUp(self):
        super().setUp()
        # Configurar parámetros necesarios para el publisher
        self.env['ir.config_parameter'].sudo().set_param(
            'nesto_sync.google_project_id', 'test-project'
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'nesto_sync.pubsub_provider', 'google_pubsub'
        )

        # Crear vendedor de prueba
        self.vendedor = self.env['res.users'].sudo().create({
            'name': 'Carlos Vendedor',
            'login': 'carlos@nuevavision.es',
            'email': 'carlos@nuevavision.es',
        })

        # Crear cliente con vendedor asignado
        self.partner_con_vendedor = self.env['res.partner'].create({
            'name': 'Cliente Con Vendedor',
            'cliente_externo': 'CLI_VEND_001',
            'contacto_externo': '001',
            'is_company': True,
            'type': 'invoice',
            'user_id': self.vendedor.id,
        })

        # Crear cliente sin vendedor
        self.partner_sin_vendedor = self.env['res.partner'].create({
            'name': 'Cliente Sin Vendedor',
            'cliente_externo': 'CLI_VEND_002',
            'contacto_externo': '001',
            'is_company': True,
            'type': 'invoice',
            'user_id': False,
        })

    def test_mensaje_incluye_vendedor_email_con_valor(self):
        """Test: Mensaje publicado incluye VendedorEmail cuando hay vendedor"""
        publisher = OdooPublisher('cliente', self.env)
        message = publisher._build_message_from_odoo(self.partner_con_vendedor)

        # Debe incluir VendedorEmail con el email del vendedor
        self.assertIn('VendedorEmail', message)
        self.assertEqual(message['VendedorEmail'], 'carlos@nuevavision.es')

    def test_mensaje_incluye_vendedor_email_vacio_cuando_no_hay_vendedor(self):
        """Test: Mensaje publicado incluye VendedorEmail='' cuando NO hay vendedor

        CRÍTICO: VendedorEmail DEBE incluirse aunque esté vacío para que
        Nesto sepa que debe asignar el vendedor 'NV' (sin vendedor).

        Si VendedorEmail no se incluye en el mensaje, Nesto interpreta
        que no debe modificar el vendedor actual.
        """
        publisher = OdooPublisher('cliente', self.env)
        message = publisher._build_message_from_odoo(self.partner_sin_vendedor)

        # DEBE incluir VendedorEmail aunque esté vacío
        self.assertIn('VendedorEmail', message,
                      "VendedorEmail DEBE estar en el mensaje aunque esté vacío")
        self.assertEqual(message['VendedorEmail'], '',
                         "VendedorEmail debe ser string vacío cuando no hay vendedor")

    def test_quitar_vendedor_publica_vendedor_email_vacio(self):
        """Test: Al quitar vendedor de un cliente, se publica VendedorEmail=''

        Escenario real que causó el bug:
        1. Cliente tiene vendedor CAM en Nesto y Odoo
        2. Usuario quita vendedor en Odoo (user_id = False)
        3. Odoo debe publicar mensaje con VendedorEmail=''
        4. Nesto debe recibir VendedorEmail='' y asignar vendedor 'NV'
        """
        # Verificar estado inicial
        self.assertEqual(self.partner_con_vendedor.user_id.id, self.vendedor.id)

        # Quitar vendedor
        self.partner_con_vendedor.with_context(skip_sync=True).write({'user_id': False})
        self.partner_con_vendedor.refresh()

        # Verificar que se quitó
        self.assertFalse(self.partner_con_vendedor.user_id)

        # Construir mensaje
        publisher = OdooPublisher('cliente', self.env)
        message = publisher._build_message_from_odoo(self.partner_con_vendedor)

        # DEBE incluir VendedorEmail vacío
        self.assertIn('VendedorEmail', message)
        self.assertEqual(message['VendedorEmail'], '')

    def test_cambiar_vendedor_publica_nuevo_email(self):
        """Test: Al cambiar vendedor, se publica el nuevo VendedorEmail"""
        # Crear nuevo vendedor
        nuevo_vendedor = self.env['res.users'].sudo().create({
            'name': 'Nuevo Vendedor',
            'login': 'nuevo@nuevavision.es',
            'email': 'nuevo@nuevavision.es',
        })

        # Cambiar vendedor
        self.partner_con_vendedor.with_context(skip_sync=True).write({
            'user_id': nuevo_vendedor.id
        })
        self.partner_con_vendedor.refresh()

        # Construir mensaje
        publisher = OdooPublisher('cliente', self.env)
        message = publisher._build_message_from_odoo(self.partner_con_vendedor)

        # Debe tener el nuevo email
        self.assertEqual(message['VendedorEmail'], 'nuevo@nuevavision.es')

    def test_reverse_transformer_vendedor_con_usuario(self):
        """Test: Reverse transformer devuelve dict con VendedorEmail"""
        publisher = OdooPublisher('cliente', self.env)

        # Simular registro con user_id
        mock_record = Mock()
        mock_user = Mock()
        mock_user.login = 'test@example.com'
        mock_user.email = 'test@example.com'
        mock_record.user_id = mock_user

        result = publisher._apply_reverse_transformer(
            'vendedor', mock_user, mock_record, {}
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result['VendedorEmail'], 'test@example.com')

    def test_reverse_transformer_vendedor_sin_usuario(self):
        """Test: Reverse transformer devuelve VendedorEmail='' cuando no hay usuario"""
        publisher = OdooPublisher('cliente', self.env)

        # Simular registro sin user_id
        mock_record = Mock()
        mock_record.user_id = None

        result = publisher._apply_reverse_transformer(
            'vendedor', None, mock_record, {}
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result['VendedorEmail'], '')

    def test_reverse_transformer_vendedor_user_false(self):
        """Test: Reverse transformer con user_id=False devuelve VendedorEmail=''"""
        publisher = OdooPublisher('cliente', self.env)

        # Simular registro con user_id=False (caso común en Odoo)
        mock_record = Mock()
        mock_record.user_id = False

        result = publisher._apply_reverse_transformer(
            'vendedor', False, mock_record, {}
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result['VendedorEmail'], '')


@tagged('post_install', '-at_install', 'nesto_sync')
class TestOdooPublisherMensajeCompleto(TransactionCase):
    """Tests para construcción de mensajes completos"""

    def setUp(self):
        super().setUp()
        # Configurar parámetros necesarios para el publisher
        self.env['ir.config_parameter'].sudo().set_param(
            'nesto_sync.google_project_id', 'test-project'
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'nesto_sync.pubsub_provider', 'google_pubsub'
        )

        # Cliente con todos los datos
        self.partner = self.env['res.partner'].create({
            'name': 'Empresa Completa S.L.',
            'cliente_externo': 'CLI_COMP_001',
            'contacto_externo': '001',
            'is_company': True,
            'type': 'invoice',
            'vat': 'B12345678',
            'street': 'Calle Test 123',
            'city': 'Madrid',
            'zip': '28001',
            'mobile': '666111222',
            'phone': '912345678',
        })

    def test_mensaje_contiene_campos_obligatorios(self):
        """Test: Mensaje contiene identificadores y metadatos"""
        publisher = OdooPublisher('cliente', self.env)

        with patch.object(publisher, 'publisher') as mock_pub:
            publisher.publish_record(self.partner)

            # Verificar que se llamó a publish_event
            mock_pub.publish_event.assert_called_once()

            # Obtener el mensaje publicado
            call_args = mock_pub.publish_event.call_args
            message = call_args[0][1]  # Segundo argumento

            # Verificar identificadores
            self.assertEqual(message['Cliente'], 'CLI_COMP_001')
            self.assertEqual(message['Contacto'], '001')

            # Verificar metadatos
            self.assertEqual(message['Tabla'], 'Clientes')
            self.assertEqual(message['Source'], 'Odoo')
            self.assertIn('Usuario', message)

    def test_mensaje_no_incluye_campos_vacios(self):
        """Test: Campos vacíos (excepto VendedorEmail) no se incluyen"""
        # Partner sin email
        partner_sin_email = self.env['res.partner'].create({
            'name': 'Sin Email',
            'cliente_externo': 'CLI_SE_001',
            'contacto_externo': '001',
            'is_company': True,
            'type': 'invoice',
            # Sin email, sin phone, sin mobile
        })

        publisher = OdooPublisher('cliente', self.env)
        message = publisher._build_message_from_odoo(partner_sin_email)

        # No debe incluir campos vacíos
        self.assertNotIn('CorreoElectronico', message)

        # PERO VendedorEmail SÍ debe incluirse aunque esté vacío
        self.assertIn('VendedorEmail', message)
