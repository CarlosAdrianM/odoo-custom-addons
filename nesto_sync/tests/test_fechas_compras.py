"""Tests de las fechas de compras que envía Nesto (Issue #8, NestoAPI#498).

FechaPrimerPresupuesto, FechaPrimerPedido y FechaUltimoPedido las calcula Nesto y solo
viajan de Nesto a Odoo: nunca se devuelven.
"""
import unittest
from datetime import date
from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.nesto_sync.config.entity_configs import ENTITY_CONFIGS
from odoo.addons.nesto_sync.core.generic_processor import GenericEntityProcessor
from odoo.addons.nesto_sync.core.generic_service import GenericEntityService
from odoo.addons.nesto_sync.core.odoo_publisher import OdooPublisher
from odoo.addons.nesto_sync.transformers.field_transformers import FieldTransformerRegistry

CAMPOS = {
    'FechaPrimerPresupuesto': 'fecha_primer_presupuesto',
    'FechaPrimerPedido': 'fecha_primer_pedido',
    'FechaUltimoPedido': 'fecha_ultimo_pedido',
}


def _processor():
    env = MagicMock()
    env.user.company_id.id = 1
    return GenericEntityProcessor(env, ENTITY_CONFIGS['cliente'])


class TestTransformerFecha(unittest.TestCase):
    """El transformer 'fecha': ISO a Date, null a False."""

    def setUp(self):
        self.transformer = FieldTransformerRegistry.get('fecha')
        self.context = {'mapping': {'odoo_field': 'fecha_primer_pedido'}}

    def _transformar(self, valor):
        return self.transformer.transform(valor, self.context)['fecha_primer_pedido']

    def test_fecha_iso_simple(self):
        self.assertEqual(self._transformar('2026-01-15'), date(2026, 1, 15))

    def test_fecha_iso_con_hora(self):
        self.assertEqual(self._transformar('2026-01-15T10:30:00'), date(2026, 1, 15))

    def test_fecha_iso_con_zona(self):
        self.assertEqual(self._transformar('2026-01-15T10:30:00Z'), date(2026, 1, 15))

    def test_fecha_con_espacio(self):
        self.assertEqual(self._transformar('2026-01-15 10:30:00'), date(2026, 1, 15))

    def test_null_vacia_el_campo(self):
        self.assertIs(self._transformar(None), False)

    def test_cadena_vacia_vacia_el_campo(self):
        self.assertIs(self._transformar(''), False)

    def test_formato_desconocido_falla(self):
        with self.assertRaises(ValueError):
            self._transformar('15/01/2026')

    def test_sin_campo_destino_falla(self):
        with self.assertRaises(ValueError):
            self.transformer.transform('2026-01-15', {'mapping': {}})


class TestMapeoFechas(unittest.TestCase):
    """Mapeo de las tres fechas y respeto de los mensajes parciales (Issue #3)."""

    def setUp(self):
        self.processor = _processor()

    def _valores(self, message):
        return self.processor._build_values(message)

    def test_las_tres_fechas_se_mapean(self):
        valores = self._valores({
            'Cliente': '12345', 'Contacto': '0',
            'FechaPrimerPresupuesto': '2026-01-15',
            'FechaPrimerPedido': '2026-02-20',
            'FechaUltimoPedido': '2026-09-01',
        })
        self.assertEqual(valores['fecha_primer_presupuesto'], date(2026, 1, 15))
        self.assertEqual(valores['fecha_primer_pedido'], date(2026, 2, 20))
        self.assertEqual(valores['fecha_ultimo_pedido'], date(2026, 9, 1))

    def test_mensaje_sin_las_fechas_no_las_toca(self):
        valores = self._valores({'Cliente': '12345', 'Contacto': '0', 'Nombre': 'Cliente Test'})
        for odoo_field in CAMPOS.values():
            self.assertNotIn(odoo_field, valores)

    def test_fecha_null_vacia_el_campo(self):
        """Ausente y null son cosas distintas: null sí borra."""
        valores = self._valores({'Cliente': '12345', 'Contacto': '0', 'FechaPrimerPedido': None})
        self.assertIn('fecha_primer_pedido', valores)
        self.assertIs(valores['fecha_primer_pedido'], False)

    def test_una_fecha_no_arrastra_a_las_otras(self):
        valores = self._valores({'Cliente': '12345', 'Contacto': '0', 'FechaUltimoPedido': '2026-09-01'})
        self.assertEqual(valores['fecha_ultimo_pedido'], date(2026, 9, 1))
        self.assertNotIn('fecha_primer_pedido', valores)
        self.assertNotIn('fecha_primer_presupuesto', valores)


