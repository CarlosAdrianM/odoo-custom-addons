"""
Odoo Publisher - Publisher genérico que convierte registros de Odoo a mensajes de Nesto

Arquitectura simétrica al GenericProcessor pero en dirección inversa:
- GenericProcessor: Nesto → Odoo
- OdooPublisher: Odoo → Nesto

Usa la misma configuración declarativa (entity_configs.py)
"""

import logging
from ..config.entity_configs import get_entity_config
from ..infrastructure.publisher_factory import PublisherFactory

_logger = logging.getLogger(__name__)


class OdooPublisher:
    """
    Publisher genérico que convierte registros de Odoo a mensajes de Nesto

    Similar a GenericProcessor pero en dirección inversa.
    Usa entity_configs para saber cómo mapear campos Odoo → Nesto.
    """

    def __init__(self, entity_type, env):
        """
        Inicializa el publisher

        Args:
            entity_type (str): Tipo de entidad ('cliente', 'producto', etc.)
            env: Odoo environment
        """
        self.entity_type = entity_type
        self.env = env
        self.config = get_entity_config(entity_type)
        self.publisher = PublisherFactory.create_publisher(env)

    def publish_record(self, record):
        """
        Publica un registro de Odoo a PubSub

        Args:
            record: Registro de Odoo (res.partner, product.product, etc.)

        Returns:
            bool: True si se publicó correctamente
        """
        try:
            # 1. Construir mensaje en formato Nesto
            data = self._build_message_from_odoo(record)

            # 2. Envolver en estructura ExternalSyncMessageDTO
            message = self._wrap_in_sync_message(data, record)

            # 3. Obtener topic configurado
            topic = self.config.get('pubsub_topic', 'sincronizacion-tablas')

            # 4. Publicar
            # Obtener identificadores para mejor logging
            cliente = getattr(record, 'cliente_externo', None)
            contacto = getattr(record, 'contacto_externo', None)
            persona = getattr(record, 'persona_contacto_externa', None)

            _logger.info(
                f"📨 Publicando {self.entity_type} desde Odoo: "
                f"{record._name} ID {record.id} "
                f"(Cliente={cliente}, Contacto={contacto}, PersonaContacto={persona})"
            )

            self.publisher.publish_event(topic, message)

            return True

        except Exception as e:
            _logger.error(
                f"Error publicando {self.entity_type} ID {record.id}: {str(e)}",
                exc_info=True
            )
            return False

    def _build_message_from_odoo(self, record):
        """
        Construye mensaje en formato Nesto a partir de registro Odoo

        Este método convierte de Odoo → Nesto (inverso de GenericProcessor)

        Args:
            record: Registro de Odoo

        Returns:
            dict: Mensaje en formato Nesto (idéntico al que envía NestoAPI)
        """
        message = {}

        # Mapeo de campos según reverse_field_mappings
        # SIEMPRE inferir desde field_mappings primero
        reverse_mappings = self._infer_reverse_mappings()

        # Sobrescribir con reverse_field_mappings explícitos (para identificadores)
        explicit_mappings = self.config.get('reverse_field_mappings', {})
        if explicit_mappings:
            reverse_mappings.update(explicit_mappings)

        # Procesar cada campo de Odoo → Nesto
        for odoo_field, mapping in reverse_mappings.items():
            nesto_field = mapping.get('nesto_field')
            if not nesto_field:
                continue

            # Obtener valor del registro
            value = getattr(record, odoo_field, None)

            # Serializar objetos Odoo (Many2one, Many2many, etc.)
            value = self._serialize_odoo_value(value)

            # Aplicar transformer inverso si existe
            if 'reverse_transformer' in mapping:
                transformer_name = mapping['reverse_transformer']
                value = self._apply_reverse_transformer(
                    transformer_name, value, record, mapping
                )

            # Solo añadir el campo si tiene valor real
            # Omitir: None, False, 0, string vacío
            # Excepto para campos que son genuinamente booleanos en Nesto
            if value in (None, False, '', 0) and nesto_field not in ('ClientePrincipal',):
                continue

            message[nesto_field] = value

        # Procesar children si es jerárquico
        if self.config.get('hierarchy', {}).get('enabled'):
            self._add_children_to_message(record, message)

        return message

    def _wrap_in_sync_message(self, data, record):
        """
        Envuelve los datos en el formato que espera el subscriber de Nesto

        Formato PLANO (sin Parent/Children):
        {
            "Nif": "...",
            "Cliente": "...",
            "Contacto": "...",
            "Nombre": "...",
            "Direccion": "...",
            "PersonasContacto": [...],  // ✅ Array de children directamente
            "Tabla": "Clientes",
            "Source": "Odoo"
        }

        Args:
            data (dict): Datos del registro (ya incluye PersonasContacto si aplica)
            record: Registro de Odoo

        Returns:
            dict: Mensaje en formato plano compatible con subscriber
        """
        # El mensaje ya está construido correctamente por _build_message_from_odoo
        # Solo necesitamos añadir metadatos Tabla y Source

        message = data.copy()

        # Añadir metadatos
        message["Tabla"] = self.config.get('nesto_table', 'Clientes')
        message["Source"] = "Odoo"

        return message

    def _infer_reverse_mappings(self):
        """
        Infiere reverse_field_mappings desde field_mappings

        Si no se definió reverse_field_mappings explícitamente,
        lo generamos automáticamente desde field_mappings

        Returns:
            dict: Reverse mappings inferidos
        """
        reverse = {}
        field_mappings = self.config.get('field_mappings', {})

        for nesto_field, mapping in field_mappings.items():
            # Saltar campos internos (que empiezan con _)
            # Estos son solo para sincronización Nesto → Odoo
            if nesto_field.startswith('_'):
                continue

            # Campos simples
            if 'odoo_field' in mapping:
                odoo_field = mapping['odoo_field']
                reverse[odoo_field] = {
                    'nesto_field': nesto_field
                }

            # Campos con transformer
            elif 'odoo_fields' in mapping:
                for odoo_field in mapping['odoo_fields']:
                    if odoo_field not in reverse:
                        reverse[odoo_field] = {
                            'nesto_field': nesto_field,
                            'reverse_transformer': mapping.get('transformer')
                        }

        return reverse

    def _infer_reverse_child_mappings(self):
        """
        Infiere reverse_child_field_mappings desde child_field_mappings

        Análogo a _infer_reverse_mappings pero para children

        Returns:
            dict: Reverse mappings inferidos para children
        """
        reverse = {}
        child_field_mappings = self.config.get('child_field_mappings', {})

        for nesto_field, mapping in child_field_mappings.items():
            # Saltar campos internos (que empiezan con _)
            # Estos son solo para sincronización Nesto → Odoo
            if nesto_field.startswith('_'):
                continue

            # Campos simples
            if 'odoo_field' in mapping:
                odoo_field = mapping['odoo_field']
                reverse[odoo_field] = {
                    'nesto_field': nesto_field
                }

            # Campos con transformer
            elif 'odoo_fields' in mapping:
                for odoo_field in mapping['odoo_fields']:
                    if odoo_field not in reverse:
                        reverse[odoo_field] = {
                            'nesto_field': nesto_field,
                            'reverse_transformer': mapping.get('transformer')
                        }

        return reverse

    def _apply_reverse_transformer(self, transformer_name, value, record, mapping):
        """
        Aplica transformer inverso (Odoo → Nesto)

        Por ejemplo:
        - 'phone' transformer (Nesto → Odoo): "666111111/912345678" → mobile="666111111", phone="912345678"
        - Reverse transformer (Odoo → Nesto): mobile="666111111", phone="912345678" → "666111111/912345678"

        Args:
            transformer_name (str): Nombre del transformer
            value: Valor actual del campo
            record: Registro completo (para obtener otros campos si es necesario)
            mapping: Configuración del mapeo

        Returns:
            Valor transformado
        """
        # Implementación de transformers inversos
        if transformer_name == 'phone':
            # Combinar mobile + phone en formato "mobile/phone"
            # Si solo hay mobile, devolver solo mobile
            mobile = getattr(record, 'mobile', None) or ''
            phone = getattr(record, 'phone', None) or ''

            if mobile and phone:
                return f"{mobile}/{phone}"
            elif mobile:
                return mobile
            elif phone:
                return phone
            else:
                return None

        elif transformer_name == 'country_state':
            # Convertir state_id (Many2one) a nombre de provincia EN MAYÚSCULAS
            state = getattr(record, 'state_id', None)
            if state and hasattr(state, 'name'):
                return state.name.upper()
            return None

        elif transformer_name == 'estado_to_active':
            # Convertir active (bool) a Estado (int)
            # active=True → Estado=9, active=False → Estado=-1
            active = getattr(record, 'active', True)
            return 9 if active else -1

        elif transformer_name == 'cliente_principal':
            # Convertir type a ClientePrincipal (bool)
            # type='invoice' → ClientePrincipal=true
            # type='delivery' → ClientePrincipal=false
            record_type = getattr(record, 'type', 'delivery')
            return record_type == 'invoice'

        elif transformer_name == 'spain_country':
            # No enviar country_id en mensajes salientes
            # (es un campo fijo solo para entrada)
            return None

        elif transformer_name == 'cargos':
            # Convertir function (string) a número de cargo
            # Usar mapeo inverso de cargos_funciones
            from ..models.cargos import cargos_funciones

            # Crear diccionario inverso: string → código
            funciones_cargos = {v: k for k, v in cargos_funciones.items()}

            # Buscar el código correspondiente al string
            if value and isinstance(value, str):
                cargo_code = funciones_cargos.get(value)
                return cargo_code if cargo_code else None

            return None

        else:
            # Transformer no implementado
            _logger.debug(f"Reverse transformer '{transformer_name}' no implementado, usando valor directo")
            return value

    def _add_children_to_message(self, record, message):
        """
        Añade children al mensaje si el modelo es jerárquico

        Args:
            record: Registro parent
            message (dict): Mensaje a modificar (se añade campo PersonasContacto, etc.)
        """
        hierarchy_config = self.config.get('hierarchy', {})
        parent_field = hierarchy_config.get('parent_field', 'parent_id')

        # Buscar children
        children = self.env[self.config['odoo_model']].search([
            (parent_field, '=', record.id)
        ])

        if not children:
            return

        # Obtener tipo de children desde config
        child_types = hierarchy_config.get('child_types', ['PersonasContacto'])

        # Por ahora, asumimos un solo tipo de children
        child_field_name = child_types[0] if child_types else 'PersonasContacto'

        # Construir lista de children
        children_list = []

        # Usar reverse_child_field_mappings para sincronización Odoo → Nesto
        # SIEMPRE inferir desde child_field_mappings primero
        reverse_child_mappings = self._infer_reverse_child_mappings()

        # Sobrescribir con reverse_child_field_mappings explícitos (para identificadores)
        explicit_child_mappings = self.config.get('reverse_child_field_mappings', {})
        if explicit_child_mappings:
            reverse_child_mappings.update(explicit_child_mappings)

        for child in children:
            child_data = {}

            # Mapear campos del child usando reverse mappings
            for odoo_field, mapping in reverse_child_mappings.items():
                nesto_field = mapping.get('nesto_field')
                if not nesto_field:
                    continue

                # Obtener valor del child
                value = getattr(child, odoo_field, None)

                # Serializar objetos Odoo
                value = self._serialize_odoo_value(value)

                # Aplicar transformer inverso si existe
                if 'reverse_transformer' in mapping:
                    transformer_name = mapping['reverse_transformer']
                    value = self._apply_reverse_transformer(
                        transformer_name, value, child, mapping
                    )

                # Solo añadir el campo si tiene valor real
                if value in (None, False, '', 0):
                    continue

                child_data[nesto_field] = value

            children_list.append(child_data)

        message[child_field_name] = children_list

    def _serialize_odoo_value(self, value):
        """
        Serializa valores de Odoo para JSON

        Convierte objetos Odoo (Many2one, Many2many, recordset) a valores serializables

        Args:
            value: Valor a serializar

        Returns:
            Valor serializable a JSON
        """
        # None, bool, int, float, str → ya son serializables
        if value is None or isinstance(value, (bool, int, float, str)):
            return value

        # Markup de Odoo (HTML) → convertir a string
        # Markup hereda de str pero puede causar problemas con JSON
        if hasattr(value, '__html__'):
            return str(value)

        # Many2one (ej: state_id, country_id) → devolver ID
        if hasattr(value, '_name') and hasattr(value, 'id'):
            # Es un recordset de Odoo
            if len(value) == 1:
                # Many2one: devolver solo el ID
                return value.id
            elif len(value) > 1:
                # Many2many o One2many: devolver lista de IDs
                return value.ids
            else:
                # Recordset vacío
                return None

        # Listas/tuplas → serializar cada elemento
        if isinstance(value, (list, tuple)):
            return [self._serialize_odoo_value(v) for v in value]

        # Diccionarios → serializar cada valor
        if isinstance(value, dict):
            return {k: self._serialize_odoo_value(v) for k, v in value.items()}

        # Si llegamos aquí, intentar convertir a string
        return str(value)
