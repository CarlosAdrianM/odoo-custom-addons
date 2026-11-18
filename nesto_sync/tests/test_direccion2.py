"""Dirección 2 y tipo de lugar de los clientes (NestoAPI#874).

Direccion2 va a street2 y TipoLugar a tipo_lugar. Ausente o null = no modificar,
"" = vaciar. Solo entran: Odoo no los publica hacia Nesto.
"""
import copy
import unittest
from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.nesto_sync.config.entity_configs import ENTITY_CONFIGS
from odoo.addons.nesto_sync.core.generic_processor import GenericEntityProcessor
from odoo.addons.nesto_sync.core.generic_service import GenericEntityService
from odoo.addons.nesto_sync.core.odoo_publisher import OdooPublisher
from odoo.addons.nesto_sync.transformers.field_transformers import FieldTransformerRegistry

CAMPOS = {'Direccion2': 'street2', 'TipoLugar': 'tipo_lugar'}

# Datos inventados
MENSAJE = {
    "Cliente": "99998", "Contacto": "0", "ClientePrincipal": True,
    "Nombre": "CENTRO EJEMPLO", "Direccion": "C/ DE LA PRUEBA, 13", "CodigoPostal": "28001",
    "Poblacion": "MADRID", "Provincia": "MADRID", "Telefono": "600000000", "Estado": 0,
    "Direccion2": "LOCAL 6 · RÓTULO: EL EJEMPLO", "TipoLugar": "Local",
    "Tabla": "Clientes", "Source": "Nesto",
}


def _processor():
    env = MagicMock()
    env.user.company_id.id = 1
    return GenericEntityProcessor(env, ENTITY_CONFIGS['cliente'])


def _transformar(nombre, valor):
    return FieldTransformerRegistry.get(nombre).transform(valor, {'mapping': {'odoo_field': 'c'}})


class TestTransformersDireccion2(unittest.TestCase):

    def test_texto_null_no_toca_y_vacio_vacia(self):
        self.assertEqual(_transformar('texto_opcional', None), {})
        self.assertEqual(_transformar('texto_opcional', ''), {'c': False})
        self.assertEqual(_transformar('texto_opcional', '   '), {'c': False})
        self.assertEqual(_transformar('texto_opcional', ' 1º D '), {'c': '1º D'})

    def test_tipo_lugar(self):
        self.assertEqual(_transformar('tipo_lugar', None), {})
        self.assertEqual(_transformar('tipo_lugar', ''), {'c': False})
        self.assertEqual(_transformar('tipo_lugar', 'Piso'), {'c': 'Piso'})
        self.assertEqual(_transformar('tipo_lugar', ' NAVE '), {'c': 'Nave'})

    def test_tipo_lugar_desconocido_no_toca(self):
        self.assertEqual(_transformar('tipo_lugar', 'Garaje'), {})


class TestMapeoDireccion2(unittest.TestCase):

    def setUp(self):
        self.processor = _processor()

    def test_el_mensaje_trae_los_dos(self):
        valores = self.processor._build_values(copy.deepcopy(MENSAJE))
        self.assertEqual(valores['street'], 'C/ DE LA PRUEBA, 13')
        self.assertEqual(valores['street2'], 'LOCAL 6 · RÓTULO: EL EJEMPLO')
        self.assertEqual(valores['tipo_lugar'], 'Local')

    def test_ausentes_o_null_no_se_tocan(self):
        sin_ellos = {k: v for k, v in MENSAJE.items() if k not in CAMPOS}
        con_nulls = dict(MENSAJE, Direccion2=None, TipoLugar=None)
        for mensaje in (sin_ellos, con_nulls):
            valores = self.processor._build_values(mensaje)
            for campo in CAMPOS.values():
                self.assertNotIn(campo, valores)


class TestDireccion2NoVuelveANesto(TransactionCase):

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('nesto_sync.google_project_id', 'test-project')
        # La copia de pruebas tiene el publicador desactivado: aquí se fija el de verdad
        icp.set_param('nesto_sync.event_publisher', 'google_pubsub')
        self.partner = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente Dirección 2', 'cliente_externo': 'CLI_DIR2_001', 'contacto_externo': '0',
            'is_company': True, 'type': 'invoice', 'street': 'C/ de la Prueba, 13',
            'street2': '1º D', 'tipo_lugar': 'Piso',
        })

    def test_el_mapeo_inverso_inferido_los_excluye(self):
        inverso = OdooPublisher('cliente', self.env)._infer_reverse_mappings()
        for odoo_field in CAMPOS.values():
            self.assertNotIn(odoo_field, inverso)

    def test_el_mensaje_publicado_no_los_lleva(self):
        mensaje = OdooPublisher('cliente', self.env)._build_message_from_odoo(self.partner)
        for nesto_field in CAMPOS:
            self.assertNotIn(nesto_field, mensaje)
        self.assertEqual(mensaje['Direccion'], 'C/ de la Prueba, 13')


@tagged('post_install', '-at_install', 'nesto_sync')
class TestDireccion2EnLaFicha(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = ENTITY_CONFIGS['cliente']
        self.service = GenericEntityService(self.env, self.config, test_mode=True)
        self.processor = GenericEntityProcessor(self.env, self.config)
        self.partner = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente Recorrido', 'cliente_externo': 'CLI_DIR2_002', 'contacto_externo': '0',
            'is_company': True, 'type': 'invoice',
        })

    def _procesar(self, message):
        valores = self.processor.process(message)['parent']
        self.service._update_record(self.partner, valores)
        self.partner.invalidate_recordset(list(CAMPOS.values()))

    def test_llegan_un_null_no_los_borra_y_un_vacio_si(self):
        base = {'Cliente': 'CLI_DIR2_002', 'Contacto': '0', 'ClientePrincipal': True}
        self._procesar(dict(base, Direccion2='3º BD', TipoLugar='Piso'))
        self.assertEqual(self.partner.street2, '3º BD')
        self.assertEqual(self.partner.tipo_lugar, 'Piso')

        self._procesar(dict(base, Nombre='Cliente Renombrado'))
        self._procesar(dict(base, Direccion2=None, TipoLugar=None))
        self.assertEqual(self.partner.street2, '3º BD')
        self.assertEqual(self.partner.tipo_lugar, 'Piso')

        self._procesar(dict(base, Direccion2='', TipoLugar=''))
        self.assertFalse(self.partner.street2)
        self.assertFalse(self.partner.tipo_lugar)
