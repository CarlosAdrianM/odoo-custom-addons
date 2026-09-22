"""
Tests del filtrado de CodigoBarras (issue #21)

Un código de barras repetido o basura rechazaba el mensaje ENTERO por la
restricción de unicidad de product.product.barcode: el producto no se creaba ni
se actualizaba y el mensaje acababa en la DLQ (108 productos el 18/09, y 26
kits detrás porque sus componentes eran de esos).
"""

from odoo.tests import TransactionCase

from ..core.entity_registry import EntityRegistry
from ..transformers.field_transformers import FieldTransformerRegistry


class TestCodigoBarrasTransformer(TransactionCase):
    """El transformer por su cuenta, sin pasar por el processor"""

    def setUp(self):
        super().setUp()
        self.transformer = FieldTransformerRegistry.get('codigo_barras')

    def _transformar(self, valor, producto='P1'):
        return self.transformer.transform(
            valor, {'env': self.env, 'nesto_data': {'Producto': producto}}
        )

    def test_ean13_valido_y_libre_se_escribe(self):
        self.assertEqual(self._transformar('8437017506386'), {'barcode': '8437017506386'})

    def test_ean8_upc_y_gtin14_son_validos(self):
        for codigo in ('80870296', '123456789012', '12345678901234'):
            with self.subTest(codigo=codigo):
                self.assertEqual(self._transformar(codigo), {'barcode': codigo})

    def test_codigos_basura_de_nesto_se_vacian(self):
        """"0" y "1" se usan en Nesto como «sin código»"""
        for codigo in ('0', '1', '00', '99'):
            with self.subTest(codigo=codigo):
                self.assertEqual(self._transformar(codigo), {'barcode': False})

    def test_vacio_y_nulo_se_vacian(self):
        for valor in (None, '', '   '):
            with self.subTest(valor=valor):
                self.assertEqual(self._transformar(valor), {'barcode': False})

    def test_con_letras_o_longitud_rara_se_vacia(self):
        # 11 y 15 dígitos no son ninguna de las longitudes válidas
        for codigo in ('ABC12345', '84370175063', '843701750638612', '84370-17506'):
            with self.subTest(codigo=codigo):
                self.assertEqual(self._transformar(codigo), {'barcode': False})

    def test_numero_en_vez_de_texto(self):
        """Nesto puede mandarlo como número"""
        self.assertEqual(self._transformar(8437017506386), {'barcode': '8437017506386'})
        self.assertEqual(self._transformar(1), {'barcode': False})

    def test_su_propio_codigo_no_es_un_duplicado(self):
        self.env['product.template'].create({
            'name': 'Producto 1',
            'producto_externo': 'P1',
            'barcode': '8437017506386',
        })
        self.assertEqual(self._transformar('8437017506386', 'P1'), {'barcode': '8437017506386'})

    def test_duplicado_de_otro_producto_no_toca_el_barcode(self):
        """No se devuelve barcode: lo que Odoo ya tenga se queda como está"""
        self.env['product.template'].create({
            'name': 'Producto 1',
            'producto_externo': 'P1',
            'barcode': '8437017506386',
        })
        self.assertEqual(self._transformar('8437017506386', 'P2'), {})

    def test_duplicado_aunque_el_dueno_este_archivado(self):
        """La restricción de unicidad es de la tabla y no mira el archivado"""
        dueno = self.env['product.template'].create({
            'name': 'Producto 1',
            'producto_externo': 'P1',
            'barcode': '8437017506386',
        })
        dueno.with_context(skip_sync=True).write({'active': False})

        self.assertEqual(self._transformar('8437017506386', 'P2'), {})


class TestCodigoBarrasMensajeCompleto(TransactionCase):
    """El mensaje entero: lo que antes acababa en la DLQ"""

    def setUp(self):
        super().setUp()
        registry = EntityRegistry()
        self.processor = registry.get_processor('producto', self.env)
        self.service = registry.get_service('producto', self.env, test_mode=True)

    def _sincronizar(self, mensaje):
        self.service.create_or_update_contact(self.processor.process(mensaje))
        return self.env['product.template'].search([
            ('producto_externo', '=', mensaje['Producto'])
        ])

    def test_producto_nuevo_con_ean_repetido_entra_sin_codigo(self):
        self.env['product.template'].create({
            'name': 'El que llegó primero',
            'producto_externo': '44604',
            'barcode': '4779044932412',
        })

        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '44605',
            'Nombre': 'El que llegaba después',
            'CodigoBarras': '4779044932412',
            'Estado': 1,
        })

        self.assertEqual(len(producto), 1, "El producto tiene que entrar en Odoo")
        self.assertEqual(producto.name, 'El que llegaba después')
        self.assertFalse(producto.barcode)

    def test_producto_nuevo_con_codigo_basura_entra_sin_codigo(self):
        self.env['product.template'].create({
            'name': 'El que se quedó el 1',
            'producto_externo': '39918',
            'barcode': '1',
        })

        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '37496',
            'Nombre': 'Otro sin código en Nesto',
            'CodigoBarras': '1',
            'Estado': 1,
        })

        self.assertEqual(len(producto), 1)
        self.assertFalse(producto.barcode)

    def test_el_codigo_basura_se_limpia_en_la_siguiente_sincronizacion(self):
        """El "1" de 39918 se va solo cuando Nesto vuelva a publicarlo"""
        self.env['product.template'].create({
            'name': 'El que se quedó el 1',
            'producto_externo': '39918',
            'barcode': '1',
        })

        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '39918',
            'Nombre': 'El que se quedó el 1',
            'CodigoBarras': '1',
            'Estado': 1,
        })

        self.assertFalse(producto.barcode)

    def test_una_actualizacion_con_ean_ajeno_no_borra_el_codigo_bueno(self):
        self.env['product.template'].create({
            'name': 'Dueño del EAN',
            'producto_externo': '45260',
            'barcode': '8436566603249',
        })
        self.env['product.template'].create({
            'name': 'Con su propio EAN',
            'producto_externo': '45259',
            'barcode': '8436566603270',
        })

        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '45259',
            'Nombre': 'Con su propio EAN',
            'CodigoBarras': '8436566603249',  # el de 45260
            'Estado': 1,
        })

        self.assertEqual(producto.barcode, '8436566603270',
                         "Un duplicado en Nesto no debe borrar el código bueno de Odoo")

    def test_codigo_valido_y_libre_se_guarda(self):
        producto = self._sincronizar({
            'Tabla': 'Productos',
            'Producto': '12345',
            'Nombre': 'Producto normal',
            'CodigoBarras': '8437017506386',
            'Estado': 1,
        })

        self.assertEqual(producto.barcode, '8437017506386')
