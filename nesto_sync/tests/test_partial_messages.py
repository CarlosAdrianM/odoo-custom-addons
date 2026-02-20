"""
Tests para verificar que mensajes parciales no sobrescriben campos ausentes (Issue #3).

Ejecutar: python -m pytest nesto_sync/tests/test_partial_messages.py -v
"""
import unittest
from unittest.mock import patch, MagicMock

from nesto_sync.core.generic_processor import GenericEntityProcessor
from nesto_sync.config.entity_configs import ENTITY_CONFIGS


def _make_processor(config=None):
    """Crea un GenericEntityProcessor con env mockeado."""
    env = MagicMock()
    env.user.company_id.id = 1
    return GenericEntityProcessor(env, config or ENTITY_CONFIGS['producto'])


class TestPartialMessages(unittest.TestCase):
    """Tests para verificar que mensajes parciales no sobrescriben campos ausentes (Issue #3)."""

    def setUp(self):
        self.processor = _make_processor()

    def test_mensaje_completo_funciona_igual(self):
        """Un mensaje con todos los campos se procesa normalmente."""
        message = {
            'Producto': 'TEST001',
            'Nombre': 'Producto Test',
            'PrecioProfesional': 25.50,
            'CodigoBarras': '1234567890',
        }

        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer'):
                values = self.processor._build_values(message)

        self.assertEqual(values['default_code'], 'TEST001')
        self.assertEqual(values['name'], 'Producto Test')
        self.assertEqual(values['list_price'], 25.50)
        self.assertEqual(values['barcode'], '1234567890')

    def test_mensaje_parcial_no_sobrescribe_campos_ausentes(self):
        """Un mensaje con solo Producto no debe incluir Nombre, Precio, etc."""
        message = {
            'Producto': 'TEST001',
        }

        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer'):
                values = self.processor._build_values(message)

        self.assertEqual(values['default_code'], 'TEST001')
        # Campos ausentes NO deben aparecer en values
        self.assertNotIn('name', values)
        self.assertNotIn('list_price', values)
        self.assertNotIn('barcode', values)

    def test_campos_fixed_siempre_se_procesan(self):
        """Los campos tipo 'fixed' se procesan aunque no vengan en el mensaje."""
        config = {
            'field_mappings': {
                '_tipo': {
                    'type': 'fixed',
                    'odoo_field': 'type',
                    'value': 'product'
                },
                'Nombre': {
                    'odoo_field': 'name',
                    'required': False,
                    'default': '<sin nombre>'
                },
            },
            'external_id_mapping': {},
        }
        processor = _make_processor(config)

        message = {}  # Mensaje vacío

        with patch.object(processor, '_add_external_ids'):
            values = processor._build_values(message)

        # El campo fixed siempre aparece
        self.assertEqual(values['type'], 'product')
        # El campo Nombre NO debe aparecer (ausente del mensaje)
        self.assertNotIn('name', values)

    def test_campos_context_siempre_se_procesan(self):
        """Los campos tipo 'context' se procesan aunque no vengan en el mensaje."""
        message = {
            'Producto': 'TEST001',
        }

        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer'):
                values = self.processor._build_values(message)

        # company_id (campo context) siempre debe estar
        self.assertIn('company_id', values)
        self.assertEqual(values['company_id'], 1)

    def test_campo_presente_con_valor_none_si_se_procesa(self):
        """Un campo presente con valor None explícito SÍ se debe procesar."""
        message = {
            'Producto': 'TEST001',
            'CodigoBarras': None,
        }

        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer'):
                values = self.processor._build_values(message)

        # CodigoBarras está presente (aunque con None), así que debe procesarse
        self.assertIn('barcode', values)
        self.assertIsNone(values['barcode'])

    def test_campo_con_default_no_se_aplica_si_ausente(self):
        """Si un campo tiene default pero no viene en el mensaje, no se debe aplicar el default."""
        message = {
            'Producto': 'TEST001',
        }

        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer'):
                values = self.processor._build_values(message)

        # Nombre tiene default '<Nombre producto no proporcionado>' pero no viene en el mensaje
        self.assertNotIn('name', values)
        # PrecioProfesional tiene default 0.0 pero no viene en el mensaje
        self.assertNotIn('list_price', values)

    def test_transformer_no_se_invoca_si_campo_ausente(self):
        """Los transformers no deben ejecutarse para campos ausentes."""
        message = {
            'Producto': 'TEST001',
            'Nombre': 'Test',
        }

        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer') as mock_transformer:
                self.processor._build_values(message)

        transformer_names_called = [call[0][0] for call in mock_transformer.call_args_list]
        self.assertNotIn('estado_to_active', transformer_names_called)
        self.assertNotIn('ficticio_to_detailed_type', transformer_names_called)
        self.assertNotIn('grupo', transformer_names_called)
        self.assertNotIn('subgrupo', transformer_names_called)
        self.assertNotIn('familia', transformer_names_called)
        self.assertNotIn('url_to_image', transformer_names_called)
        self.assertNotIn('unidad_medida_y_tamanno', transformer_names_called)

    def test_transformer_si_se_invoca_si_campo_presente(self):
        """Los transformers deben ejecutarse para campos presentes."""
        message = {
            'Producto': 'TEST001',
            'Nombre': 'Test',
            'Estado': 1,
        }

        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer') as mock_transformer:
                self.processor._build_values(message)

        transformer_names_called = [call[0][0] for call in mock_transformer.call_args_list]
        self.assertIn('estado_to_active', transformer_names_called)
        self.assertNotIn('ficticio_to_detailed_type', transformer_names_called)

    def test_child_data_respeta_campos_parciales(self):
        """Los child_data también deben respetar campos parciales."""
        config = {
            'field_mappings': {},
            'child_field_mappings': {
                'Nombre': {
                    'odoo_field': 'name',
                    'required': False,
                    'default': '<sin nombre>'
                },
                'CorreoElectronico': {
                    'odoo_field': 'email',
                },
            },
            'external_id_mapping': {},
        }
        processor = _make_processor(config)

        message = {'Cliente': '1'}
        child_data = {'Nombre': 'Juan'}  # Sin CorreoElectronico

        with patch.object(processor, '_add_external_ids'):
            values = processor._build_values(message, is_parent=False, child_data=child_data)

        self.assertEqual(values['name'], 'Juan')
        self.assertNotIn('email', values)


