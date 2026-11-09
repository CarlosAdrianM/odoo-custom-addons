"""Origen del cliente y consentimiento de comunicaciones (issue #43, NestoAPI#623).

Origen, FechaOrigen y AceptaComunicaciones los manda solo el importador de leads de
Nesto, una vez, en el contacto principal. Un null no vacía nada y nunca vuelven a Nesto.
"""
import copy
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.nesto_sync.config.entity_configs import ENTITY_CONFIGS
from odoo.addons.nesto_sync.core.generic_processor import GenericEntityProcessor
from odoo.addons.nesto_sync.core.generic_service import GenericEntityService
from odoo.addons.nesto_sync.core.odoo_publisher import OdooPublisher
from odoo.addons.nesto_sync.transformers.field_transformers import FieldTransformerRegistry

CAMPOS = {
    'Origen': 'origen_cliente',
    'FechaOrigen': 'fecha_origen',
    'AceptaComunicaciones': 'acepta_comunicaciones',
}

# Mensaje de ejemplo que pasó NestoAPI en la issue #43 (datos inventados)
MENSAJE_META = {
    "Cliente": "99999", "Contacto": "0", "ClientePrincipal": True,
    "Nombre": "MARÍA EJEMPLO PRUEBA", "Nif": None, "CodigoPostal": "28001",
    "Poblacion": "MADRID", "Provincia": "MADRID", "Telefono": "600000000",
    "Comentarios": "Lead de Meta (Instagram) 05/11 21:48: tengo un centro de estética; "
                   "solicita: una demostración de harmonia. No acepta correos comerciales.",
    "Vendedor": "LHY", "Estado": 5,
    "PersonasContacto": [{"Id": 1, "Nombre": "MARÍA EJEMPLO PRUEBA",
                          "CorreoElectronico": "maria@example.com", "Telefonos": "600000000"}],
    "Origen": "META-HARMONIA-0926", "FechaOrigen": "2026-11-05T21:48:00",
    "AceptaComunicaciones": False, "Tabla": "Clientes", "Source": "Nesto",
}


def _processor():
    env = MagicMock()
    env.user.company_id.id = 1
    return GenericEntityProcessor(env, ENTITY_CONFIGS['cliente'])


def _transformar(nombre, valor, campo):
    return FieldTransformerRegistry.get(nombre).transform(valor, {'mapping': {'odoo_field': campo}})


class TestTransformersOrigen(unittest.TestCase):

    def test_fecha_sin_zona_es_hora_de_madrid(self):
        # 05/11 está en horario de invierno (UTC+1)
        self.assertEqual(_transformar('fecha_hora_madrid', '2026-11-05T21:48:00', 'f'),
                         {'f': datetime(2026, 11, 5, 20, 48)})
        # En verano, UTC+2
        self.assertEqual(_transformar('fecha_hora_madrid', '2026-07-01T10:00:00', 'f'),
                         {'f': datetime(2026, 7, 1, 8, 0)})

    def test_fecha_con_zona_se_respeta(self):
        self.assertEqual(_transformar('fecha_hora_madrid', '2026-11-05T21:48:00Z', 'f'),
                         {'f': datetime(2026, 11, 5, 21, 48)})
        self.assertEqual(_transformar('fecha_hora_madrid', '2026-11-05T21:48:00.123+01:00', 'f'),
                         {'f': datetime(2026, 11, 5, 20, 48)})

    def test_fecha_null_no_toca(self):
        self.assertEqual(_transformar('fecha_hora_madrid', None, 'f'), {})
        self.assertEqual(_transformar('fecha_hora_madrid', '', 'f'), {})

    def test_fecha_formato_desconocido_falla(self):
        with self.assertRaises(ValueError):
            _transformar('fecha_hora_madrid', '05/11/2026 21:48', 'f')

    def test_acepta(self):
        self.assertEqual(_transformar('acepta_comunicaciones', True, 'a'), {'a': 'si'})
        self.assertEqual(_transformar('acepta_comunicaciones', False, 'a'), {'a': 'no'})
        self.assertEqual(_transformar('acepta_comunicaciones', 'false', 'a'), {'a': 'no'})
        self.assertEqual(_transformar('acepta_comunicaciones', None, 'a'), {})

    def test_acepta_valor_raro_falla(self):
        with self.assertRaises(ValueError):
            _transformar('acepta_comunicaciones', 'quizás', 'a')

    def test_origen_null_no_toca(self):
        self.assertEqual(_transformar('sin_vaciar', None, 'o'), {})
        self.assertEqual(_transformar('sin_vaciar', '  ', 'o'), {})
        self.assertEqual(_transformar('sin_vaciar', ' META-HARMONIA-0926 ', 'o'),
                         {'o': 'META-HARMONIA-0926'})


