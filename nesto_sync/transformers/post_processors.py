"""
Post Processors - Procesamiento posterior a la transformación de campos

Los post_processors ejecutan lógica después de procesar todos los campos.
Útil para lógica que depende de múltiples campos o de relaciones.
"""

import logging

_logger = logging.getLogger(__name__)


class PostProcessorRegistry:
    """Registry central de post_processors disponibles"""

    _post_processors = {}

    @classmethod
    def register(cls, name):
        """Decorador para registrar un post_processor"""
        def decorator(processor_class):
            cls._post_processors[name] = processor_class
            return processor_class
        return decorator

    @classmethod
    def get(cls, name):
        """Obtiene una instancia de un post_processor por nombre"""
        processor_class = cls._post_processors.get(name)
        if not processor_class:
            raise ValueError(f"Post processor no encontrado: {name}")
        return processor_class()

    @classmethod
    def get_all(cls):
        """Devuelve todos los post_processors registrados"""
        return cls._post_processors.keys()


@PostProcessorRegistry.register('assign_email_from_children')
class AssignEmailFromChildren:
    """Asigna el email del primer hijo que tenga email al parent"""

    def process(self, parent_values, children_values_list, context):
        """
        Busca el primer email disponible en los children y lo asigna al parent

        Args:
            parent_values: Dict con valores del parent
            children_values_list: Lista de dicts con valores de children
            context: Dict con contexto

        Returns:
            Tuple (parent_values, children_values_list) modificados
        """
        # Si el parent ya tiene email, no hacer nada
        if parent_values.get('email'):
            return parent_values, children_values_list

        # Buscar primer email en children
        for child in children_values_list:
            email = child.get('email')
            if email and email.strip():
                parent_values['email'] = email
                break

        return parent_values, children_values_list


@PostProcessorRegistry.register('merge_comments')
class MergeComments:
    """Combina múltiples campos _append_comment en un único comment"""

    def process(self, parent_values, children_values_list, context):
        """
        Combina todos los _append_comment en el campo comment

        Args:
            parent_values: Dict con valores del parent
            children_values_list: Lista de dicts con valores de children
            context: Dict con contexto

        Returns:
            Tuple (parent_values, children_values_list) modificados
        """
        # Buscar todos los _append_comment en parent_values
        comment_parts = []

        # Añadir comment base si existe
        if parent_values.get('comment'):
            comment_parts.append(parent_values['comment'])

        # Buscar _append_comment (temporal generado por transformers)
        if parent_values.get('_append_comment'):
            comment_parts.append(parent_values.pop('_append_comment'))

        # Combinar todo
        if comment_parts:
            parent_values['comment'] = '\n'.join(comment_parts)

        return parent_values, children_values_list


@PostProcessorRegistry.register('set_parent_id_for_children')
class SetParentIdForChildren:
    """Asigna parent_id a los children después de procesar el parent"""

    def process(self, parent_values, children_values_list, context):
        """
        Asigna el parent_id a todos los children

        Args:
            parent_values: Dict con valores del parent
            children_values_list: Lista de dicts con valores de children
            context: Dict con contexto

        Returns:
            Tuple (parent_values, children_values_list) modificados
        """
        # Este post_processor se ejecuta DESPUÉS de crear el parent
        # Por eso recibe el parent_id en el contexto
        parent_id = context.get('parent_id')

        if parent_id:
            for child in children_values_list:
                # Solo asignar si no tiene parent_id ya asignado
                if not child.get('parent_id'):
                    child['parent_id'] = parent_id

        return parent_values, children_values_list


@PostProcessorRegistry.register('normalize_phone_numbers')
class NormalizePhoneNumbers:
    """Normaliza formato de números de teléfono (ejemplo)"""

    def process(self, parent_values, children_values_list, context):
        """
        Normaliza teléfonos (quita espacios, añade prefijo si falta, etc.)

        Args:
            parent_values: Dict con valores del parent
            children_values_list: Lista de dicts con valores de children
            context: Dict con contexto

        Returns:
            Tuple (parent_values, children_values_list) modificados
        """
        # Normalizar teléfonos del parent
        self._normalize_phones(parent_values)

        # Normalizar teléfonos de children
        for child in children_values_list:
            self._normalize_phones(child)

        return parent_values, children_values_list

    def _normalize_phones(self, values):
        """Normaliza campos mobile y phone"""
        if values.get('mobile'):
            values['mobile'] = self._normalize_phone(values['mobile'])

        if values.get('phone'):
            values['phone'] = self._normalize_phone(values['phone'])

    def _normalize_phone(self, phone):
        """Normaliza un número de teléfono"""
        if not phone:
            return phone

        # Quitar espacios
        phone = phone.replace(' ', '').replace('-', '')

        # Aquí se podría añadir lógica para:
        # - Añadir prefijo internacional (+34 para España)
        # - Validar longitud
        # - etc.

        return phone


