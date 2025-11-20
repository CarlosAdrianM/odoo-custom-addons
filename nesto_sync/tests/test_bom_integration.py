"""
Tests de Integración para Sincronización de BOMs

Tests end-to-end que validan flujos completos:
- Sincronización Nesto → Odoo → Nesto
- Múltiples kits con componentes compartidos
- BOMs anidadas (kits que contienen kits)
- Actualización y eliminación de BOMs
"""

import json
from odoo.tests import TransactionCase


class TestBomIntegration(TransactionCase):
    """Tests de integración para sincronización bidireccional de BOMs"""

    def setUp(self):
        super(TestBomIntegration, self).setUp()

        # Crear componentes base que se usarán en los kits
        self.comp_a = self.env['product.template'].create({
            'name': 'Componente A',
            'producto_externo': 'COMP_A',
            'type': 'product',
        })

        self.comp_b = self.env['product.template'].create({
            'name': 'Componente B',
            'producto_externo': 'COMP_B',
            'type': 'product',
        })

        self.comp_c = self.env['product.template'].create({
            'name': 'Componente C',
            'producto_externo': 'COMP_C',
            'type': 'product',
        })

        # Importar servicios necesarios
        from ..config.entity_configs import get_entity_config
        from ..core.generic_processor import GenericEntityProcessor
        from ..core.generic_service import GenericEntityService
        from ..core.odoo_publisher import OdooPublisher

        self.entity_config = get_entity_config('producto')
        self.processor = GenericEntityProcessor(self.env, self.entity_config)
        self.service = GenericEntityService(self.env, self.entity_config)
        self.publisher = OdooPublisher('producto', self.env)

    def test_flow_nesto_to_odoo_to_nesto(self):
        """
        Test: Flujo completo Nesto → Odoo → Nesto
        1. Mensaje de Nesto crea producto con BOM
        2. BOM se sincroniza correctamente
        3. Al publicar desde Odoo, mensaje incluye ProductosKit
        """
        # 1. Mensaje de Nesto con ProductosKit
        mensaje_nesto = {
            'Tabla': 'Productos',
            'Producto': 'KIT_INTEGRATION',
            'Nombre': 'Kit de Integración',
            'Grupo': 'ACC',
            'Estado': 1,
            'ProductosKit': [
                {'ProductoId': 'COMP_A', 'Cantidad': 3},
                {'ProductoId': 'COMP_B', 'Cantidad': 1},
                {'ProductoId': 'COMP_C', 'Cantidad': 2},
            ]
        }

        # 2. Procesar mensaje (Nesto → Odoo)
        processed = self.processor.process(mensaje_nesto)
        result = self.service.sync(mensaje_nesto, processed)

        # Verificar que el producto se creó
        product = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_INTEGRATION')
        ])
        self.assertEqual(len(product), 1, "Producto debe existir")

        # Verificar que la BOM se creó
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', product.id)
        ])
        self.assertEqual(len(bom), 1, "BOM debe existir")
        self.assertEqual(len(bom.bom_line_ids), 3, "BOM debe tener 3 componentes")

        # 3. Publicar desde Odoo (Odoo → Nesto)
        mensaje_odoo = self.publisher._build_message_from_odoo(product)

        # Verificar que el mensaje incluye ProductosKit
        self.assertIn('ProductosKit', mensaje_odoo)
        productos_kit = mensaje_odoo['ProductosKit']

        self.assertEqual(len(productos_kit), 3, "ProductosKit debe tener 3 items")

        # Verificar cantidades
        kit_comp_a = next(
            (item for item in productos_kit if item['ProductoId'] == 'COMP_A'),
            None
        )
        self.assertIsNotNone(kit_comp_a)
        self.assertEqual(kit_comp_a['Cantidad'], 3)

        kit_comp_b = next(
            (item for item in productos_kit if item['ProductoId'] == 'COMP_B'),
            None
        )
        self.assertIsNotNone(kit_comp_b)
        self.assertEqual(kit_comp_b['Cantidad'], 1)

    def test_multiple_kits_shared_components(self):
        """
        Test: Múltiples kits que comparten componentes
        Verificar que los componentes compartidos funcionan correctamente
        """
        # Kit 1: Contiene A y B
        mensaje_kit1 = {
            'Tabla': 'Productos',
            'Producto': 'KIT_1',
            'Nombre': 'Kit 1',
            'ProductosKit': [
                {'ProductoId': 'COMP_A', 'Cantidad': 2},
                {'ProductoId': 'COMP_B', 'Cantidad': 1},
            ]
        }

        # Kit 2: Contiene B y C
        mensaje_kit2 = {
            'Tabla': 'Productos',
            'Producto': 'KIT_2',
            'Nombre': 'Kit 2',
            'ProductosKit': [
                {'ProductoId': 'COMP_B', 'Cantidad': 3},
                {'ProductoId': 'COMP_C', 'Cantidad': 1},
            ]
        }

        # Sincronizar Kit 1
        processed1 = self.processor.process(mensaje_kit1)
        self.service.sync(mensaje_kit1, processed1)

        # Sincronizar Kit 2
        processed2 = self.processor.process(mensaje_kit2)
        self.service.sync(mensaje_kit2, processed2)

        # Verificar que ambos kits existen
        kit1 = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_1')
        ])
        kit2 = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_2')
        ])

        self.assertEqual(len(kit1), 1)
        self.assertEqual(len(kit2), 1)

        # Verificar BOMs
        bom1 = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', kit1.id)
        ])
        bom2 = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', kit2.id)
        ])

        self.assertEqual(len(bom1.bom_line_ids), 2, "Kit 1 debe tener 2 componentes")
        self.assertEqual(len(bom2.bom_line_ids), 2, "Kit 2 debe tener 2 componentes")

        # Verificar que COMP_B está en ambos kits con cantidades diferentes
        comp_b_in_kit1 = bom1.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP_B'
        )
        comp_b_in_kit2 = bom2.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP_B'
        )

        self.assertEqual(comp_b_in_kit1.product_qty, 1)
        self.assertEqual(comp_b_in_kit2.product_qty, 3)

    def test_nested_bom_valid(self):
        """
        Test: BOMs anidadas válidas (sin ciclos)
        Kit Superior contiene Kit Medio contiene Componentes
        """
        # Crear kit medio (contiene componentes simples)
        mensaje_kit_medio = {
            'Tabla': 'Productos',
            'Producto': 'KIT_MEDIO',
            'Nombre': 'Kit Medio',
            'ProductosKit': [
                {'ProductoId': 'COMP_A', 'Cantidad': 2},
                {'ProductoId': 'COMP_B', 'Cantidad': 1},
            ]
        }

        processed_medio = self.processor.process(mensaje_kit_medio)
        self.service.sync(mensaje_kit_medio, processed_medio)

        # Crear kit superior (contiene kit medio + otro componente)
        mensaje_kit_superior = {
            'Tabla': 'Productos',
            'Producto': 'KIT_SUPERIOR',
            'Nombre': 'Kit Superior',
            'ProductosKit': [
                {'ProductoId': 'KIT_MEDIO', 'Cantidad': 1},
                {'ProductoId': 'COMP_C', 'Cantidad': 3},
            ]
        }

        # Debe sincronizar sin problemas (no hay ciclos)
        processed_superior = self.processor.process(mensaje_kit_superior)
        self.service.sync(mensaje_kit_superior, processed_superior)

        # Verificar que ambos kits existen con sus BOMs
        kit_medio = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_MEDIO')
        ])
        kit_superior = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_SUPERIOR')
        ])

        bom_medio = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', kit_medio.id)
        ])
        bom_superior = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', kit_superior.id)
        ])

        self.assertEqual(len(bom_medio.bom_line_ids), 2, "Kit Medio debe tener 2 componentes")
        self.assertEqual(len(bom_superior.bom_line_ids), 2, "Kit Superior debe tener 2 items")

    def test_update_bom_from_nesto(self):
        """
        Test: Actualizar BOM existente desde mensaje de Nesto
        """
        # 1. Crear kit inicial
        mensaje_inicial = {
            'Tabla': 'Productos',
            'Producto': 'KIT_UPDATE',
            'Nombre': 'Kit Actualizable',
            'ProductosKit': [
                {'ProductoId': 'COMP_A', 'Cantidad': 1},
                {'ProductoId': 'COMP_B', 'Cantidad': 1},
            ]
        }

        processed = self.processor.process(mensaje_inicial)
        self.service.sync(mensaje_inicial, processed)

        product = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_UPDATE')
        ])
        bom_inicial = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', product.id)
        ])

        self.assertEqual(len(bom_inicial.bom_line_ids), 2, "BOM inicial debe tener 2 componentes")

        # 2. Actualizar con mensaje nuevo (cambiar componentes)
        mensaje_actualizado = {
            'Tabla': 'Productos',
            'Producto': 'KIT_UPDATE',
            'Nombre': 'Kit Actualizable',
            'ProductosKit': [
                {'ProductoId': 'COMP_A', 'Cantidad': 5},  # Cantidad cambiada
                {'ProductoId': 'COMP_C', 'Cantidad': 2},  # Componente nuevo
                # COMP_B eliminado
            ]
        }

        processed_update = self.processor.process(mensaje_actualizado)
        self.service.sync(mensaje_actualizado, processed_update)

        # 3. Verificar actualización
        bom_actualizada = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', product.id)
        ])

        self.assertEqual(len(bom_actualizada), 1, "Debe seguir siendo 1 BOM")
        self.assertEqual(len(bom_actualizada.bom_line_ids), 2, "BOM debe tener 2 componentes nuevos")

        # Verificar que COMP_B ya no está
        comp_b = bom_actualizada.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP_B'
        )
        self.assertEqual(len(comp_b), 0, "COMP_B debe haber sido eliminado")

        # Verificar nueva cantidad de COMP_A
        comp_a = bom_actualizada.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP_A'
        )
        self.assertEqual(comp_a.product_qty, 5, "COMP_A debe tener cantidad 5")

        # Verificar que COMP_C se añadió
        comp_c = bom_actualizada.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'COMP_C'
        )
        self.assertEqual(comp_c.product_qty, 2, "COMP_C debe tener cantidad 2")

    def test_delete_bom_from_nesto(self):
        """
        Test: Eliminar BOM cuando ProductosKit viene vacío
        """
        # 1. Crear kit con BOM
        mensaje_inicial = {
            'Tabla': 'Productos',
            'Producto': 'KIT_DELETE',
            'Nombre': 'Kit a Eliminar',
            'ProductosKit': [
                {'ProductoId': 'COMP_A', 'Cantidad': 1},
            ]
        }

        processed = self.processor.process(mensaje_inicial)
        self.service.sync(mensaje_inicial, processed)

        product = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_DELETE')
        ])
        bom_inicial = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', product.id)
        ])

        self.assertEqual(len(bom_inicial), 1, "BOM debe existir")

        # 2. Enviar mensaje con ProductosKit vacío
        mensaje_sin_kit = {
            'Tabla': 'Productos',
            'Producto': 'KIT_DELETE',
            'Nombre': 'Kit a Eliminar',
            'ProductosKit': []
        }

        processed_delete = self.processor.process(mensaje_sin_kit)
        self.service.sync(mensaje_sin_kit, processed_delete)

        # 3. Verificar que la BOM se eliminó
        bom_final = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', product.id)
        ])

        self.assertEqual(len(bom_final), 0, "BOM debe haberse eliminado")

    def test_modify_bom_in_odoo_publishes_to_nesto(self):
        """
        Test: Modificar BOM en Odoo y verificar que se publica correctamente
        """
        # 1. Crear producto sin BOM
        product = self.env['product.template'].create({
            'name': 'Kit Manual',
            'producto_externo': 'KIT_MANUAL',
            'type': 'product',
        })

        # 2. Crear BOM manualmente en Odoo
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {
                    'product_id': self.comp_a.product_variant_id.id,
                    'product_qty': 4,
                }),
                (0, 0, {
                    'product_id': self.comp_b.product_variant_id.id,
                    'product_qty': 2,
                }),
            ]
        })

        # 3. Publicar producto
        mensaje = self.publisher._build_message_from_odoo(product)

        # 4. Verificar que ProductosKit está en el mensaje
        self.assertIn('ProductosKit', mensaje)
        productos_kit = mensaje['ProductosKit']

        self.assertEqual(len(productos_kit), 2, "ProductosKit debe tener 2 items")

        # Verificar componentes y cantidades
        comp_a_item = next(
            (item for item in productos_kit if item['ProductoId'] == 'COMP_A'),
            None
        )
        self.assertIsNotNone(comp_a_item)
        self.assertEqual(comp_a_item['Cantidad'], 4)

        comp_b_item = next(
            (item for item in productos_kit if item['ProductoId'] == 'COMP_B'),
            None
        )
        self.assertIsNotNone(comp_b_item)
        self.assertEqual(comp_b_item['Cantidad'], 2)

    def test_producto_mtp_in_bom_not_saleable(self):
        """
        Test: Producto MTP usado como componente de BOM no es vendible
        """
        # 1. Crear producto MTP
        mensaje_mtp = {
            'Tabla': 'Productos',
            'Producto': 'MTP_001',
            'Nombre': 'Aceite Base',
            'Grupo': 'MTP',
            'Estado': 1,
        }

        processed_mtp = self.processor.process(mensaje_mtp)
        self.service.sync(mensaje_mtp, processed_mtp)

        producto_mtp = self.env['product.template'].search([
            ('producto_externo', '=', 'MTP_001')
        ])

        # Verificar que MTP no es vendible
        self.assertFalse(producto_mtp.sale_ok, "Producto MTP no debe ser vendible")

        # 2. Crear kit que usa MTP como componente
        mensaje_kit = {
            'Tabla': 'Productos',
            'Producto': 'KIT_CON_MTP',
            'Nombre': 'Kit con Materia Prima',
            'Grupo': 'ACC',
            'ProductosKit': [
                {'ProductoId': 'MTP_001', 'Cantidad': 2},
                {'ProductoId': 'COMP_A', 'Cantidad': 1},
            ]
        }

        # Debe sincronizar sin problemas
        processed_kit = self.processor.process(mensaje_kit)
        self.service.sync(mensaje_kit, processed_kit)

        kit = self.env['product.template'].search([
            ('producto_externo', '=', 'KIT_CON_MTP')
        ])

        # Verificar que el kit SÍ es vendible
        self.assertTrue(kit.sale_ok, "Kit debe ser vendible aunque contenga MTP")

        # Verificar que la BOM contiene MTP
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', kit.id)
        ])

        mtp_line = bom.bom_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.producto_externo == 'MTP_001'
        )

        self.assertEqual(len(mtp_line), 1, "BOM debe contener MTP")
        self.assertEqual(mtp_line.product_qty, 2, "MTP debe tener cantidad 2")
