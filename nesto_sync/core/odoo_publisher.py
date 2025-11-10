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
            message = self._build_message_from_odoo(record)

            # 2. Obtener topic configurado
            topic = self.config.get('pubsub_topic', 'sincronizacion-tablas')

            # 3. Publicar
            _logger.info(
                f"Publicando {self.entity_type} desde Odoo: "
                f"{record._name} ID {record.id}"
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
        reverse_mappings = self.config.get('reverse_field_mappings', {})

        if not reverse_mappings:
            # Si no hay reverse_mappings, inferir desde field_mappings
            reverse_mappings = self._infer_reverse_mappings()

        # Procesar cada campo de Odoo → Nesto
        for odoo_field, mapping in reverse_mappings.items():
            nesto_field = mapping.get('nesto_field')
            if not nesto_field:
                continue

            # Obtener valor del registro
            value = getattr(record, odoo_field, None)

            # Aplicar transformer inverso si existe
            if 'reverse_transformer' in mapping:
                transformer_name = mapping['reverse_transformer']
                value = self._apply_reverse_transformer(
                    transformer_name, value, record, mapping
                )

            message[nesto_field] = value

        # Añadir campos de contexto
        message['Tabla'] = self.config.get('nesto_table', 'Clientes')
        message['Source'] = 'Odoo'

        # Procesar children si es jerárquico
        if self.config.get('hierarchy', {}).get('enabled'):
            self._add_children_to_message(record, message)

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
        # TODO: Implementar transformers inversos
        # Por ahora, retornamos el valor sin transformar
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
        child_mappings = self.config.get('child_field_mappings', {})

        for child in children:
            child_data = {}

            # Mapear campos del child
            for nesto_field, mapping in child_mappings.items():
                if 'odoo_field' in mapping:
                    odoo_field = mapping['odoo_field']
                    child_data[nesto_field] = getattr(child, odoo_field, None)

            children_list.append(child_data)

        message[child_field_name] = children_list