@PostProcessorRegistry.register('sync_product_bom')
class SyncProductBom:
    """
    Sincroniza la lista BOM (Bill of Materials) de un producto desde Nesto

    Este post-processor procesa el campo ProductosKit del mensaje y:
    1. Valida que todos los componentes existen en Odoo
    2. Detecta ciclos infinitos (recursión)
    3. Crea/actualiza/elimina la BOM según corresponda

    IMPORTANTE: Este post-processor se ejecuta DESPUÉS de crear/actualizar el producto,
    por lo que necesita recibir el product_id en el contexto.
    """

    MAX_BOM_DEPTH = 10  # Profundidad máxima para validación de recursión

    def process(self, parent_values, children_values_list, context):
        """
        Procesa ProductosKit y lo guarda en parent_values

        Este post-processor NO sincroniza directamente la BOM.
        Solo guarda los datos de ProductosKit en parent_values para que
        GenericService los procese después de crear/actualizar el producto.

        Args:
            parent_values: Dict con valores del parent
            children_values_list: Lista de dicts con valores de children
            context: Dict con contexto (debe incluir 'message')

        Returns:
            Tuple (parent_values, children_values_list) modificados
        """
        message = context.get('message')

        if not message:
            _logger.warning("SyncProductBom: contexto incompleto (falta message)")
            return parent_values, children_values_list

        # Guardar ProductosKit en parent_values para procesarlo después en GenericService
        productos_kit = message.get('ProductosKit')

        # IMPORTANTE: Guardar como campo especial que NO existe en el modelo
        # Esto evita que se intente guardar en la base de datos
        # GenericService lo detectará y procesará después
        if productos_kit is not None:
            parent_values['_productos_kit_data'] = productos_kit

        return parent_values, children_values_list

    @staticmethod
    def sync_bom_after_save(env, product_record, productos_kit_data):
        """
        Método estático para sincronizar BOM después de crear/actualizar producto

        Este método es llamado desde GenericService después de guardar el producto.

        Args:
            env: Odoo environment
            product_record: Registro product.template
            productos_kit_data: Lista de dicts con ProductoId y Cantidad

        Raises:
            ValueError: Si algún componente no existe o hay ciclos
        """
        processor = SyncProductBom()
        processor._sync_bom(env, product_record, productos_kit_data)

    def _sync_bom(self, env, product_record, productos_kit_data):
        """
        Sincroniza la BOM completa de un producto

        Args:
            env: Odoo environment
            product_record: Registro product.template
            productos_kit_data: Lista de dicts con ProductoId y Cantidad

        Raises:
            ValueError: Si algún componente no existe o hay ciclos
        """
        _logger.info(
            f"Sincronizando BOM para producto {product_record.producto_externo} "
            f"({len(productos_kit_data or [])} componentes)"
        )

        # Buscar BOM existente del producto
        bom_model = env['mrp.bom']
        existing_bom = bom_model.search([
            ('product_tmpl_id', '=', product_record.id),
            ('active', '=', True)
        ], limit=1)

        # CASO 1: ProductosKit vacío o None → Eliminar BOM si existe
        if not productos_kit_data:
            if existing_bom:
                _logger.info(
                    f"Eliminando BOM existente para producto {product_record.producto_externo} "
                    f"(ProductosKit vacío)"
                )
                existing_bom.unlink()
            return

        # CASO 2: ProductosKit tiene componentes → Validar y crear/actualizar BOM

        # Paso 1: Validar que TODOS los componentes existen
        component_products = self._validate_and_get_components(
            env, productos_kit_data, product_record
        )

        # Paso 2: Validar que no hay ciclos infinitos
        self._validate_no_bom_cycles(
            env, product_record, component_products
        )

        # Paso 3: Comparar con BOM existente
        bom_changed = self._has_bom_changed(
            existing_bom, component_products, productos_kit_data
        )

        if not bom_changed and existing_bom:
            _logger.info(
                f"BOM sin cambios para producto {product_record.producto_externo}, "
                f"saltando actualización"
            )
            return

        # Paso 4: Actualizar o crear BOM
        if existing_bom:
            self._update_bom(existing_bom, component_products, productos_kit_data)
        else:
            self._create_bom(env, product_record, component_products, productos_kit_data)

    def _validate_and_get_components(self, env, productos_kit_data, parent_product):
        """
        Valida que todos los componentes existen y los devuelve

        Args:
            env: Odoo environment
            productos_kit_data: Lista de dicts con ProductoId y Cantidad
            parent_product: Producto principal (para error messages)

        Returns:
            Dict {producto_externo: product.product record}

        Raises:
            ValueError: Si algún componente no existe
        """
        import json

        product_product_model = env['product.product']
        components = {}
        missing_components = []

        # Si productos_kit_data es un string JSON, deserializarlo
        if isinstance(productos_kit_data, str):
            try:
                productos_kit_data = json.loads(productos_kit_data)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"ProductosKit contiene JSON inválido para producto "
                    f"{parent_product.producto_externo}: {e}"
                )

        for kit_item in productos_kit_data:
            # Si kit_item es un string, deserializarlo también
            if isinstance(kit_item, str):
                try:
                    kit_item = json.loads(kit_item)
                except json.JSONDecodeError as e:
                    _logger.warning(
                        f"ProductosKit contiene item con JSON inválido: {kit_item}, error: {e}"
                    )
                    continue

            # Si kit_item es un int o string simple, asumimos que es el ProductoId directamente
            # Formato alternativo: ProductosKit = [41224, 41225, ...]
            if isinstance(kit_item, (int, str)):
                producto_id = str(kit_item)
                cantidad = 1  # Cantidad por defecto
            elif isinstance(kit_item, dict):
                producto_id = kit_item.get('ProductoId')
                cantidad = kit_item.get('Cantidad', 1)
            else:
                _logger.warning(
                    f"ProductosKit contiene item con tipo inesperado: {type(kit_item)}, valor: {kit_item}"
                )
                continue

            if not producto_id:
                _logger.warning(f"ProductosKit contiene item sin ProductoId: {kit_item}")
                continue

            # Buscar producto por producto_externo
            # IMPORTANTE: Buscamos en product.product, no product.template
            # porque la BOM apunta a variantes específicas
            component = product_product_model.search([
                ('product_tmpl_id.producto_externo', '=', str(producto_id))
            ], limit=1)

            if not component:
                missing_components.append(producto_id)
            else:
                components[producto_id] = component

        # Si falta algún componente, lanzar excepción → DLQ
        if missing_components:
            raise ValueError(
                f"Componentes de BOM no encontrados para producto "
                f"{parent_product.producto_externo}: {', '.join(missing_components)}. "
                f"Asegúrate de que estos productos existen en Odoo antes de sincronizar el kit."
            )

        return components

    def _validate_no_bom_cycles(self, env, parent_product, component_products):
        """
        Valida que no hay ciclos infinitos en la BOM

        Detecta casos como:
        - A contiene B, B contiene A (ciclo directo)
        - A contiene B, B contiene C, C contiene A (ciclo indirecto)

        Args:
            env: Odoo environment
            parent_product: Producto principal
            component_products: Dict de productos componentes

        Raises:
            ValueError: Si se detecta un ciclo
        """
        # Obtener producto_externo del parent
        parent_externo = parent_product.producto_externo

        # Validar que el producto no se contiene a sí mismo (ciclo directo)
        for producto_id, component in component_products.items():
            component_externo = component.product_tmpl_id.producto_externo

            if component_externo == parent_externo:
                raise ValueError(
                    f"Ciclo detectado: Producto {parent_externo} se contiene a sí mismo "
                    f"en su BOM"
                )

        # Validar ciclos profundos (A → B → C → A)
        visited = set()
        path = [parent_externo]

        for producto_id, component in component_products.items():
            if self._has_cycle_in_bom(env, component, parent_externo, visited, path, 0):
                raise ValueError(
                    f"Ciclo detectado en BOM de producto {parent_externo}: "
                    f"{' → '.join(path)}"
                )

    def _has_cycle_in_bom(self, env, product, target_externo, visited, path, depth):
        """
        Búsqueda recursiva de ciclos en BOM (DFS)

        Args:
            env: Odoo environment
            product: product.product actual
            target_externo: producto_externo que estamos buscando (el parent)
            visited: Set de productos ya visitados
            path: Lista con el camino actual (para logging)
            depth: Profundidad actual

        Returns:
            bool: True si se encontró un ciclo
        """
        # Límite de profundidad para evitar recursión infinita
        if depth > self.MAX_BOM_DEPTH:
            _logger.warning(
                f"Alcanzada profundidad máxima ({self.MAX_BOM_DEPTH}) "
                f"en validación de BOM: {' → '.join(path)}"
            )
            return False

        # Obtener producto_externo del producto actual
        current_externo = product.product_tmpl_id.producto_externo

        # Si ya visitamos este producto, saltar (evitar loops)
        if current_externo in visited:
            return False

        visited.add(current_externo)
        path.append(current_externo)

        # Buscar BOM del producto actual
        bom = env['mrp.bom'].search([
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('active', '=', True)
        ], limit=1)

        if not bom:
            # No tiene BOM, no hay ciclo por este camino
            path.pop()
            return False

        # Revisar cada componente de la BOM
        for line in bom.bom_line_ids:
            component_externo = line.product_id.product_tmpl_id.producto_externo

            # ¿Este componente es el producto original? → CICLO!
            if component_externo == target_externo:
                path.append(component_externo)
                return True

            # Búsqueda recursiva en este componente
            if self._has_cycle_in_bom(
                env, line.product_id, target_externo, visited, path, depth + 1
            ):
                return True

        # No encontramos ciclo por este camino
        path.pop()
        return False

    def _has_bom_changed(self, existing_bom, component_products, productos_kit_data):
        """
        Compara BOM existente con la nueva para detectar cambios

        Args:
            existing_bom: mrp.bom record existente (o False)
            component_products: Dict de productos componentes
            productos_kit_data: Lista con datos de ProductosKit

        Returns:
            bool: True si hay cambios
        """
        if not existing_bom:
            return True  # No existe BOM, hay cambio

        # Comparar número de líneas
        if len(existing_bom.bom_line_ids) != len(productos_kit_data):
            return True

        # Crear dict de componentes existentes: {producto_externo: cantidad}
        existing_components = {}
        for line in existing_bom.bom_line_ids:
            producto_externo = line.product_id.product_tmpl_id.producto_externo
            existing_components[producto_externo] = line.product_qty

        # Comparar con componentes nuevos
        for kit_item in productos_kit_data:
            # Manejar formato alternativo (int/string directo)
            if isinstance(kit_item, (int, str)):
                producto_id = str(kit_item)
                cantidad = 1
            elif isinstance(kit_item, dict):
                producto_id = kit_item.get('ProductoId')
                cantidad = kit_item.get('Cantidad', 1)
            else:
                continue

            if not producto_id:
                continue

            # ¿Existe este componente en la BOM actual?
            existing_qty = existing_components.get(str(producto_id))

            if existing_qty is None:
                # Componente nuevo
                return True

            if existing_qty != cantidad:
                # Cantidad cambió
                return True

        # No hay cambios
        return False

    def _update_bom(self, existing_bom, component_products, productos_kit_data):
        """
        Actualiza BOM existente eliminando líneas viejas y creando nuevas

        Args:
            existing_bom: mrp.bom record
            component_products: Dict de productos componentes
            productos_kit_data: Lista con datos de ProductosKit
        """
        _logger.info(f"Actualizando BOM ID {existing_bom.id}")

        # Estrategia simple: Borrar todas las líneas y recrear
        # (más simple que actualizar línea por línea)
        existing_bom.bom_line_ids.unlink()

        # Crear nuevas líneas
        for kit_item in productos_kit_data:
            # Manejar formato alternativo (int/string directo)
            if isinstance(kit_item, (int, str)):
                producto_id = str(kit_item)
                cantidad = 1
            elif isinstance(kit_item, dict):
                producto_id = kit_item.get('ProductoId')
                cantidad = kit_item.get('Cantidad', 1)
            else:
                continue

            if not producto_id:
                continue

            component = component_products.get(producto_id)
            if not component:
                continue

            existing_bom.write({
                'bom_line_ids': [(0, 0, {
                    'product_id': component.id,
                    'product_qty': cantidad,
                })]
            })

        _logger.info(
            f"BOM actualizada: {len(productos_kit_data)} componentes"
        )

    def _create_bom(self, env, product_record, component_products, productos_kit_data):
        """
        Crea nueva BOM para el producto

        Args:
            env: Odoo environment
            product_record: product.template record
            component_products: Dict de productos componentes
            productos_kit_data: Lista con datos de ProductosKit
        """
        _logger.info(
            f"Creando nueva BOM para producto {product_record.producto_externo}"
        )

        # Preparar líneas de BOM
        bom_lines = []
        for kit_item in productos_kit_data:
            # Manejar formato alternativo (int/string directo)
            if isinstance(kit_item, (int, str)):
                producto_id = str(kit_item)
                cantidad = 1
            elif isinstance(kit_item, dict):
                producto_id = kit_item.get('ProductoId')
                cantidad = kit_item.get('Cantidad', 1)
            else:
                continue

            if not producto_id:
                continue

            component = component_products.get(producto_id)
            if not component:
                continue

            bom_lines.append((0, 0, {
                'product_id': component.id,
                'product_qty': cantidad,
            }))

        # Crear BOM
        bom_vals = {
            'product_tmpl_id': product_record.id,
            'product_qty': 1.0,
            'type': 'normal',  # BOM normal (no phantom), con stock y facturación
            'bom_line_ids': bom_lines,
        }

        bom = env['mrp.bom'].create(bom_vals)

        _logger.info(
            f"BOM creada (ID {bom.id}) con {len(bom_lines)} componentes"
        )
