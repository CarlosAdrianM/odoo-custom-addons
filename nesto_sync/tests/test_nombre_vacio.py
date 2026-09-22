"""
Tests del Nombre vacío (issue #19)

`Nombre` es required y tenía default, pero el default solo se aplicaba cuando
el valor era None. Nesto manda la cadena vacía, así que no se aplicaba y se
lanzaba `ValueError: Campo requerido faltante: Nombre`, con lo que se perdía el
mensaje ENTERO. El 18/09 había 91 entidades atascadas por esto: 46 direcciones
de entrega, 11 personas de contacto y 34 productos que YA EXISTÍAN en Odoo y
perdían stock, familia y kit por un campo que Odoo ya tenía.
"""

from odoo.tests import TransactionCase

from ..core.entity_registry import EntityRegistry

NOMBRE_POR_DEFECTO_PRODUCTO = '<Nombre producto no proporcionado>'


class TestNombreVacioEnClientes(TransactionCase):

    def setUp(self):
        super().setUp()
        registry = EntityRegistry()
        self.processor = registry.get_processor('cliente', self.env)
        self.service = registry.get_service('cliente', self.env, test_mode=True)

        self.principal = self.env['res.partner'].with_context(skip_sync=True).create({
            'name': 'EMPRESA PRINCIPAL S.L.',
            'cliente_externo': '17410',
            'contacto_externo': '0',
            'is_company': True,
            'type': 'invoice',
        })

    def _sincronizar(self, mensaje):
        self.service.create_or_update_contact(self.processor.process(mensaje))
        return self.env['res.partner'].with_context(active_test=False).search([
            ('cliente_externo', '=', mensaje['Cliente']),
            ('contacto_externo', '=', mensaje['Contacto']),
            ('persona_contacto_externa', '=', False),
        ])

    def test_direccion_de_entrega_nueva_sin_nombre_entra(self):
        """Se queda sin nombre: Odoo enseña el del padre (issue #19)"""
        direccion = self._sincronizar({
            'Cliente': '17410',
            'Contacto': '2',
            'ClientePrincipal': False,
            'Nombre': '',
            'Direccion': 'Calle del Almacén 5',
            'Estado': 1,
        })

        self.assertEqual(len(direccion), 1, "La dirección tiene que entrar en Odoo")
        self.assertFalse(direccion.name)
        self.assertEqual(direccion.street, 'Calle del Almacén 5')
        self.assertEqual(direccion.parent_id, self.principal)

    def test_solo_espacios_cuenta_como_vacio(self):
        direccion = self._sincronizar({
            'Cliente': '17410',
            'Contacto': '3',
            'ClientePrincipal': False,
            'Nombre': '   ',
            'Direccion': 'Calle del Almacén 6',
            'Estado': 1,
        })

        self.assertEqual(len(direccion), 1)
        self.assertFalse(direccion.name)

    def test_actualizar_con_nombre_vacio_no_pisa_el_que_hay(self):
        self._sincronizar({
            'Cliente': '17410',
            'Contacto': '4',
            'ClientePrincipal': False,
            'Nombre': 'Almacén Norte',
            'Direccion': 'Calle del Almacén 7',
            'Estado': 1,
        })

        direccion = self._sincronizar({
            'Cliente': '17410',
            'Contacto': '4',
            'ClientePrincipal': False,
            'Nombre': '',
            'Direccion': 'Calle del Almacén 8',
            'Estado': 1,
        })

        self.assertEqual(direccion.name, 'Almacén Norte',
                         "El nombre que ya estaba en Odoo no se toca")
        self.assertEqual(direccion.street, 'Calle del Almacén 8',
                         "Y el resto del mensaje sí entra")

    def test_un_nombre_de_verdad_sigue_entrando(self):
        direccion = self._sincronizar({
            'Cliente': '17410',
            'Contacto': '5',
            'ClientePrincipal': False,
            'Nombre': 'Almacén Sur',
            'Estado': 1,
        })

        self.assertEqual(direccion.name, 'Almacén Sur')


