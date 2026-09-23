"""
Tests del país de los clientes (issue #30)

`_country` es un mapeo sintético: la clave no viene en el mensaje de Nesto, la
resuelve el transformer `spain_country`. Desde aa8c65b (issue #3, mensajes
parciales) el processor salía antes de tiempo si la clave no estaba en el
mensaje, y como `_country` no está NUNCA, `country_id` no se escribía jamás.

El resultado eran fichas con provincia española y sin país: 2.541 clientes en
producción, todos creados después de aa8c65b. Antes de esa fecha, ninguno.

Ojo al leer estos tests: comprueban también que los campos que SÍ son de Nesto
siguen sin escribirse cuando no vienen en el mensaje. Ese es el comportamiento
de la issue #3 y el arreglo del país no puede llevárselo por delante.
"""

from odoo.tests import TransactionCase

from ..core.entity_registry import EntityRegistry


class TestPaisEnClientes(TransactionCase):

    def setUp(self):
        super().setUp()
        registry = EntityRegistry()
        self.processor = registry.get_processor('cliente', self.env)
        self.service = registry.get_service('cliente', self.env, test_mode=True)
        self.espana = self.env.ref('base.es')

    def _sincronizar(self, mensaje):
        self.service.create_or_update_contact(self.processor.process(mensaje))
        return self.env['res.partner'].with_context(active_test=False).search([
            ('cliente_externo', '=', mensaje['Cliente']),
            ('contacto_externo', '=', mensaje['Contacto']),
            ('persona_contacto_externa', '=', False),
        ])

    def test_cliente_nuevo_entra_con_espana(self):
        cliente = self._sincronizar({
            'Cliente': '30001',
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'CLIENTE CON PAÍS S.L.',
            'Direccion': 'Calle Mayor 1',
            'Estado': 1,
        })

        self.assertEqual(len(cliente), 1)
        self.assertEqual(cliente.country_id, self.espana)

    def test_la_direccion_de_entrega_tambien(self):
        """No es solo el principal: cualquier contacto del cliente"""
        self._sincronizar({
            'Cliente': '30002',
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'CLIENTE PRINCIPAL S.L.',
            'Estado': 1,
        })

        direccion = self._sincronizar({
            'Cliente': '30002',
            'Contacto': '2',
            'ClientePrincipal': False,
            'Nombre': 'Almacén Norte',
            'Direccion': 'Calle del Almacén 5',
            'Estado': 1,
        })

        self.assertEqual(len(direccion), 1)
        self.assertEqual(direccion.country_id, self.espana)

    def test_un_mensaje_que_actualiza_tambien_pone_el_pais(self):
        """Los 2.541 de producción se arreglan solos cuando Nesto republique"""
        cliente = self._sincronizar({
            'Cliente': '30003',
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'CLIENTE SIN PAÍS S.L.',
            'Estado': 1,
        })
        cliente.with_context(skip_sync=True).write({'country_id': False})
        self.assertFalse(cliente.country_id)

        self._sincronizar({
            'Cliente': '30003',
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'CLIENTE SIN PAÍS S.L.',
            'Telefono': '912345678',
            'Estado': 1,
        })

        self.assertEqual(cliente.country_id, self.espana)


class TestPaisEnPersonasDeContacto(TransactionCase):

    def setUp(self):
        super().setUp()
        registry = EntityRegistry()
        self.processor = registry.get_processor('cliente', self.env)
        self.service = registry.get_service('cliente', self.env, test_mode=True)
        self.espana = self.env.ref('base.es')

    def test_la_persona_de_contacto_entra_con_espana(self):
        """El mapeo sintético está también en child_field_mappings"""
        self.service.create_or_update_contact(self.processor.process({
            'Cliente': '30004',
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'CLIENTE CON PERSONAS S.L.',
            'Estado': 1,
            'PersonasContacto': [{'Id': '1', 'Nombre': 'Ana Gómez', 'Cargo': 22}],
        }))

        persona = self.env['res.partner'].with_context(active_test=False).search([
            ('cliente_externo', '=', '30004'),
            ('persona_contacto_externa', '!=', False),
        ])

        self.assertEqual(len(persona), 1)
        self.assertEqual(persona.country_id, self.espana)


class TestElArregloNoRompeLosMensajesParciales(TransactionCase):
    """La issue #3 sigue en pie: lo que no viene de Nesto no se toca"""

    def setUp(self):
        super().setUp()
        registry = EntityRegistry()
        self.processor = registry.get_processor('cliente', self.env)

    def _valores_del_principal(self, cliente):
        """process() devuelve {'parent': ..., 'children': [...]}, no un dict plano"""
        return self.processor.process({
            'Cliente': cliente,
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'CLIENTE PARCIAL S.L.',
            'Estado': 1,
        })['parent']

    def test_un_campo_de_nesto_ausente_sigue_sin_aparecer(self):
        values = self._valores_del_principal('30005')

        self.assertNotIn('phone', values)
        self.assertNotIn('email', values)

    def test_pero_los_sinteticos_si(self):
        values = self._valores_del_principal('30006')

        self.assertIn('country_id', values)
        self.assertIn('company_id', values)