@tagged('post_install', '-at_install', 'nesto_sync')
class TestFechasNoVuelvenANesto(TransactionCase):
    """Las fechas las calcula Nesto: Odoo no se las devuelve nunca."""

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('nesto_sync.google_project_id', 'test-project')
        icp.set_param('nesto_sync.pubsub_provider', 'google_pubsub')
        self.partner = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente Fechas', 'cliente_externo': 'CLI_FECHAS_001', 'contacto_externo': '0',
            'is_company': True, 'type': 'invoice',
            'fecha_primer_presupuesto': date(2026, 1, 15),
            'fecha_primer_pedido': date(2026, 2, 20),
            'fecha_ultimo_pedido': date(2026, 9, 1),
        })

    def test_el_mapeo_inverso_inferido_las_excluye(self):
        inverso = OdooPublisher('cliente', self.env)._infer_reverse_mappings()
        for odoo_field in CAMPOS.values():
            self.assertNotIn(odoo_field, inverso)

    def test_el_mensaje_publicado_no_lleva_las_fechas(self):
        mensaje = OdooPublisher('cliente', self.env)._build_message_from_odoo(self.partner)
        for nesto_field in CAMPOS:
            self.assertNotIn(nesto_field, mensaje)
        # El resto del mensaje sigue construyéndose igual
        self.assertEqual(mensaje['Cliente'], 'CLI_FECHAS_001')
        self.assertEqual(mensaje['Nombre'], 'Cliente Fechas')


@tagged('post_install', '-at_install', 'nesto_sync')
class TestFechasEnLaFicha(TransactionCase):
    """Recorrido completo: mensaje de Nesto → ficha de Odoo."""

    def setUp(self):
        super().setUp()
        self.config = ENTITY_CONFIGS['cliente']
        self.service = GenericEntityService(self.env, self.config, test_mode=True)
        self.processor = GenericEntityProcessor(self.env, self.config)
        self.partner = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente Recorrido', 'cliente_externo': 'CLI_FECHAS_002', 'contacto_externo': '0',
            'is_company': True, 'type': 'invoice',
        })

    def _procesar(self, message):
        valores = self.processor.process(message)['parent']
        self.service._update_record(self.partner, valores)
        self.partner.invalidate_recordset(list(CAMPOS.values()))

    def test_las_fechas_llegan_a_la_ficha_y_un_parcial_no_las_borra(self):
        self._procesar({
            'Cliente': 'CLI_FECHAS_002', 'Contacto': '0', 'ClientePrincipal': True,
            'Nombre': 'Cliente Recorrido',
            'FechaPrimerPresupuesto': '2026-01-15',
            'FechaPrimerPedido': '2026-02-20',
            'FechaUltimoPedido': '2026-09-01',
        })
        self.assertEqual(self.partner.fecha_primer_presupuesto, date(2026, 1, 15))
        self.assertEqual(self.partner.fecha_primer_pedido, date(2026, 2, 20))
        self.assertEqual(self.partner.fecha_ultimo_pedido, date(2026, 9, 1))

        # Un mensaje que solo cambia el nombre no puede llevarse las fechas por delante
        self._procesar({
            'Cliente': 'CLI_FECHAS_002', 'Contacto': '0', 'ClientePrincipal': True,
            'Nombre': 'Cliente Recorrido Renombrado',
        })
        self.assertEqual(self.partner.fecha_primer_presupuesto, date(2026, 1, 15))
        self.assertEqual(self.partner.fecha_primer_pedido, date(2026, 2, 20))
        self.assertEqual(self.partner.fecha_ultimo_pedido, date(2026, 9, 1))

    def test_un_null_si_vacia_la_fecha(self):
        self._procesar({
            'Cliente': 'CLI_FECHAS_002', 'Contacto': '0', 'ClientePrincipal': True,
            'FechaUltimoPedido': '2026-09-01',
        })
        self.assertEqual(self.partner.fecha_ultimo_pedido, date(2026, 9, 1))

        self._procesar({
            'Cliente': 'CLI_FECHAS_002', 'Contacto': '0', 'ClientePrincipal': True,
            'FechaUltimoPedido': None,
        })
        self.assertIs(self.partner.fecha_ultimo_pedido, False)