class TestNombreVacioEnPersonasDeContacto(TransactionCase):

    def setUp(self):
        super().setUp()
        registry = EntityRegistry()
        self.processor = registry.get_processor('cliente', self.env)
        self.service = registry.get_service('cliente', self.env, test_mode=True)

    def _sincronizar(self, personas):
        mensaje = {
            'Cliente': '28676',
            'Contacto': '0',
            'ClientePrincipal': True,
            'Nombre': 'CLIENTE CON PERSONAS SIN NOMBRE',
            'Estado': 1,
            'PersonasContacto': personas,
        }
        self.service.create_or_update_contact(self.processor.process(mensaje))
        return self.env['res.partner'].with_context(active_test=False).search([
            ('cliente_externo', '=', '28676'),
            ('parent_id', '=', False),
        ])

    def _personas(self):
        return self.env['res.partner'].with_context(active_test=False).search([
            ('cliente_externo', '=', '28676'),
            ('persona_contacto_externa', '!=', False),
        ])

    def test_sin_nombre_pero_con_correo_se_usa_el_correo(self):
        cliente = self._sincronizar([
            {'Id': '1', 'Nombre': None, 'CorreoElectronico': 'compras@ejemplo.es'},
        ])

        self.assertEqual(cliente.name, 'CLIENTE CON PERSONAS SIN NOMBRE')
        persona = self._personas()
        self.assertEqual(len(persona), 1)
        self.assertEqual(persona.name, 'compras@ejemplo.es')

    def test_sin_nombre_ni_correo_se_usa_el_cargo(self):
        self._sincronizar([
            {'Id': '2', 'Nombre': '', 'Cargo': 5},  # Gerente
        ])

        persona = self._personas()
        self.assertEqual(len(persona), 1)
        self.assertEqual(persona.name, 'Gerente')

    def test_sin_nada_se_deja_fuera_pero_el_cliente_entra(self):
        cliente = self._sincronizar([
            {'Id': '3', 'Nombre': None},
        ])

        self.assertEqual(len(cliente), 1, "El cliente tiene que entrar igualmente")
        self.assertEqual(cliente.name, 'CLIENTE CON PERSONAS SIN NOMBRE')
        self.assertFalse(self._personas(), "La persona sin nada se deja fuera")

    def test_una_persona_sin_nombre_no_arrastra_a_las_demas(self):
        self._sincronizar([
            {'Id': '4', 'Nombre': None},
            {'Id': '5', 'Nombre': 'Ángela', 'CorreoElectronico': 'angela@ejemplo.es'},
        ])

        personas = self._personas()
        self.assertEqual(len(personas), 1)
        self.assertEqual(personas.name, 'Ángela')

    def test_actualizar_con_nombre_vacio_no_pisa_el_que_hay(self):
        self._sincronizar([
            {'Id': '6', 'Nombre': 'Ángela', 'CorreoElectronico': 'angela@ejemplo.es'},
        ])

        self._sincronizar([
            {'Id': '6', 'Nombre': '', 'CorreoElectronico': 'angela.nueva@ejemplo.es'},
        ])

        persona = self._personas()
        self.assertEqual(persona.name, 'Ángela',
                         "El nombre que ya estaba en Odoo no se toca")
        self.assertEqual(persona.email, 'angela.nueva@ejemplo.es',
                         "Y el resto del mensaje sí entra")


class TestNombreVacioEnProductos(TransactionCase):

    def setUp(self):
        super().setUp()
        registry = EntityRegistry()
        self.processor = registry.get_processor('producto', self.env)
        self.service = registry.get_service('producto', self.env, test_mode=True)

    def _sincronizar(self, mensaje):
        self.service.create_or_update_contact(self.processor.process(mensaje))
        return self.env['product.template'].with_context(active_test=False).search([
            ('producto_externo', '=', mensaje['Producto'])
        ])

    def test_actualizar_un_producto_con_nombre_vacio_no_lo_renombra(self):
        """Los 34 productos de la DLQ: ya existen y pierden la actualización entera"""
        self.env['product.template'].with_context(skip_sync=True).create({
            'name': 'Crema hidratante 200 ml',
            'producto_externo': '45211',
            'type': 'product',
        })

        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '45211',
            'Nombre': '',
            'CodigoBarras': '8437017506386',
            'Estado': 1,
        })

        self.assertEqual(producto.name, 'Crema hidratante 200 ml',
                         "El nombre que ya estaba en Odoo no se toca")
        self.assertEqual(producto.barcode, '8437017506386',
                         "Y el resto del mensaje sí entra")

    def test_un_producto_nuevo_sin_nombre_usa_el_default(self):
        """product.template.name es required a nivel de campo: no puede ir vacío"""
        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '45999',
            'Nombre': '',
            'Estado': 1,
        })

        self.assertEqual(len(producto), 1, "El producto tiene que entrar en Odoo")
        self.assertEqual(producto.name, NOMBRE_POR_DEFECTO_PRODUCTO)

    def test_un_nombre_de_verdad_sigue_entrando(self):
        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '45998',
            'Nombre': 'Champú anticaída',
            'Estado': 1,
        })

        self.assertEqual(producto.name, 'Champú anticaída')
