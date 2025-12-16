"""
Tests para Field Transformers

Valida que cada transformer funciona correctamente
"""

import unittest
from unittest.mock import Mock, MagicMock
from odoo.tests.common import TransactionCase
from ..transformers.field_transformers import (
    PhoneTransformer,
    CountryStateTransformer,
    EstadoToActiveTransformer,
    ClientePrincipalTransformer,
    CountryCodeTransformer,
    CargosTransformer,
    PriceTransformer,
    QuantityTransformer,
    FieldTransformerRegistry,
    VendedorTransformer
)
from ..models.country_manager import CountryManager


class TestPhoneTransformer(TransactionCase):
    """Tests para PhoneTransformer"""

    def setUp(self):
        super().setUp()
        self.transformer = PhoneTransformer()
        self.context = {}

    def test_phone_with_mobile_and_landline(self):
        """Test: teléfono con móvil y fijo separados por /"""
        result = self.transformer.transform("666123456/912345678", self.context)

        self.assertEqual(result['mobile'], '666123456')
        self.assertEqual(result['phone'], '912345678')
        self.assertNotIn('_append_comment', result)

    def test_phone_with_extras(self):
        """Test: múltiples teléfonos que generan extras"""
        result = self.transformer.transform("666111222/912345678/666333444", self.context)

        self.assertEqual(result['mobile'], '666111222')
        self.assertEqual(result['phone'], '912345678')
        self.assertIn('_append_comment', result)
        self.assertIn('666333444', result['_append_comment'])

    def test_phone_empty(self):
        """Test: teléfono vacío"""
        result = self.transformer.transform(None, self.context)

        self.assertIsNone(result['mobile'])
        self.assertIsNone(result['phone'])

    def test_phone_only_mobile(self):
        """Test: solo móvil"""
        result = self.transformer.transform("666123456", self.context)

        self.assertEqual(result['mobile'], '666123456')
        self.assertIsNone(result['phone'])


class TestEstadoToActiveTransformer(TransactionCase):
    """Tests para EstadoToActiveTransformer"""

    def setUp(self):
        super().setUp()
        self.transformer = EstadoToActiveTransformer()
        self.context = {}

    def test_estado_positive(self):
        """Test: Estado positivo = active True"""
        result = self.transformer.transform(1, self.context)
        self.assertTrue(result['active'])

    def test_estado_zero(self):
        """Test: Estado 0 = active True"""
        result = self.transformer.transform(0, self.context)
        self.assertTrue(result['active'])

    def test_estado_negative(self):
        """Test: Estado negativo = active False"""
        result = self.transformer.transform(-1, self.context)
        self.assertFalse(result['active'])

    def test_estado_none(self):
        """Test: Estado None = active True (default)"""
        result = self.transformer.transform(None, self.context)
        self.assertTrue(result['active'])


class TestClientePrincipalTransformer(TransactionCase):
    """Tests para ClientePrincipalTransformer"""

    def setUp(self):
        super().setUp()
        self.transformer = ClientePrincipalTransformer()
        self.context = {}

    def test_cliente_principal_true(self):
        """Test: Cliente principal = is_company True, type invoice"""
        result = self.transformer.transform(True, self.context)

        self.assertTrue(result['is_company'])
        self.assertEqual(result['type'], 'invoice')

    def test_cliente_principal_false(self):
        """Test: No principal = is_company False, type delivery"""
        result = self.transformer.transform(False, self.context)

        self.assertFalse(result['is_company'])
        self.assertEqual(result['type'], 'delivery')


class TestCargosTransformer(TransactionCase):
    """Tests para CargosTransformer"""

    def setUp(self):
        super().setUp()
        self.transformer = CargosTransformer()
        self.context = {}

    def test_cargo_exists(self):
        """Test: Cargo que existe en el mapeo"""
        result = self.transformer.transform(5, self.context)  # 5 = Gerente
        self.assertEqual(result['function'], 'Gerente')

    def test_cargo_not_exists(self):
        """Test: Cargo que no existe devuelve None"""
        result = self.transformer.transform(999, self.context)
        self.assertIsNone(result['function'])

    def test_cargo_none(self):
        """Test: Cargo None"""
        result = self.transformer.transform(None, self.context)
        self.assertIsNone(result['function'])


class TestPriceTransformer(TransactionCase):
    """Tests para PriceTransformer"""

    def setUp(self):
        super().setUp()
        self.transformer = PriceTransformer()
        self.context = {}

    def test_price_valid_number(self):
        """Test: Precio válido"""
        result = self.transformer.transform(99.99, self.context)
        self.assertEqual(result['list_price'], 99.99)

    def test_price_string(self):
        """Test: Precio como string"""
        result = self.transformer.transform("49.95", self.context)
        self.assertEqual(result['list_price'], 49.95)

    def test_price_none(self):
        """Test: Precio None = 0.0"""
        result = self.transformer.transform(None, self.context)
        self.assertEqual(result['list_price'], 0.0)

    def test_price_invalid(self):
        """Test: Precio inválido = 0.0"""
        result = self.transformer.transform("invalid", self.context)
        self.assertEqual(result['list_price'], 0.0)


class TestFieldTransformerRegistry(TransactionCase):
    """Tests para FieldTransformerRegistry"""

    def test_get_registered_transformer(self):
        """Test: Obtener transformer registrado"""
        transformer = FieldTransformerRegistry.get('phone')
        self.assertIsInstance(transformer, PhoneTransformer)

    def test_get_nonexistent_transformer(self):
        """Test: Obtener transformer que no existe lanza error"""
        with self.assertRaises(ValueError):
            FieldTransformerRegistry.get('nonexistent')

    def test_multiple_transformers_registered(self):
        """Test: Verificar que hay múltiples transformers registrados"""
        transformers = FieldTransformerRegistry.get_all()

        self.assertIn('phone', transformers)
        self.assertIn('estado_to_active', transformers)
        self.assertIn('cliente_principal', transformers)
        self.assertGreater(len(list(transformers)), 5)


