"""
Tests para sincronización de BOMs (Bills of Materials)

Tests unitarios para validar:
- Creación de BOMs desde ProductosKit
- Actualización de componentes
- Eliminación de BOMs
- Validación de componentes faltantes
- Detección de ciclos infinitos
- Soporte de múltiples formatos de datos
- Productos MTP (no vendibles)
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestBomSync(TransactionCase):
    """Tests para sincronización de BOMs"""

    def setUp(self):
        super(TestBomSync, self).setUp()

        # Crear productos de prueba
        self.product_kit = self.env['product.template'].create({
            'name': 'Kit de Prueba',
            'producto_externo': 'KIT001',
            'type': 'product',
        })

        self.component_1 = self.env['product.template'].create({
            'name': 'Componente 1',
            'producto_externo': 'COMP001',
            'type': 'product',
        })

        self.component_2 = self.env['product.template'].create({
            'name': 'Componente 2',
            'producto_externo': 'COMP002',
            'type': 'product',
        })

        self.component_3 = self.env['product.template'].create({
            'name': 'Componente 3',
            'producto_externo': 'COMP003',
            'type': 'product',
        })

        # Importar post-processor
        from ..transformers.post_processors import SyncProductBom
        self.bom_processor = SyncProductBom()

    def test_sync_bom_create_simple(self):
        """Test: Crear BOM con 2 componentes"""
        productos_kit = [
            {'ProductoId': 'COMP001', 'Cantidad': 2},
            {'ProductoId': 'COMP002', 'Cantidad': 1},
        ]

        # Sincronizar BOM
        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)

        # Verificar que se creó la BOM
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        self.assertEqual(len(bom), 1, "Debe existir 1 BOM")
        self.assertEqual(bom.type, 'normal', "BOM debe ser tipo 'normal'")
        self.assertEqual(len(bom.bom_line_ids), 2, "BOM debe tener 2 componentes")

        # Verificar cantidades
        line_1 = bom.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP001'
        )
        self.assertEqual(line_1.product_qty, 2, "Componente 1 debe tener cantidad 2")

        line_2 = bom.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP002'
        )
        self.assertEqual(line_2.product_qty, 1, "Componente 2 debe tener cantidad 1")

    def test_sync_bom_update_components(self):
        """Test: Actualizar componentes de BOM existente"""
        # Crear BOM inicial
        productos_kit_inicial = [
            {'ProductoId': 'COMP001', 'Cantidad': 2},
            {'ProductoId': 'COMP002', 'Cantidad': 1},
        ]
        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit_inicial)

        # Actualizar BOM (cambiar cantidades y componentes)
        productos_kit_nueva = [
            {'ProductoId': 'COMP001', 'Cantidad': 5},  # Cantidad cambiada
            {'ProductoId': 'COMP003', 'Cantidad': 2},  # Componente nuevo
        ]
        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit_nueva)

        # Verificar actualización
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        self.assertEqual(len(bom), 1, "Debe seguir existiendo solo 1 BOM")
        self.assertEqual(len(bom.bom_line_ids), 2, "BOM debe tener 2 componentes")

        # Verificar que COMP002 ya no está
        line_comp2 = bom.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP002'
        )
        self.assertEqual(len(line_comp2), 0, "COMP002 no debe estar en la BOM")

        # Verificar nueva cantidad de COMP001
        line_comp1 = bom.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP001'
        )
        self.assertEqual(line_comp1.product_qty, 5, "COMP001 debe tener cantidad 5")

    def test_sync_bom_delete_empty(self):
        """Test: Eliminar BOM cuando ProductosKit está vacío"""
        # Crear BOM inicial
        productos_kit = [
            {'ProductoId': 'COMP001', 'Cantidad': 2},
        ]
        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)

        # Verificar que existe
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        self.assertEqual(len(bom), 1, "Debe existir 1 BOM")

        # Enviar ProductosKit vacío
        self.bom_processor._sync_bom(self.env, self.product_kit, [])

        # Verificar que se eliminó
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        self.assertEqual(len(bom), 0, "BOM debe haberse eliminado")

    def test_sync_bom_missing_component(self):
        """Test: Error cuando falta un componente"""
        productos_kit = [
            {'ProductoId': 'COMP001', 'Cantidad': 2},
            {'ProductoId': 'COMP999', 'Cantidad': 1},  # No existe
        ]

        # Debe lanzar ValueError
        with self.assertRaises(ValueError) as cm:
            self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)

        self.assertIn('COMP999', str(cm.exception), "Error debe mencionar COMP999")
        self.assertIn('no encontrados', str(cm.exception).lower())

    def test_sync_bom_direct_cycle(self):
        """Test: Detectar ciclo directo (producto se contiene a sí mismo)"""
        productos_kit = [
            {'ProductoId': 'KIT001', 'Cantidad': 1},  # Se contiene a sí mismo
        ]

        # Debe lanzar ValueError
        with self.assertRaises(ValueError) as cm:
            self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)

        self.assertIn('ciclo', str(cm.exception).lower())

    def test_sync_bom_indirect_cycle(self):
        """Test: Detectar ciclo indirecto (A → B → A)"""
        # Crear producto B que contiene A
        product_b = self.env['product.template'].create({
            'name': 'Kit B',
            'producto_externo': 'KITB',
            'type': 'product',
        })

        # B contiene A
        productos_kit_b = [
            {'ProductoId': 'KIT001', 'Cantidad': 1},
        ]
        self.bom_processor._sync_bom(self.env, product_b, productos_kit_b)

        # Intentar que A contenga B (crearía ciclo A → B → A)
        productos_kit_a = [
            {'ProductoId': 'KITB', 'Cantidad': 1},
        ]

        # Debe lanzar ValueError por ciclo
        with self.assertRaises(ValueError) as cm:
            self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit_a)

        self.assertIn('ciclo', str(cm.exception).lower())

    def test_sync_bom_format_objects(self):
        """Test: Formato con objetos {ProductoId, Cantidad}"""
        productos_kit = [
            {'ProductoId': 'COMP001', 'Cantidad': 3},
            {'ProductoId': 'COMP002', 'Cantidad': 2},
        ]

        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)

        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        self.assertEqual(len(bom.bom_line_ids), 2, "Debe tener 2 componentes")

    def test_sync_bom_format_ids(self):
        """Test: Formato con array de IDs [41224, 41225]"""
        # Simular formato alternativo (solo IDs)
        productos_kit = ['COMP001', 'COMP002', 'COMP003']

        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)

        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        self.assertEqual(len(bom.bom_line_ids), 3, "Debe tener 3 componentes")

        # Todas las cantidades deben ser 1 (default)
        for line in bom.bom_line_ids:
            self.assertEqual(line.product_qty, 1, "Cantidad default debe ser 1")

    def test_sync_bom_format_json_string(self):
        """Test: Formato JSON string serializado"""
        import json

        productos_kit_dict = [
            {'ProductoId': 'COMP001', 'Cantidad': 2},
            {'ProductoId': 'COMP002', 'Cantidad': 1},
        ]
        productos_kit_json = json.dumps(productos_kit_dict)

        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit_json)

        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        self.assertEqual(len(bom.bom_line_ids), 2, "Debe tener 2 componentes")

    def test_sync_bom_no_change_skip_update(self):
        """Test: No actualizar BOM si no hubo cambios"""
        productos_kit = [
            {'ProductoId': 'COMP001', 'Cantidad': 2},
            {'ProductoId': 'COMP002', 'Cantidad': 1},
        ]

        # Crear BOM inicial
        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])
        write_date_inicial = bom.write_date

        # Sincronizar de nuevo con los mismos datos
        self.bom_processor._sync_bom(self.env, self.product_kit, productos_kit)
        bom.invalidate_cache()
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_kit.id)
        ])

        # write_date no debe haber cambiado (no se actualizó)
        self.assertEqual(
            bom.write_date, write_date_inicial,
            "BOM no debe actualizarse si no hay cambios"
        )

    def test_producto_mtp_not_saleable(self):
        """Test: Productos MTP marcados como no vendibles"""
        from ..transformers.field_transformers import GrupoTransformer

        transformer = GrupoTransformer()
        context = {'env': self.env}

        # Producto MTP
        result_mtp = transformer.transform('MTP', context)

        self.assertIn('sale_ok', result_mtp)
        self.assertFalse(result_mtp['sale_ok'], "MTP debe tener sale_ok=False")

    def test_producto_normal_saleable(self):
        """Test: Productos normales marcados como vendibles"""
        from ..transformers.field_transformers import GrupoTransformer

        transformer = GrupoTransformer()
        context = {'env': self.env}

        # Producto normal (ACC, Cosméticos, etc.)
        result_acc = transformer.transform('ACC', context)
        self.assertTrue(result_acc['sale_ok'], "ACC debe tener sale_ok=True")

        result_cosmeticos = transformer.transform('Cosméticos', context)
        self.assertTrue(result_cosmeticos['sale_ok'], "Cosméticos debe tener sale_ok=True")


class TestBomValidations(TransactionCase):
    """Tests para validaciones específicas de BOMs"""

    def setUp(self):
        super(TestBomValidations, self).setUp()

        from ..transformers.post_processors import SyncProductBom
        self.bom_processor = SyncProductBom()

        # Crear producto de prueba
        self.product = self.env['product.template'].create({
            'name': 'Test Product',
            'producto_externo': 'TEST001',
        })

    def test_validate_components_all_exist(self):
        """Test: Validación exitosa cuando todos los componentes existen"""
        # Crear componentes
        comp1 = self.env['product.template'].create({
            'name': 'Comp 1',
            'producto_externo': 'C1',
        })
        comp2 = self.env['product.template'].create({
            'name': 'Comp 2',
            'producto_externo': 'C2',
        })

        productos_kit = [
            {'ProductoId': 'C1', 'Cantidad': 1},
            {'ProductoId': 'C2', 'Cantidad': 1},
        ]

        # No debe lanzar excepción
        components = self.bom_processor._validate_and_get_components(
            self.env, productos_kit, self.product
        )

        self.assertEqual(len(components), 2, "Debe encontrar 2 componentes")
        self.assertIn('C1', components)
        self.assertIn('C2', components)

    def test_validate_components_missing(self):
        """Test: Error cuando faltan componentes"""
        productos_kit = [
            {'ProductoId': 'MISSING1', 'Cantidad': 1},
            {'ProductoId': 'MISSING2', 'Cantidad': 1},
        ]

        with self.assertRaises(ValueError) as cm:
            self.bom_processor._validate_and_get_components(
                self.env, productos_kit, self.product
            )

        error_msg = str(cm.exception)
        self.assertIn('MISSING1', error_msg)
        self.assertIn('MISSING2', error_msg)

    def test_has_bom_changed_true(self):
        """Test: Detectar cambios en BOM"""
        # Crear BOM inicial
        comp1 = self.env['product.template'].create({
            'name': 'Comp 1',
            'producto_externo': 'C1',
        })

        productos_kit_inicial = [{'ProductoId': 'C1', 'Cantidad': 2}]
        self.bom_processor._sync_bom(self.env, self.product, productos_kit_inicial)

        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product.id)
        ])

        # Verificar cambio: cantidad diferente
        productos_kit_nueva = [{'ProductoId': 'C1', 'Cantidad': 5}]
        component_products = {'C1': comp1.product_variant_id}

        changed = self.bom_processor._has_bom_changed(
            bom, component_products, productos_kit_nueva
        )

        self.assertTrue(changed, "Debe detectar cambio en cantidad")

    def test_has_bom_changed_false(self):
        """Test: No detectar cambios cuando BOM es idéntica"""
        # Crear BOM
        comp1 = self.env['product.template'].create({
            'name': 'Comp 1',
            'producto_externo': 'C1',
        })

        productos_kit = [{'ProductoId': 'C1', 'Cantidad': 2}]
        self.bom_processor._sync_bom(self.env, self.product, productos_kit)

        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product.id)
        ])

        # Mismos datos
        component_products = {'C1': comp1.product_variant_id}

        changed = self.bom_processor._has_bom_changed(
            bom, component_products, productos_kit
        )

        self.assertFalse(changed, "No debe detectar cambios en BOM idéntica")
