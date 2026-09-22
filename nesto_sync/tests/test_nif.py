"""
Tests del NIF sin validar (issue #18)

Un cliente de Nesto cuyo NIF no pasaba la validación de base_vat no entraba en
Odoo: check_vat lanzaba ValidationError, el mensaje agotaba los reintentos y
acababa en la DLQ, y con él se perdía el cliente entero (dirección, vendedor,
fechas de compras…). El 18/09 había 177 entidades atascadas por esto.

Ojo al montar estos tests: base_vat solo valida un NIF español si el partner
tiene país. Los clientes de producción lo tienen, así que los de aquí se crean
con España puesta a mano; si no, check_vat no llega ni a mirar el NIF y el test
pasaría igual sin el arreglo.
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

from ..config.entity_configs import get_entity_config
from ..core.entity_registry import EntityRegistry
from ..core.generic_service import GenericEntityService

# NIF español mal formado: le falta un dígito
NIF_MALO = 'B1234567'
# NIF español correcto, con su letra de control
NIF_BUENO = 'B12345674'


class TestContextoDeEscritura(TransactionCase):
    """El contexto con el que se escribe todo lo que viene de Nesto"""

    def test_lleva_skip_sync_y_no_vat_validation(self):
        service = GenericEntityService(
            self.env, get_entity_config('cliente'), test_mode=True
        )

        self.assertEqual(
            service._contexto_de_escritura(),
            {'skip_sync': True, 'no_vat_validation': True}
        )

    def test_tambien_para_productos(self):
        """El mismo contexto vale para cualquier entidad: todo viene de Nesto"""
        service = GenericEntityService(
            self.env, get_entity_config('producto'), test_mode=True
        )

        self.assertTrue(service._contexto_de_escritura()['no_vat_validation'])


class TestNifQueNoValida(TransactionCase):
    """De punta a punta, con base_vat puesto"""

    def setUp(self):
        super().setUp()

        modulo = self.env['ir.module.module'].sudo().search([
            ('name', '=', 'base_vat')
        ], limit=1)
        if modulo.state != 'installed':
            self.skipTest(
                "base_vat no está instalado en esta base de datos: sin él no hay "
                "validación de NIF que saltarse. En producción y en desarrollo sí lo está."
            )

        self.espana = self.env.ref('base.es')

        registry = EntityRegistry()
        self.processor = registry.get_processor('cliente', self.env)
        self.service = registry.get_service('cliente', self.env, test_mode=True)

    def _crear_cliente(self, cliente_externo, vat=NIF_BUENO):
        """Un cliente como los de producción: con país, que es lo que hace que
        base_vat valide el NIF."""
        return self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'Cliente de prueba',
            'cliente_externo': cliente_externo,
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
            'country_id': self.espana.id,
            'vat': vat,
        })

    def _sincronizar(self, mensaje):
        self.service.create_or_update_contact(self.processor.process(mensaje))
        return self.env['res.partner'].search([
            ('cliente_externo', '=', mensaje['Cliente']),
            ('contacto_externo', '=', mensaje['Contacto']),
        ])

    def _mensaje(self, cliente_externo, nif, **extra):
        mensaje = {
            'Cliente': cliente_externo,
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'Cliente de prueba',
            'Nif': nif,
            'Estado': 1,
        }
        mensaje.update(extra)
        return mensaje

    def test_el_nif_malo_saltaria_sin_el_arreglo(self):
        """Control: sin el contexto, este mismo NIF tumba el write"""
        cliente = self._crear_cliente('NIF000')

        with self.assertRaises(ValidationError):
            cliente.with_context(skip_sync=True).write({'vat': NIF_MALO})
            cliente.flush_recordset()

    def test_nif_espanol_mal_formado_no_tira_el_cliente(self):
        cliente = self._crear_cliente('NIF001')

        actualizado = self._sincronizar(self._mensaje(
            'NIF001', NIF_MALO, Direccion='Calle de la Prueba 1', Poblacion='Madrid'
        ))

        self.assertEqual(actualizado, cliente)
        self.assertEqual(actualizado.vat, NIF_MALO)
        self.assertEqual(actualizado.street, 'Calle de la Prueba 1',
                         "Y con el NIF entra el resto de la ficha")

    def test_intracomunitario_mal_formado_tampoco(self):
        self._crear_cliente('NIF002')

        cliente = self._sincronizar(self._mensaje('NIF002', 'FR000000000'))

        self.assertEqual(cliente.vat, 'FR000000000')

    def test_un_cliente_nuevo_con_nif_malo_entra(self):
        """Sin ficha previa en Odoo: es el caso de los 69 clientes sin ficha"""
        cliente = self._sincronizar(self._mensaje('NIF003', NIF_MALO))

        self.assertEqual(len(cliente), 1)
        self.assertEqual(cliente.vat, NIF_MALO)

    def test_un_nif_bueno_sigue_entrando(self):
        self._crear_cliente('NIF004')

        cliente = self._sincronizar(self._mensaje('NIF004', NIF_BUENO))

        self.assertEqual(cliente.vat, NIF_BUENO)

    def test_editar_a_mano_en_odoo_sigue_validando(self):
        """El contexto solo se aplica a lo que entra por el service"""
        cliente = self._crear_cliente('NIF005')

        with self.assertRaises(ValidationError):
            cliente.write({'vat': NIF_MALO})
            cliente.flush_recordset()

    def test_el_nif_dudoso_queda_en_el_log(self):
        self._crear_cliente('NIF006')

        with self.assertLogs('odoo.addons.nesto_sync.core.generic_service', 'WARNING') as logs:
            self._sincronizar(self._mensaje('NIF006', NIF_MALO))

        self.assertTrue(
            any(NIF_MALO in linea and 'NIF006' in linea for linea in logs.output),
            f"El NIF dudoso tiene que quedar en el log para poder pasar la lista "
            f"a Nesto. Log: {logs.output}"
        )