class TestFieldPresentInData(unittest.TestCase):
    """Tests para el helper _field_present_in_data."""

    def setUp(self):
        self.processor = _make_processor()

    def test_campo_simple_presente(self):
        self.assertTrue(self.processor._field_present_in_data({'Nombre': 'Test'}, 'Nombre'))

    def test_campo_simple_ausente(self):
        self.assertFalse(self.processor._field_present_in_data({'Nombre': 'Test'}, 'Precio'))

    def test_campo_presente_con_valor_none(self):
        self.assertTrue(self.processor._field_present_in_data({'Nombre': None}, 'Nombre'))

    def test_campo_presente_con_valor_vacio(self):
        self.assertTrue(self.processor._field_present_in_data({'Nombre': ''}, 'Nombre'))

    def test_campo_anidado_presente(self):
        data = {'PersonaContacto': {'Id': '1', 'Nombre': 'Juan'}}
        self.assertTrue(self.processor._field_present_in_data(data, 'PersonaContacto.Id'))

    def test_campo_anidado_ausente(self):
        data = {'PersonaContacto': {'Id': '1'}}
        self.assertFalse(self.processor._field_present_in_data(data, 'PersonaContacto.Email'))

    def test_campo_anidado_padre_ausente(self):
        data = {'Nombre': 'Test'}
        self.assertFalse(self.processor._field_present_in_data(data, 'PersonaContacto.Id'))

    def test_data_vacio(self):
        self.assertFalse(self.processor._field_present_in_data({}, 'Nombre'))

    def test_data_none(self):
        self.assertFalse(self.processor._field_present_in_data(None, 'Nombre'))

    def test_path_vacio(self):
        self.assertFalse(self.processor._field_present_in_data({'Nombre': 'Test'}, ''))


if __name__ == '__main__':
    unittest.main()