class TestMapeoOrigen(unittest.TestCase):

    def setUp(self):
        self.processor = _processor()

    def test_el_mensaje_de_ejemplo_trae_los_tres(self):
        valores = self.processor._build_values(copy.deepcopy(MENSAJE_META))
        self.assertEqual(valores['origen_cliente'], 'META-HARMONIA-0926')
        self.assertEqual(valores['fecha_origen'], datetime(2026, 11, 5, 20, 48))
        self.assertEqual(valores['acepta_comunicaciones'], 'no')
        # Estado 5 «primera visita» entra activo
        self.assertIs(valores['active'], True)

    def test_mensaje_normal_no_los_toca(self):
        mensaje = {k: v for k, v in MENSAJE_META.items() if k not in CAMPOS}
        valores = self.processor._build_values(mensaje)
        for campo in CAMPOS.values():
            self.assertNotIn(campo, valores)

    def test_nulls_no_los_tocan(self):
        mensaje = dict(MENSAJE_META, Origen=None, FechaOrigen=None, AceptaComunicaciones=None)
        valores = self.processor._build_values(mensaje)
        for campo in CAMPOS.values():
            self.assertNotIn(campo, valores)


class TestOrigenNoVuelveANesto(TransactionCase):

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('nesto_sync.google_project_id', 'test-project')
        icp.set_param('nesto_sync.pubsub_provider', 'google_pubsub')
        self.partner = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente Origen', 'cliente_externo': 'CLI_ORIGEN_001', 'contacto_externo': '0',
            'is_company': True, 'type': 'invoice',
            'origen_cliente': 'META-HARMONIA-0926', 'fecha_origen': datetime(2026, 11, 5, 20, 48),
            'acepta_comunicaciones': 'si',
        })

    def test_el_mapeo_inverso_inferido_los_excluye(self):
        inverso = OdooPublisher('cliente', self.env)._infer_reverse_mappings()
        for odoo_field in CAMPOS.values():
            self.assertNotIn(odoo_field, inverso)

    def test_el_mensaje_publicado_no_los_lleva(self):
        mensaje = OdooPublisher('cliente', self.env)._build_message_from_odoo(self.partner)
        for nesto_field in CAMPOS:
            self.assertNotIn(nesto_field, mensaje)
        self.assertEqual(mensaje['Cliente'], 'CLI_ORIGEN_001')


@tagged('post_install', '-at_install', 'nesto_sync')
class TestOrigenEnLaFicha(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = ENTITY_CONFIGS['cliente']
        self.service = GenericEntityService(self.env, self.config, test_mode=True)
        self.processor = GenericEntityProcessor(self.env, self.config)
        self.partner = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente Recorrido', 'cliente_externo': 'CLI_ORIGEN_002', 'contacto_externo': '0',
            'is_company': True, 'type': 'invoice',
        })

    def _procesar(self, message):
        valores = self.processor.process(message)['parent']
        self.service._update_record(self.partner, valores)
        self.partner.invalidate_recordset(list(CAMPOS.values()))

    def test_llegan_y_un_mensaje_normal_o_con_nulls_no_los_borra(self):
        base = {'Cliente': 'CLI_ORIGEN_002', 'Contacto': '0', 'ClientePrincipal': True}
        self._procesar(dict(base, Origen='META-HARMONIA-0926',
                            FechaOrigen='2026-11-05T21:48:00', AceptaComunicaciones=True))
        self.assertEqual(self.partner.origen_cliente, 'META-HARMONIA-0926')
        self.assertEqual(self.partner.fecha_origen, datetime(2026, 11, 5, 20, 48))
        self.assertEqual(self.partner.acepta_comunicaciones, 'si')

        self._procesar(dict(base, Nombre='Cliente Renombrado'))
        self._procesar(dict(base, Origen=None, FechaOrigen=None, AceptaComunicaciones=None))
        self.assertEqual(self.partner.origen_cliente, 'META-HARMONIA-0926')
        self.assertEqual(self.partner.fecha_origen, datetime(2026, 11, 5, 20, 48))
        self.assertEqual(self.partner.acepta_comunicaciones, 'si')

        # Retirar el consentimiento sí se escribe
        self._procesar(dict(base, AceptaComunicaciones=False))
        self.assertEqual(self.partner.acepta_comunicaciones, 'no')
