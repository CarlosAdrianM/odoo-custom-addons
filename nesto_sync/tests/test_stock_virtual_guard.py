"""
Tests de la guarda de stock: CantidadMontable NUNCA llega a los quants.

Issue #6 (espejo de NestoAPI#412). El contrato de Stocks[] usado aquí es el
confirmado con NestoAPI el 27/08/2026.

Ejecutar: python -m pytest nesto_sync/tests/test_stock_virtual_guard.py -v
"""
import copy
import unittest
from unittest.mock import MagicMock, patch

from odoo.addons.nesto_sync.core.generic_processor import GenericEntityProcessor
from odoo.addons.nesto_sync.core.stock_guard import (
    QUANT_SOURCE_FIELD,
    STOCK_FIELDS_PERMITIDOS,
    VIRTUAL_STOCK_FIELDS,
    assert_stock_mapping_is_safe,
    sanitize_message,
    sanitize_stocks,
    strip_virtual_stock_fields,
)
from odoo.addons.nesto_sync.config.entity_configs import ENTITY_CONFIGS


# Entrada de stock con TODOS los campos del contrato (NestoAPI, 27/08/2026)
STOCK_ALG_COMPLETO = {
    'Almacen': 'ALG',
    'Stock': 3,
    'PendienteEntregar': 1,
    'PendienteRecibir': 10,
    'PendienteReposicion': 0,
    'FechaEstimadaRecepcion': '2026-09-15T00:00:00',
    'CantidadDisponible': 2,
    'CantidadMontable': 7,
}

