"""
Tests para Validators

Valida que los validadores funcionan correctamente
"""

from odoo.tests.common import TransactionCase
from unittest.mock import Mock
from ..transformers.validators import (
    ValidateClientePrincipalExists,
    ValidateRequiredFields,
    ValidateNifFormat,
    RequirePrincipalClientError,
    ValidatorRegistry
)


class TestValidateClientePrincipalExists(TransactionCase):
    """Tests para ValidateClientePrincipalExists"""

    def setUp(self):
        super().setUp()
        self.validator = ValidateClientePrincipalExists()
        # Usar env real de Odoo
        self.values = {'cliente_externo': '12345'}
        self.context = {'env': self.env}

    def test_cliente_principal_no_validation_needed(self):
        """Test: Cliente principal no necesita validación"""
        message = {'ClientePrincipal': True, 'Cliente': '12345'}

        # No debe lanzar excepción
        self.validator.validate(message, self.values, self.context)

        # values no debe tener parent_id porque no se ejecutó la lógica
        self.assertNotIn('parent_id', self.values)

    def test_cliente_no_principal_parent_exists(self):
        """Test: Cliente no principal con parent existente"""
        # Crear parent real en BD
        parent = self.env['res.partner'].create({
            'name': 'Cliente Principal',
            'cliente_externo': '12345',
            'parent_id': False
        })

        message = {'ClientePrincipal': False, 'Cliente': '12345'}

        # No debe lanzar excepción
        self.validator.validate(message, self.values, self.context)

        # Debe asignar parent_id
        self.assertEqual(self.values['parent_id'], parent.id)

    def test_cliente_no_principal_parent_not_exists(self):
        """Test: Cliente no principal sin parent = ERROR"""
        message = {'ClientePrincipal': False, 'Cliente': '99999'}  # ID que no existe
        self.values = {'cliente_externo': '99999'}

        # Debe lanzar RequirePrincipalClientError
        with self.assertRaises(RequirePrincipalClientError) as cm:
            self.validator.validate(message, self.values, self.context)

        self.assertIn('99999', str(cm.exception))


class TestValidateRequiredFields(TransactionCase):
    """Tests para ValidateRequiredFields"""

    def setUp(self):
        super().setUp()
        self.validator = ValidateRequiredFields()

    def test_required_field_present(self):
        """Test: Campo requerido presente"""
        message = {'Nombre': 'Test Cliente'}
        values = {}
        context = {
            'entity_config': {
                'field_mappings': {
                    'Nombre': {'required': True}
                }
            }
        }

        # No debe lanzar excepción
        self.validator.validate(message, values, context)

    def test_required_field_missing(self):
        """Test: Campo requerido faltante"""
        message = {}  # Sin Nombre
        values = {}
        context = {
            'entity_config': {
                'field_mappings': {
                    'Nombre': {'required': True}
                }
            }
        }

        # Debe lanzar ValueError
        with self.assertRaises(ValueError) as cm:
            self.validator.validate(message, values, context)

        self.assertIn('Nombre', str(cm.exception))

    def test_required_field_empty_string(self):
        """Test: Campo requerido con string vacío"""
        message = {'Nombre': '   '}  # Solo espacios
        values = {}
        context = {
            'entity_config': {
                'field_mappings': {
                    'Nombre': {'required': True}
                }
            }
        }

        # Debe lanzar ValueError
        with self.assertRaises(ValueError) as cm:
            self.validator.validate(message, values, context)

        self.assertIn('Nombre', str(cm.exception))

    def test_optional_field_missing(self):
        """Test: Campo opcional faltante = OK"""
        message = {}
        values = {}
        context = {
            'entity_config': {
                'field_mappings': {
                    'Comentarios': {}  # Sin required
                }
            }
        }

        # No debe lanzar excepción
        self.validator.validate(message, values, context)


class TestValidateNifFormat(TransactionCase):
    """Tests para ValidateNifFormat"""

    def setUp(self):
        super().setUp()
        self.validator = ValidateNifFormat()
        self.message = {}
        self.context = {}

    def test_nif_valid_format(self):
        """Test: NIF con formato válido"""
        values = {'vat': 'B12345678'}

        # No debe lanzar excepción
        self.validator.validate(self.message, values, self.context)

    def test_nif_too_short(self):
        """Test: NIF demasiado corto"""
        values = {'vat': '123'}

        # Debe lanzar ValueError
        with self.assertRaises(ValueError) as cm:
            self.validator.validate(self.message, values, self.context)

        self.assertIn('formato', str(cm.exception).lower())

    def test_nif_too_long(self):
        """Test: NIF demasiado largo"""
        values = {'vat': '12345678901'}

        # Debe lanzar ValueError
        with self.assertRaises(ValueError) as cm:
            self.validator.validate(self.message, values, self.context)

        self.assertIn('formato', str(cm.exception).lower())

    def test_nif_empty(self):
        """Test: NIF vacío = OK (opcional)"""
        values = {'vat': None}

        # No debe lanzar excepción
        self.validator.validate(self.message, values, self.context)


class TestValidatorRegistry(TransactionCase):
    """Tests para ValidatorRegistry"""

    def test_get_registered_validator(self):
        """Test: Obtener validador registrado"""
        validator = ValidatorRegistry.get('validate_cliente_principal_exists')
        self.assertIsInstance(validator, ValidateClientePrincipalExists)

    def test_get_nonexistent_validator(self):
        """Test: Obtener validador que no existe lanza error"""
        with self.assertRaises(ValueError):
            ValidatorRegistry.get('nonexistent')

    def test_multiple_validators_registered(self):
        """Test: Verificar que hay múltiples validadores registrados"""
        validators = ValidatorRegistry.get_all()

        self.assertIn('validate_cliente_principal_exists', validators)
        self.assertIn('validate_required_fields', validators)
        self.assertGreater(len(list(validators)), 2)
