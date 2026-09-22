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

    def test_el_error_de_principal_inexistente_lo_dice_claro(self):
        """Hay que poder distinguirlo del principal archivado (issue #20)"""
        message = {'ClientePrincipal': False, 'Cliente': '99999'}
        self.values = {'cliente_externo': '99999'}

        with self.assertRaises(RequirePrincipalClientError) as cm:
            self.validator.validate(message, self.values, self.context)

        self.assertIn('ni activo ni archivado', str(cm.exception))


class TestPrincipalArchivado(TransactionCase):
    """
    Issue #20: si el cliente principal está archivado, sus direcciones y
    personas de contacto no entraban nunca. La búsqueda del padre no veía los
    archivados, cada mensaje agotaba los reintentos y se iba a la DLQ, y así
    para siempre. 55 entidades el 18/09.
    """

    def setUp(self):
        super().setUp()
        self.validator = ValidateClientePrincipalExists()
        self.context = {'env': self.env}

        self.principal = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente archivado',
            'cliente_externo': '31795',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
            'parent_id': False,
        })
        self.principal.with_context(skip_sync=True).write({'active': False})

    def test_el_hijo_se_cuelga_del_principal_archivado(self):
        values = {'cliente_externo': '31795'}

        self.validator.validate(
            {'ClientePrincipal': False, 'Cliente': '31795'}, values, self.context
        )

        self.assertEqual(values['parent_id'], self.principal.id)

    def test_no_se_desarchiva_el_principal(self):
        """El archivado se decidió a mano en Odoo: no lo deshace este mensaje"""
        values = {'cliente_externo': '31795'}

        self.validator.validate(
            {'ClientePrincipal': False, 'Cliente': '31795'}, values, self.context
        )

        self.principal.invalidate_recordset(['active'])
        self.assertFalse(self.principal.active)

    def test_queda_aviso_en_el_log(self):
        values = {'cliente_externo': '31795'}

        with self.assertLogs('odoo.addons.nesto_sync.transformers.validators', 'WARNING') as logs:
            self.validator.validate(
                {'ClientePrincipal': False, 'Cliente': '31795'}, values, self.context
            )

        self.assertTrue(
            any('archivado' in linea and '31795' in linea for linea in logs.output),
            f"Log: {logs.output}"
        )

    def test_un_principal_activo_no_deja_aviso(self):
        activo = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente activo',
            'cliente_externo': '31796',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
            'parent_id': False,
        })
        values = {'cliente_externo': '31796'}

        with self.assertNoLogs('odoo.addons.nesto_sync.transformers.validators', 'WARNING'):
            self.validator.validate(
                {'ClientePrincipal': False, 'Cliente': '31796'}, values, self.context
            )

        self.assertEqual(values['parent_id'], activo.id)


class TestPrincipalArchivadoMensajeCompleto(TransactionCase):
    """El mensaje entero: lo que antes acababa en la DLQ"""

    def setUp(self):
        super().setUp()
        from ..core.entity_registry import EntityRegistry

        registry = EntityRegistry()
        self.processor = registry.get_processor('cliente', self.env)
        self.service = registry.get_service('cliente', self.env, test_mode=True)

        self.principal = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente archivado',
            'cliente_externo': '31795',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
            'parent_id': False,
        })
        self.principal.with_context(skip_sync=True).write({'active': False})

    def test_la_direccion_de_entrega_entra(self):
        mensaje = {
            'Cliente': '31795',
            'Contacto': '1',
            'ClientePrincipal': False,
            'Nombre': 'Almacén del cliente archivado',
            'Direccion': 'Calle de la Prueba 2',
            'Estado': 1,
        }

        self.service.create_or_update_contact(self.processor.process(mensaje))

        direccion = self.env['res.partner'].with_context(active_test=False).search([
            ('cliente_externo', '=', '31795'),
            ('contacto_externo', '=', '1'),
        ])

        self.assertEqual(len(direccion), 1, "La dirección tiene que entrar en Odoo")
        self.assertEqual(direccion.parent_id, self.principal)
        self.assertEqual(direccion.street, 'Calle de la Prueba 2')

    def test_la_persona_de_contacto_entra(self):
        mensaje = {
            'Cliente': '31795',
            'Contacto': '0',
            'ClientePrincipal': False,
            'Nombre': 'Cliente archivado',
            'Estado': 1,
            'PersonasContacto': [
                {'Id': '2', 'Nombre': 'Persona de contacto', 'CorreoElectronico': 'p@ejemplo.es'},
            ],
        }

        self.service.create_or_update_contact(self.processor.process(mensaje))

        persona = self.env['res.partner'].with_context(active_test=False).search([
            ('cliente_externo', '=', '31795'),
            ('persona_contacto_externa', '=', '2'),
        ])

        self.assertEqual(len(persona), 1)
        self.assertEqual(persona.email, 'p@ejemplo.es')


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
