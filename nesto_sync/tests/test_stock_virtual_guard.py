"""
Tests de la guarda de stock virtual: CantidadMontable NUNCA llega a los quants.

Issue #6 (espejo de NestoAPI#412).

Ejecutar: python -m pytest nesto_sync/tests/test_stock_virtual_guard.py -v
"""
import copy
import unittest
from unittest.mock import MagicMock, patch

from nesto_sync.core.generic_processor import GenericEntityProcessor
from nesto_sync.core.stock_guard import (
    VIRTUAL_STOCK_FIELDS,
    assert_config_ignores_virtual_stock,
    sanitize_message,
    sanitize_stocks,
    strip_virtual_stock_fields,
)
from nesto_sync.config.entity_configs import ENTITY_CONFIGS


# Mensaje real de Nesto tras NestoAPI#412: kit con stock físico 3 y 7 montables
MENSAJE_KIT = {
    'Tabla': 'Productos',
    'Producto': '31573',
    'Nombre': 'Kit de prueba',
    'ProductosKit': ['17404', '25000'],
    'ComponentesKit': [
        {'ProductoId': '17404', 'Cantidad': 2},
        {'ProductoId': '25000', 'Cantidad': 1},
    ],
    'Stocks': [
        {
            'Almacen': 'ALG',
            'Stock': 3,
            'PendienteEntregar': 1,
            'CantidadDisponible': 2,
            'CantidadMontable': 7,
        },
        {
            'Almacen': 'REI',
            'Stock': 0,
            'PendienteEntregar': 0,
            'CantidadDisponible': 0,
            'CantidadMontable': 4,
        },
    ],
}


def _make_processor(config=None):
    """Crea un GenericEntityProcessor con env mockeado."""
    env = MagicMock()
    env.user.company_id.id = 1
    return GenericEntityProcessor(env, config or ENTITY_CONFIGS['producto'])


class TestSanitizacionStockVirtual(unittest.TestCase):
    """La guarda elimina CantidadMontable y respeta el stock físico."""

    def test_strip_elimina_solo_campos_virtuales(self):
        entrada = {'Almacen': 'ALG', 'Stock': 3, 'CantidadDisponible': 2, 'CantidadMontable': 7}

        salida = strip_virtual_stock_fields(entrada)

        self.assertNotIn('CantidadMontable', salida)
        self.assertEqual(salida, {'Almacen': 'ALG', 'Stock': 3, 'CantidadDisponible': 2})

    def test_strip_no_copia_si_no_hay_campos_virtuales(self):
        entrada = {'Almacen': 'ALG', 'Stock': 3}

        self.assertIs(strip_virtual_stock_fields(entrada), entrada)

    def test_sanitize_stocks_limpia_todos_los_almacenes(self):
        stocks = sanitize_stocks(copy.deepcopy(MENSAJE_KIT['Stocks']))

        for entrada in stocks:
            self.assertNotIn('CantidadMontable', entrada)

        # El stock físico se conserva intacto
        self.assertEqual(stocks[0]['Stock'], 3)
        self.assertEqual(stocks[0]['CantidadDisponible'], 2)
        self.assertEqual(stocks[0]['PendienteEntregar'], 1)

    def test_sanitize_message_no_muta_el_original(self):
        original = copy.deepcopy(MENSAJE_KIT)

        saneado = sanitize_message(original)

        self.assertEqual(original, MENSAJE_KIT, "El mensaje original debe quedar intacto (logs/DLQ)")
        self.assertNotIn('CantidadMontable', saneado['Stocks'][0])

    def test_sanitize_message_sin_stocks_es_idempotente(self):
        mensaje = {'Tabla': 'Productos', 'Producto': '31573'}

        self.assertIs(sanitize_message(mensaje), mensaje)

    def test_sanitize_message_tolera_stocks_malformados(self):
        mensaje = {'Producto': '1', 'Stocks': None}
        self.assertIs(sanitize_message(mensaje), mensaje)

        mensaje = {'Producto': '1', 'Stocks': [None, {'CantidadMontable': 5}]}
        saneado = sanitize_message(mensaje)
        self.assertEqual(saneado['Stocks'], [None, {}])


