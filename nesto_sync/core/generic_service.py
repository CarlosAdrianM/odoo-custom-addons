"""
Generic Entity Service - Servicio genérico para operaciones CRUD

Este servicio maneja la creación y actualización de registros en Odoo,
incluyendo la detección de cambios reales (anti-bucle infinito).
"""

import json
import logging
from odoo.http import Response
from odoo import models

_logger = logging.getLogger(__name__)


def _sanitize_value_for_logging(value):
    """
    Sanitiza un valor individual para logging, reemplazando datos binarios grandes con resúmenes

    Args:
        value: Valor a sanitizar (puede ser str, bytes, o cualquier otro tipo)

    Returns:
        Valor sanitizado apto para logging
    """
    # Detectar si es un campo de imagen (base64 o bytes)
    if isinstance(value, bytes):
        return f"<binary_data: {len(value)} bytes>"

    if isinstance(value, str):
        # Detectar base64 de imágenes o string representation de bytes
        # Típicamente empiezan con caracteres específicos o "b'..."
        is_image_data = (
            value.startswith('iVBOR') or  # PNG base64
            value.startswith('/9j/') or    # JPEG base64
            value.startswith('R0lGOD') or  # GIF base64
            value.startswith("b'iVBOR") or  # String repr of PNG bytes
            value.startswith("b'/9j/") or   # String repr of JPEG bytes
            value.startswith('b"iVBOR') or
            value.startswith('b"/9j/')
        )

        # Si parece imagen y es suficientemente largo, sanitizar
        if is_image_data and len(value) > 100:
            return f"<image_data: {len(value)} bytes>"

        # Truncar strings muy largos (no imagen)
        if len(value) > 200:
            return value[:200] + "..."

    return value