class TestCountryStateTransformer(TransactionCase):
    """Tests para CountryStateTransformer (requiere BD Odoo)"""

    def setUp(self):
        super().setUp()
        self.transformer = CountryStateTransformer()

        # Mock del country_manager
        self.mock_country_manager = Mock(spec=CountryManager)
        self.context = {'country_manager': self.mock_country_manager}

    def test_province_exists(self):
        """Test: Provincia que existe"""
        self.mock_country_manager.get_or_create_state.return_value = 45

        result = self.transformer.transform('Madrid', self.context)

        self.assertEqual(result['state_id'], 45)
        self.mock_country_manager.get_or_create_state.assert_called_once_with('Madrid')

    def test_province_empty(self):
        """Test: Provincia vacía"""
        result = self.transformer.transform(None, self.context)

        self.assertIsNone(result['state_id'])
        self.mock_country_manager.get_or_create_state.assert_not_called()

    def test_province_no_country_manager(self):
        """Test: Sin country_manager en contexto lanza error"""
        with self.assertRaises(ValueError) as cm:
            self.transformer.transform('Madrid', {})

        self.assertIn('CountryManager', str(cm.exception))


class TestCountryCodeTransformer(TransactionCase):
    """Tests para CountryCodeTransformer (requiere BD Odoo)"""

    def setUp(self):
        super().setUp()
        self.transformer = CountryCodeTransformer()
        # Usar env real de Odoo en lugar de mock
        self.context = {'env': self.env}

    def test_country_code_exists(self):
        """Test: Código de país que existe"""
        # Buscar un país que realmente existe en la BD
        result = self.transformer.transform('ES', self.context)

        # Debe retornar un country_id válido
        self.assertIsNotNone(result['country_id'])
        self.assertIsInstance(result['country_id'], int)

    def test_country_code_not_exists(self):
        """Test: Código de país que no existe"""
        # Usar código que probablemente no existe
        result = self.transformer.transform('XX', self.context)

        self.assertIsNone(result['country_id'])

    def test_country_code_empty(self):
        """Test: Código vacío"""
        result = self.transformer.transform(None, self.context)

        self.assertIsNone(result['country_id'])


class TestVendedorTransformer(TransactionCase):
    """Tests para VendedorTransformer - Auto-mapeo SOLO por email (sin vendedor_externo)"""

    def setUp(self):
        super().setUp()
        self.transformer = VendedorTransformer()

        # Crear usuario de prueba
        self.user_juan = self.env['res.users'].sudo().create({
            'name': 'Juan Pérez',
            'login': 'juan@nuevavision.es',
            'email': 'juan@nuevavision.es',
        })

    def test_auto_mapeo_exitoso(self):
        """Test: Auto-mapeo por email funciona correctamente"""
        context = {
            'env': self.env,
            'nesto_data': {
                'VendedorEmail': 'juan@nuevavision.es'
            }
        }

        # El código de vendedor se ignora, solo importa VendedorEmail
        result = self.transformer.transform('001', context)

        self.assertEqual(result['user_id'], self.user_juan.id)
        self.assertNotIn('vendedor_externo', result)  # Ya no existe este campo

    def test_auto_mapeo_email_case_insensitive(self):
        """Test: Auto-mapeo ignora mayúsculas/minúsculas en email"""
        context = {
            'env': self.env,
            'nesto_data': {
                'VendedorEmail': 'JUAN@NUEVAVISION.ES'
            }
        }

        result = self.transformer.transform('001', context)

        self.assertEqual(result['user_id'], self.user_juan.id)

    def test_email_no_encontrado(self):
        """Test: Email que no existe en Odoo → user_id=False"""
        context = {
            'env': self.env,
            'nesto_data': {
                'VendedorEmail': 'noexiste@email.com'
            }
        }

        result = self.transformer.transform('002', context)

        self.assertFalse(result['user_id'])

    def test_sin_email_en_mensaje(self):
        """Test: Mensaje sin VendedorEmail → dict vacío (no modifica user_id)"""
        context = {
            'env': self.env,
            'nesto_data': {}  # Sin VendedorEmail
        }

        result = self.transformer.transform('003', context)

        # Sin email, no se modifica nada
        self.assertEqual(result, {})

    def test_codigo_vendedor_ignorado(self):
        """Test: El código de vendedor se ignora, solo importa el email"""
        context = {
            'env': self.env,
            'nesto_data': {
                'VendedorEmail': 'juan@nuevavision.es'
            }
        }

        # Aunque no venga código, si hay email funciona
        result = self.transformer.transform('', context)
        self.assertEqual(result['user_id'], self.user_juan.id)

        result = self.transformer.transform(None, context)
        self.assertEqual(result['user_id'], self.user_juan.id)

    def test_email_con_espacios(self):
        """Test: Email con espacios se limpia correctamente"""
        context = {
            'env': self.env,
            'nesto_data': {
                'VendedorEmail': '  juan@nuevavision.es  '
            }
        }

        result = self.transformer.transform('001', context)

        self.assertEqual(result['user_id'], self.user_juan.id)

    def test_registro_en_registry(self):
        """Test: VendedorTransformer está registrado correctamente"""
        transformer = FieldTransformerRegistry.get('vendedor')
        self.assertIsInstance(transformer, VendedorTransformer)