class TestGuardaDeConfiguracion(unittest.TestCase):
    """Ninguna entidad puede cablear un campo virtual de stock."""

    def test_todas_las_entidades_actuales_pasan_la_guarda(self):
        for nombre, config in ENTITY_CONFIGS.items():
            with self.subTest(entidad=nombre):
                assert_config_ignores_virtual_stock(config)

    def test_mapeo_entrante_de_campo_virtual_falla(self):
        config = {
            'message_type': 'producto',
            'field_mappings': {'CantidadMontable': {'odoo_field': 'qty_available'}},
        }

        with self.assertRaises(ValueError) as ctx:
            assert_config_ignores_virtual_stock(config)

        self.assertIn('CantidadMontable', str(ctx.exception))

    def test_mapeo_entrante_anidado_de_campo_virtual_falla(self):
        config = {
            'message_type': 'producto',
            'field_mappings': {'Stocks.CantidadMontable': {'odoo_field': 'qty_available'}},
        }

        with self.assertRaises(ValueError):
            assert_config_ignores_virtual_stock(config)

    def test_mapeo_en_children_de_campo_virtual_falla(self):
        config = {
            'message_type': 'producto',
            'child_field_mappings': {'CantidadMontable': {'odoo_field': 'quantity'}},
        }

        with self.assertRaises(ValueError):
            assert_config_ignores_virtual_stock(config)

    def test_mapeo_inverso_de_campo_virtual_falla(self):
        """Odoo tampoco debe publicar CantidadMontable: lo calcula Nesto."""
        config = {
            'message_type': 'producto',
            'reverse_field_mappings': {'qty_available': {'nesto_field': 'CantidadMontable'}},
        }

        with self.assertRaises(ValueError):
            assert_config_ignores_virtual_stock(config)

    def test_el_processor_valida_la_config_al_construirse(self):
        config = dict(
            ENTITY_CONFIGS['producto'],
            field_mappings=dict(
                ENTITY_CONFIGS['producto']['field_mappings'],
                CantidadMontable={'odoo_field': 'qty_available'},
            ),
        )

        with self.assertRaises(ValueError):
            _make_processor(config)


class TestMensajeKitNoTocaElStock(unittest.TestCase):
    """Un mensaje real con montables > 0 no produce ningún valor de stock."""

    def setUp(self):
        self.processor = _make_processor()

    def test_build_values_ignora_stocks_por_completo(self):
        with patch.object(self.processor, '_add_external_ids'):
            with patch.object(self.processor, '_apply_transformer'):
                values = self.processor._build_values(copy.deepcopy(MENSAJE_KIT))

        # Ningún campo de stock de Odoo aparece en los valores
        for campo in ('qty_available', 'quantity', 'inventory_quantity', 'free_qty', 'virtual_available'):
            self.assertNotIn(campo, values)

        # Ni ningún valor derivado de las cantidades montables (7 y 4)
        self.assertNotIn(7, values.values())
        self.assertNotIn(4, values.values())

        # Los campos que sí están mapeados siguen procesándose
        self.assertEqual(values['default_code'], '31573')
        self.assertEqual(values['name'], 'Kit de prueba')

    def test_los_post_processors_nunca_ven_cantidadmontable(self):
        """Defensa en profundidad: el mensaje ya llega saneado al pipeline."""
        vistos = {}

        class _Espia:
            def process(self, parent_values, children_values_list, context):
                vistos['message'] = context['message']
                return parent_values, children_values_list

        with patch('nesto_sync.core.generic_processor.PostProcessorRegistry.get',
                   return_value=_Espia()):
            with patch.object(self.processor, '_add_external_ids'):
                with patch.object(self.processor, '_apply_transformer'):
                    self.processor.process(copy.deepcopy(MENSAJE_KIT))

        for entrada in vistos['message']['Stocks']:
            self.assertNotIn('CantidadMontable', entrada)
        # El resto del mensaje llega íntegro (ComponentesKit para la futura BoM)
        self.assertEqual(len(vistos['message']['ComponentesKit']), 2)

    def test_no_se_accede_al_modelo_stock_quant(self):
        with patch('nesto_sync.core.generic_processor.PostProcessorRegistry.get',
                   return_value=MagicMock(process=lambda p, c, ctx: (p, c))):
            with patch.object(self.processor, '_add_external_ids'):
                with patch.object(self.processor, '_apply_transformer'):
                    self.processor.process(copy.deepcopy(MENSAJE_KIT))

        modelos_usados = [
            call.args[0] for call in self.processor.env.__getitem__.call_args_list
        ]
        self.assertNotIn('stock.quant', modelos_usados)
        self.assertNotIn('stock.move', modelos_usados)

    def test_la_guarda_cubre_todos_los_campos_virtuales_declarados(self):
        """Si se añade otro campo virtual a la lista, queda cubierto igual."""
        mensaje = {
            'Producto': '31573',
            'Nombre': 'Kit',
            'Stocks': [dict({'Almacen': 'ALG', 'Stock': 3},
                            **{campo: 99 for campo in VIRTUAL_STOCK_FIELDS})],
        }

        saneado = sanitize_message(mensaje)

        for campo in VIRTUAL_STOCK_FIELDS:
            self.assertNotIn(campo, saneado['Stocks'][0])
        self.assertEqual(saneado['Stocks'][0]['Stock'], 3)


if __name__ == '__main__':
    unittest.main()