class GenericEntityService:
    """Service genérico para cualquier entidad"""

    def __init__(self, env, entity_config, test_mode=False):
        """
        Inicializa el service

        Args:
            env: Environment de Odoo
            entity_config: Dict con configuración de la entidad
            test_mode: Si True, no hace commits (para testing)
        """
        self.env = env
        self.config = entity_config
        self.test_mode = test_mode
        self.model = env[entity_config['odoo_model']]

    def create_or_update_contact(self, processed_data):
        """
        Crea o actualiza un contacto principal y sus children

        Args:
            processed_data: Dict con {'parent': {...}, 'children': [...]}

        Returns:
            Response HTTP
        """
        parent_values = processed_data.get('parent', {})
        children_values_list = processed_data.get('children', [])

        # Rastrear si hubo cambios
        had_changes = False

        # Crear o actualizar el parent
        parent_response = self._create_or_update_single(parent_values)

        # Si falló el parent, retornar error
        if parent_response.status_code != 200:
            return parent_response

        # Verificar si el parent tuvo cambios (creación o actualización)
        parent_response_data = json.loads(parent_response.response[0].decode())
        if parent_response_data.get('message') != 'Sin cambios':
            had_changes = True

        # Obtener el parent_id para los children
        parent_record = self._find_record(parent_values)
        if parent_record:
            # Crear o actualizar los children
            for child_values in children_values_list:
                child_values['parent_id'] = parent_record.id
                child_response = self._create_or_update_single(child_values)

                # Si falla un child, loguear pero continuar
                if child_response.status_code != 200:
                    _logger.warning(f"Falló creación/actualización de child: {child_response.response}")
                else:
                    # Verificar si el child tuvo cambios
                    child_response_data = json.loads(child_response.response[0].decode())
                    if child_response_data.get('message') != 'Sin cambios':
                        had_changes = True

        # Retornar mensaje apropiado según si hubo cambios
        message = 'Sincronización completada' if had_changes else 'Sin cambios'
        return Response(
            response=json.dumps({'message': message}),
            status=200,
            content_type='application/json'
        )

    def _create_or_update_single(self, values):
        """
        Crea o actualiza un único registro

        Args:
            values: Dict con valores para el registro

        Returns:
            Response HTTP
        """
        # Buscar registro existente
        record = self._find_record(values)

        if record:
            # Detectar cambios antes de actualizar (ANTI-BUCLE)
            if self._has_changes(record, values):
                _logger.info(f"Cambios detectados, actualizando {self.config['odoo_model']}")
                return self._update_record(record, values)
            else:
                _logger.info(f"Sin cambios en {self.config['odoo_model']}, omitiendo actualización")
                return Response(
                    response=json.dumps({'message': 'Sin cambios'}),
                    status=200,
                    content_type='application/json'
                )
        else:
            # Crear nuevo registro
            _logger.info(f"Creando nuevo {self.config['odoo_model']}")
            return self._create_record(values)

    def _find_record(self, values):
        """
        Busca un registro existente según los id_fields configurados

        Args:
            values: Dict con valores (debe incluir id_fields)

        Returns:
            Recordset de Odoo o None
        """
        domain = self._build_search_domain(values)

        # Buscar incluyendo activos e inactivos
        record = self.model.sudo().search(domain, limit=1)

        return record if record else None

    def _build_search_domain(self, values):
        """
        Construye dominio de búsqueda basado en id_fields

        Args:
            values: Dict con valores

        Returns:
            Lista con dominio de Odoo
        """
        domain = []

        # Añadir criterios de id_fields
        for id_field in self.config.get('id_fields', []):
            value = values.get(id_field)
            domain.append((id_field, '=', value))

        # Buscar en activos e inactivos
        if 'active' in self.model._fields:
            domain.append('|')
            domain.append(('active', '=', True))
            domain.append(('active', '=', False))

        return domain

    def _has_changes(self, record, new_values):
        """
        Detecta si hay cambios reales entre el registro y los nuevos valores

        Esta es la función clave para evitar el bucle infinito:
        Solo actualiza si realmente cambió algo.

        Args:
            record: Recordset de Odoo
            new_values: Dict con nuevos valores

        Returns:
            bool: True si hay cambios, False si todo es igual
        """
        for field, new_value in new_values.items():
            # Saltar campos que no existen en el modelo
            if field not in record._fields:
                _logger.debug(f"Campo {field} no existe en modelo, omitiendo comparación")
                continue

            # Obtener valor actual
            current_value = getattr(record, field, None)

            # Comparar según tipo de campo
            if self._values_are_different(field, current_value, new_value, record):
                # Sanitizar valores para logging (evitar base64 de imágenes en logs)
                sanitized_current = _sanitize_value_for_logging(current_value)
                sanitized_new = _sanitize_value_for_logging(new_value)
                _logger.info(f"Cambio en {field}: '{sanitized_current}' -> '{sanitized_new}'")
                return True

        # El kit no es un campo del modelo: viaja aparte, en
        # _productos_kit_data, y el bucle de arriba lo salta. Sin esto, un
        # mensaje que solo cambia (o vacía) ProductosKit se quedaba en «sin
        # cambios» y la BOM no se sincronizaba nunca (issue #12).
        if self._bom_has_changes(record, new_values):
            _logger.info(f"Cambio en la BOM de {self.config['odoo_model']} (ID: {record.id})")
            return True

        _logger.debug(f"No hay cambios en {self.config['odoo_model']} (ID: {record.id})")
        return False

    def _bom_has_changes(self, record, new_values):
        """
        Detecta si el ProductosKit del mensaje cambia la BOM del producto

        Args:
            record: Recordset de Odoo
            new_values: Dict con nuevos valores

        Returns:
            bool: True si hay que sincronizar la BOM
        """
        if self.config.get('odoo_model') != 'product.template':
            return False

        productos_kit_data = new_values.get('_productos_kit_data')
        if productos_kit_data is None:
            return False

        from ..transformers.post_processors import SyncProductBom

        return SyncProductBom.bom_needs_sync(self.env, record, productos_kit_data)

    def _normalize_html(self, html_text):
        """
        Normaliza texto HTML para comparación

        Elimina tags HTML, normaliza espacios y ordena líneas para evitar
        falsos positivos por reordenamiento de contenido.

        Args:
            html_text: Texto con posible HTML

        Returns:
            str: Texto normalizado sin HTML
        """
        if not html_text:
            return ''

        import re

        # Convertir a string si es necesario
        text = str(html_text).strip()

        # Eliminar tags HTML
        text = re.sub(r'<[^>]+>', '', text)

        # Normalizar espacios y saltos de línea
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Ordenar líneas para evitar detectar cambios por reordenamiento
        lines.sort()

        return '\n'.join(lines)

    def _values_are_different(self, field, current_value, new_value, record):
        """
        Compara dos valores considerando el tipo de campo

        Args:
            field: Nombre del campo
            current_value: Valor actual en Odoo
            new_value: Nuevo valor del mensaje
            record: Recordset de Odoo

        Returns:
            bool: True si son diferentes
        """
        field_type = record._fields[field].type

        # Campos relacionales (many2one)
        if field_type == 'many2one':
            current_id = current_value.id if current_value else None
            new_id = new_value if isinstance(new_value, int) else None
            return current_id != new_id

        # Campos many2many o one2many
        if field_type in ('many2many', 'one2many'):
            current_ids = set(current_value.ids) if current_value else set()
            new_ids = set(new_value) if isinstance(new_value, (list, tuple)) else set()
            return current_ids != new_ids

        # Campos boolean
        if field_type == 'boolean':
            return bool(current_value) != bool(new_value)

        # Campos numéricos (float, integer)
        if field_type in ('float', 'integer', 'monetary'):
            # Comparar con tolerancia para floats
            if field_type == 'float':
                return abs(float(current_value or 0) - float(new_value or 0)) > 0.01
            else:
                return int(current_value or 0) != int(new_value or 0)

        # Campos de texto (char, text)
        if field_type in ('char', 'text'):
            # Normalizar None y strings vacíos
            current = (current_value or '').strip()
            new = (new_value or '').strip()

            # Para el campo 'name', comparar case-insensitive
            # (Nesto a veces cambia mayúsculas/minúsculas internamente)
            if field == 'name':
                return current.upper() != new.upper()

            return current != new

        # Campos HTML o 'comment' (que puede tener HTML de Odoo vs texto plano de Nesto)
        if field_type == 'html' or field == 'comment':
            # Normalizar HTML para comparación
            return self._normalize_html(current_value) != self._normalize_html(new_value)

        # Campos de fecha/datetime
        if field_type in ('date', 'datetime'):
            # Convertir a string para comparar
            return str(current_value) != str(new_value)

        # Por defecto, comparación directa
        return current_value != new_value

    def _contexto_de_escritura(self):
        """
        Contexto con el que se escribe todo lo que viene de Nesto

        - skip_sync: el cambio viene de Nesto, no se republica (anti-bucle).
        - no_vat_validation: base_vat no valida el NIF (issue #18). Nesto es la
          fuente de verdad del NIF, así que Odoo no gana nada rechazándolo:
          lo que hacía era perder el cliente entero (dirección, vendedor,
          fechas de compras…) y dejar el mensaje en la DLQ. El 18/09 había 177
          entidades atascadas por esto, la causa más frecuente de las que no se
          arreglan solas. base_vat respeta esta clave a propósito, para
          «API pushes from external platforms where you have no control over
          VAT numbers».

        Solo afecta a lo que entra por aquí: lo que se edite a mano en Odoo
        sigue validándose como siempre.

        Returns:
            Dict con el contexto
        """
        return {'skip_sync': True, 'no_vat_validation': True}

    def _avisar_si_el_nif_no_valida(self, record, values):
        """
        Deja en el log el NIF que no habría pasado la validación

        No bloquea nada: es para poder sacar la lista y pasársela a quien
        mantiene las fichas en Nesto (issue #18).

        Args:
            record: Registro ya creado o actualizado
            values: Valores que se escribieron
        """
        if self.config.get('odoo_model') != 'res.partner' or not values.get('vat'):
            return

        # base_vat puede no estar instalado
        if not hasattr(record, '_run_vat_test'):
            return

        try:
            pais = record.commercial_partner_id.country_id
            if record._run_vat_test(record.vat, pais, record.is_company) is False:
                _logger.warning(
                    f"NIF que no pasa la validación de base_vat y se ha guardado "
                    f"igualmente (issue #18): cliente_externo={record.cliente_externo}, "
                    f"contacto_externo={record.contacto_externo}, vat={record.vat}"
                )
        except Exception as e:
            # Un aviso nunca puede tumbar una sincronización
            _logger.debug(f"No se ha podido comprobar el NIF de {record.id}: {e}")

    def _aplicar_defaults_al_crear(self, values):
        """
        Rellena los campos requeridos que no traen valor, con su default

        El default es para CREAR. Si el registro ya existe, un campo requerido
        que llega vacío se omite en el processor y Odoo conserva lo que tenía:
        aplicarlo también al actualizar pisaría el nombre bueno de una ficha con
        un '<Nombre producto no proporcionado>' (issue #19).

        Por eso los defaults solo quedan donde Odoo no admite el campo vacío:
        product.template.name es required a nivel de campo. En res.partner no
        hay default a propósito: la restricción check_name solo exige nombre
        cuando type='contact', así que una dirección de entrega puede quedarse
        sin nombre y Odoo enseña el del padre.

        Args:
            values: Dict de valores, se modifica in situ
        """
        for mapping in self.config.get('field_mappings', {}).values():
            odoo_field = mapping.get('odoo_field')
            if not odoo_field or not mapping.get('required') or 'default' not in mapping:
                continue

            if not values.get(odoo_field):
                _logger.info(
                    f"Creando {self.config['odoo_model']} sin {odoo_field}: "
                    f"se usa el default {mapping['default']!r}"
                )
                values[odoo_field] = mapping['default']

    def _create_record(self, values):
        """
        Crea un nuevo registro

        Args:
            values: Dict con valores para el registro

        Returns:
            Response HTTP
        """
        try:
            # Copiar valores para no modificar el original
            values = values.copy()

            # Extraer _productos_kit_data si existe (campo especial que no se guarda)
            productos_kit_data = values.pop('_productos_kit_data', None)

            # El default de un campo requerido se aplica SOLO al crear
            self._aplicar_defaults_al_crear(values)

            # CRÍTICO: Añadir skip_sync=True para evitar bucle infinito
            # Este create viene de Nesto, NO debe publicarse
            record = self.model.sudo().with_context(**self._contexto_de_escritura()).create(values)

            if record:
                _logger.info(f"{self.config['odoo_model']} creado con ID: {record.id}")
                self._avisar_si_el_nif_no_valida(record, values)

                # Procesar BOM si es producto y tiene _productos_kit_data
                if productos_kit_data is not None and self.config.get('odoo_model') == 'product.template':
                    self._sync_product_bom(record, productos_kit_data)

                if not self.test_mode:
                    self.env.cr.commit()

                return Response(
                    response=json.dumps({
                        'message': f"{self.config['message_type']} creado",
                        'id': record.id
                    }),
                    status=200,
                    content_type='application/json'
                )
            else:
                _logger.error(f"Error al crear {self.config['odoo_model']}")
                self.env.cr.rollback()
                return Response(
                    response=json.dumps({'error': 'Error al crear registro'}),
                    status=500,
                    content_type='application/json'
                )

        except Exception as e:
            _logger.error(f"Excepción al crear {self.config['odoo_model']}: {str(e)}")
            self.env.cr.rollback()
            # Re-lanzar la excepción para que el controller active el sistema DLQ
            raise

    def _update_record(self, record, values):
        """
        Actualiza un registro existente

        Args:
            record: Recordset de Odoo
            values: Dict con valores a actualizar

        Returns:
            Response HTTP
        """
        try:
            # Copiar valores para no modificar el original
            values = values.copy()

            # Extraer _productos_kit_data si existe (campo especial que no se guarda)
            productos_kit_data = values.pop('_productos_kit_data', None)

            # Protección contra jerarquías recursivas
            # Si el parent_id es el mismo que el ID del registro, eliminarlo
            if 'parent_id' in values and values['parent_id'] == record.id:
                _logger.warning(
                    f"Eliminando parent_id recursivo: registro {record.id} "
                    f"intentaba asignarse a sí mismo como parent"
                )
                del values['parent_id']

            # IMPORTANTE: Eliminar id_fields que no han cambiado
            # Esto evita que se disparen validaciones de unicidad innecesarias
            for id_field in self.config.get('id_fields', []):
                if id_field in values:
                    current_value = record[id_field]
                    new_value = values[id_field]

                    # Si el valor no ha cambiado, eliminarlo de la actualización
                    if current_value == new_value:
                        _logger.debug(
                            f"Omitiendo campo {id_field} en actualización "
                            f"(valor sin cambios: {current_value})"
                        )
                        del values[id_field]

            # Filtrar solo los campos que realmente cambiaron para evitar
            # efectos secundarios (ej: notificaciones de reasignación de vendedor
            # cuando user_id no ha cambiado pero otro campo sí)
            values = {
                field: value
                for field, value in values.items()
                if field not in record._fields
                or self._values_are_different(field, getattr(record, field, None), value, record)
            }

            # CRÍTICO: Añadir skip_sync=True para evitar bucle infinito
            # Este write viene de Nesto, NO debe volver a publicarse
            record.sudo().with_context(**self._contexto_de_escritura()).write(values)
            _logger.info(f"{self.config['odoo_model']} actualizado: ID {record.id}")
            self._avisar_si_el_nif_no_valida(record, values)

            # Procesar BOM si es producto y tiene _productos_kit_data
            if productos_kit_data is not None and self.config.get('odoo_model') == 'product.template':
                self._sync_product_bom(record, productos_kit_data)

            if not self.test_mode:
                self.env.cr.commit()

            return Response(
                response=json.dumps({
                    'message': f"{self.config['message_type']} actualizado",
                    'id': record.id
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error al actualizar {self.config['odoo_model']}: {str(e)}")
            self.env.cr.rollback()
            # Re-lanzar la excepción para que el controller active el sistema DLQ
            raise

    def _sync_product_bom(self, product_record, productos_kit_data):
        """
        Sincroniza la BOM de un producto usando el post-processor SyncProductBom

        Args:
            product_record: Registro product.template
            productos_kit_data: Lista de dicts con ProductoId y Cantidad

        Raises:
            ValueError: Si algún componente no existe o hay ciclos
        """
        from ..transformers.post_processors import SyncProductBom

        try:
            SyncProductBom.sync_bom_after_save(self.env, product_record, productos_kit_data)
        except Exception as e:
            _logger.error(
                f"Error sincronizando BOM para producto {product_record.producto_externo}: {e}",
                exc_info=True
            )
            # Re-lanzar para que vaya a DLQ
            raise
