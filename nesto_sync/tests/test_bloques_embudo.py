"""Códigos de vendedor y estado, baja de boletín y bloques del embudo de reactivación.

Contrato acordado con NestoAPI (endpoint api/Clientes/Sync/Republicar): en todos los
campos nuevos, clave ausente o null = no tocar, y ninguno vuelve a Nesto.
"""
import copy
import unittest
from unittest.mock import MagicMock

from odoo.addons.nesto_sync.config.entity_configs import ENTITY_CONFIGS
from odoo.addons.nesto_sync.core.generic_processor import GenericEntityProcessor
from odoo.addons.nesto_sync.core.generic_service import GenericEntityService
from odoo.addons.nesto_sync.core.odoo_publisher import OdooPublisher

MENSAJE_BLOQUE = {
    "Cliente": "99998", "Contacto": "0", "ClientePrincipal": True,
    "Nombre": "CENTRO EJEMPLO", "CodigoPostal": "28001", "Poblacion": "MADRID",
    "Provincia": "MADRID", "Telefono": "600000001",
    "Vendedor": "NV", "VendedorEmail": None, "VendedorPeluqueria": "NV", "Estado": 0,
    "FechaUltimoPedido": "2023-02-01T00:00:00",
    "PersonasContacto": [
        {"Id": 1, "Nombre": "ANA EJEMPLO", "CorreoElectronico": "ana@example.com", "EnviarBoletin": True},
        {"Id": 2, "Nombre": "LUIS EJEMPLO", "CorreoElectronico": "luis@example.com", "EnviarBoletin": False},
        {"Id": 3, "Nombre": "SIN DATO", "CorreoElectronico": "otro@example.com"},
    ],
    "BloqueEmbudo": "NV-2026-11-01", "ResponsableEmbudoEmail": "tiendaonline@nuevavision.es",
    "ResponsableEmbudoTipo": "TiendaOnline", "Tabla": "Clientes", "Source": "Nesto",
}

CAMPOS_NUEVOS = ('vendedor_nesto', 'estado_nesto', 'vendedor_peluqueria_nesto', 'bloque_embudo',
                 'responsable_embudo_email', 'responsable_embudo_tipo', 'enviar_boletin')


def _procesar(mensaje):
    env = MagicMock()
    env.user.company_id.id = 1
    procesador = GenericEntityProcessor(env, ENTITY_CONFIGS['cliente'])
    # Como process(), sin los validadores (necesitan una base de datos de verdad)
    padre = procesador._build_values(mensaje, is_parent=True)
    hijos = procesador._process_children(mensaje, padre)
    padre, hijos = procesador._run_post_processors(padre, hijos, mensaje)
    return {'parent': padre, 'children': hijos}


class TestBloquesEmbudo(unittest.TestCase):

    def _valores(self, mensaje):
        resultado = _procesar(mensaje)
        return resultado['parent'], resultado['children']

    def test_mensaje_de_bloque(self):
        padre, hijos = self._valores(copy.deepcopy(MENSAJE_BLOQUE))
        self.assertEqual(padre['vendedor_nesto'], 'NV')
        self.assertEqual(padre['estado_nesto'], '0')
        self.assertTrue(padre['active'])
        self.assertEqual(padre['vendedor_peluqueria_nesto'], 'NV')
        self.assertEqual(padre['bloque_embudo'], 'NV-2026-11-01')
        self.assertEqual(padre['responsable_embudo_email'], 'tiendaonline@nuevavision.es')
        self.assertEqual(padre['responsable_embudo_tipo'], 'TiendaOnline')
        # VendedorEmail a null no toca el vendedor de Odoo (#25)
        self.assertNotIn('user_id', padre)
        self.assertEqual([h.get('enviar_boletin') for h in hijos], ['si', 'no', None])
        # Las personas no llevan los códigos del cliente
        self.assertNotIn('vendedor_nesto', hijos[0])

    def test_mensaje_normal_no_borra_el_bloque(self):
        mensaje = copy.deepcopy(MENSAJE_BLOQUE)
        for clave in ('BloqueEmbudo', 'ResponsableEmbudoEmail', 'ResponsableEmbudoTipo'):
            del mensaje[clave]
        mensaje['VendedorPeluqueria'] = None
        padre, _hijos = self._valores(mensaje)
        for campo in ('bloque_embudo', 'responsable_embudo_email', 'responsable_embudo_tipo',
                      'vendedor_peluqueria_nesto'):
            self.assertNotIn(campo, padre)

    def test_claves_a_null_no_tocan(self):
        mensaje = copy.deepcopy(MENSAJE_BLOQUE)
        mensaje.update({'BloqueEmbudo': None, 'ResponsableEmbudoEmail': None,
                        'ResponsableEmbudoTipo': '', 'Vendedor': None})
        mensaje['PersonasContacto'][0]['EnviarBoletin'] = None
        padre, hijos = self._valores(mensaje)
        for campo in ('bloque_embudo', 'responsable_embudo_email', 'responsable_embudo_tipo',
                      'vendedor_nesto'):
            self.assertNotIn(campo, padre)
        self.assertNotIn('enviar_boletin', hijos[0])

    def test_estado_anulado_se_guarda_y_archiva(self):
        mensaje = copy.deepcopy(MENSAJE_BLOQUE)
        mensaje['Estado'] = -1
        padre, _hijos = self._valores(mensaje)
        self.assertEqual(padre['estado_nesto'], '-1')
        self.assertFalse(padre['active'])

    def test_nada_vuelve_a_nesto(self):
        publicador = OdooPublisher.__new__(OdooPublisher)
        publicador.config = ENTITY_CONFIGS['cliente']
        inversos = set(publicador._infer_reverse_mappings()) | set(publicador._infer_reverse_child_mappings())
        for campo in CAMPOS_NUEVOS:
            self.assertNotIn(campo, inversos)


class TestIdentificadorNumerico(unittest.TestCase):
    """Un campo de texto que llega como número se compara como texto, sin romper."""

    def _distinto(self, actual, nuevo):
        servicio = GenericEntityService.__new__(GenericEntityService)
        registro = MagicMock()
        registro._fields = {'persona_contacto_externa': MagicMock(type='char')}
        return servicio._values_are_different('persona_contacto_externa', actual, nuevo, registro)

    def test_numero_contra_texto(self):
        self.assertFalse(self._distinto('1', 1))
        self.assertTrue(self._distinto('1', 2))
        self.assertFalse(self._distinto(False, None))
        self.assertTrue(self._distinto(False, 0))