# Mensaje real de Nesto: kit con stock físico 3 y 7 montables
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
        dict(STOCK_ALG_COMPLETO),
        {
            'Almacen': 'REI',
            'Stock': 0,
            'PendienteEntregar': 0,
            'PendienteRecibir': 0,
            'PendienteReposicion': 0,
            'FechaEstimadaRecepcion': '9999-12-31T00:00:00',
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


class TestAllowlistDeStock(unittest.TestCase):
    """La allowlist deja pasar lo real y descarta lo virtual y lo desconocido."""

    def test_strip_conserva_todos_los_campos_del_contrato(self):
        salida = strip_virtual_stock_fields(dict(STOCK_ALG_COMPLETO))

        self.assertNotIn('CantidadMontable', salida)
        self.assertEqual(salida, {
            'Almacen': 'ALG',
            'Stock': 3,
            'PendienteEntregar': 1,
            'PendienteRecibir': 10,
            'PendienteReposicion': 0,
            'FechaEstimadaRecepcion': '2026-09-15T00:00:00',
            'CantidadDisponible': 2,
        })

    def test_strip_descarta_campos_desconocidos(self):
        """Un campo nuevo no previsto se descarta por defecto (allowlist)."""
        entrada = {'Almacen': 'ALG', 'Stock': 3, 'CampoNuevoDeNesto': 999}

        salida = strip_virtual_stock_fields(entrada)

        self.assertNotIn('CampoNuevoDeNesto', salida)
        self.assertEqual(salida, {'Almacen': 'ALG', 'Stock': 3})

    def test_strip_avisa_de_campos_desconocidos(self):
        """Descartar en silencio ocultaría un cambio de contrato: se avisa."""
        entrada = {'Almacen': 'ALG', 'Stock': 3, 'CampoNuevoDeNesto': 999}

        with patch('nesto_sync.core.stock_guard._logger') as logger:
            strip_virtual_stock_fields(entrada)

        logger.warning.assert_called_once()
        self.assertIn('CampoNuevoDeNesto', str(logger.warning.call_args))

    def test_strip_no_avisa_por_los_campos_virtuales_conocidos(self):
        """CantidadMontable es esperado: se ignora sin ruido en los logs."""
        with patch('nesto_sync.core.stock_guard._logger') as logger:
            strip_virtual_stock_fields(dict(STOCK_ALG_COMPLETO))

        logger.warning.assert_not_called()

    def test_strip_no_copia_si_no_hay_nada_que_quitar(self):
        entrada = {'Almacen': 'ALG', 'Stock': 3}

        self.assertIs(strip_virtual_stock_fields(entrada), entrada)

    def test_sanitize_stocks_limpia_todos_los_almacenes(self):
        stocks = sanitize_stocks(copy.deepcopy(MENSAJE_KIT['Stocks']))

        for entrada in stocks:
            self.assertNotIn('CantidadMontable', entrada)

        # El stock físico y los pendientes reales se conservan intactos
        self.assertEqual(stocks[0]['Stock'], 3)
        self.assertEqual(stocks[0]['CantidadDisponible'], 2)
        self.assertEqual(stocks[0]['PendienteEntregar'], 1)
        self.assertEqual(stocks[0]['PendienteRecibir'], 10)
        self.assertEqual(stocks[0]['PendienteReposicion'], 0)

    def test_sanitize_stocks_no_copia_si_ya_esta_limpio(self):
        stocks = [{'Almacen': 'ALG', 'Stock': 3}]

        self.assertIs(sanitize_stocks(stocks), stocks)

    def test_el_campo_para_quants_es_stock(self):
        """Si algún día se mapean quants, el origen documentado es Stock."""
        self.assertEqual(QUANT_SOURCE_FIELD, 'Stock')
        self.assertIn(QUANT_SOURCE_FIELD, STOCK_FIELDS_PERMITIDOS)
        self.assertNotIn(QUANT_SOURCE_FIELD, VIRTUAL_STOCK_FIELDS)

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
    """Ninguna entidad puede cablear stock inseguro."""

    def test_todas_las_entidades_actuales_pasan_la_guarda(self):
        for nombre, config in ENTITY_CONFIGS.items():
            with self.subTest(entidad=nombre):
                assert_stock_mapping_is_safe(config)

    def test_mapeo_entrante_de_campo_virtual_falla(self):
        config = {
            'message_type': 'producto',
            'field_mappings': {'CantidadMontable': {'odoo_field': 'qty_available'}},
        }

        with self.assertRaises(ValueError) as ctx:
            assert_stock_mapping_is_safe(config)

        self.assertIn('CantidadMontable', str(ctx.exception))

    def test_mapeo_entrante_anidado_de_campo_virtual_falla(self):
        config = {
            'message_type': 'producto',
            'field_mappings': {'Stocks.CantidadMontable': {'odoo_field': 'qty_available'}},
        }

        with self.assertRaises(ValueError):
            assert_stock_mapping_is_safe(config)

    def test_mapeo_en_children_de_campo_virtual_falla(self):
        config = {
            'message_type': 'producto',
            'child_field_mappings': {'CantidadMontable': {'odoo_field': 'quantity'}},
        }

        with self.assertRaises(ValueError):
            assert_stock_mapping_is_safe(config)

    def test_mapeo_inverso_de_campo_virtual_falla(self):
        """Odoo tampoco debe publicar CantidadMontable: lo calcula Nesto."""
        config = {
            'message_type': 'producto',
            'reverse_field_mappings': {'qty_available': {'nesto_field': 'CantidadMontable'}},
        }

        with self.assertRaises(ValueError):
            assert_stock_mapping_is_safe(config)

    def test_mapeo_de_campo_de_stock_desconocido_falla(self):
        """Allowlist: un campo de Stocks[] no previsto tampoco se puede mapear."""
        config = {
            'message_type': 'producto',
            'field_mappings': {'Stocks.CampoInventado': {'odoo_field': 'qty_available'}},
        }

        with self.assertRaises(ValueError) as ctx:
            assert_stock_mapping_is_safe(config)

        self.assertIn('allowlist', str(ctx.exception))

    def test_mapeo_de_stock_fisico_esta_permitido(self):
        """La guarda no estorba al mapeo legítimo del stock físico."""
        config = {
            'message_type': 'producto',
            'field_mappings': {
                'Stocks.Stock': {'odoo_field': 'qty_available'},
                'Stocks.CantidadDisponible': {'odoo_field': 'free_qty'},
                'Stocks.FechaEstimadaRecepcion': {'odoo_field': 'date_planned'},
            },
        }

        assert_stock_mapping_is_safe(config)  # no debe lanzar

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
            self.assertIn('Stock', entrada)
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
