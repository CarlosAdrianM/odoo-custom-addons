"""
Generic Entity Processor - Procesador genérico basado en configuración

Este procesador transforma mensajes de Nesto a formato Odoo usando
la configuración declarativa de cada entidad.
"""

import json
import logging
from ..models.country_manager import CountryManager
from ..transformers.field_transformers import FieldTransformerRegistry
from ..transformers.validators import ValidatorRegistry
from ..transformers.post_processors import PostProcessorRegistry

_logger = logging.getLogger(__name__)


class GenericEntityProcessor:
    """Processor genérico basado en configuración"""

    def __init__(self, env, entity_config):
        """
        Inicializa el processor

        Args:
            env: Environment de Odoo
            entity_config: Dict con configuración de la entidad
        """
        self.env = env
        self.config = entity_config
        self.country_manager = CountryManager(env)

    def process(self, message):
        """
        Procesa un mensaje según la configuración de la entidad

        Args:
            message: Dict o string JSON con datos de Nesto

        Returns:
            Dict con estructura {'parent': {...}, 'children': [...]}
        """
        # Si message es string, convertir a dict
        if isinstance(message, str):
            message = json.loads(message)

        _logger.info(f"Procesando mensaje de tipo {self.config.get('message_type')}")

        # 1. Validar campos requeridos
        self._validate_required_fields(message)

        # 2. Construir valores base para parent
        parent_values = self._build_values(message, is_parent=True)

        # 3. Procesar jerarquía si aplica (children)
        children_values_list = []
        if self.config.get('hierarchy', {}).get('enabled'):
            children_values_list = self._process_children(message, parent_values)

        # 4. Aplicar post_processors
        parent_values, children_values_list = self._run_post_processors(
            parent_values, children_values_list, message
        )

        # 5. Aplicar validadores personalizados
        self._run_validators(message, parent_values)

        return {
            'parent': parent_values,
            'children': children_values_list
        }

    def _build_values(self, message, is_parent=True, child_data=None):
        """
        Construye dict de valores para Odoo

        Args:
            message: Mensaje original de Nesto
            is_parent: Si es el registro parent o un child
            child_data: Datos específicos del child (si aplica)

        Returns:
            Dict con valores para Odoo
        """
        values = {}
        context = {
            'env': self.env,
            'country_manager': self.country_manager,
            'message': message,
            'nesto_data': message,  # Añadido para acceso en transformers (ej: SubgrupoTransformer)
            'is_parent': is_parent,
            'child_data': child_data,
            'entity_config': self.config
        }

        # Seleccionar mapeo de campos apropiado (parent o child)
        field_mappings = self.config.get('child_field_mappings', {}) if child_data else self.config.get('field_mappings', {})

        # Procesar cada mapeo de campo
        for nesto_field, mapping in field_mappings.items():
            self._process_field_mapping(nesto_field, mapping, message, values, context, child_data)

        # Añadir IDs externos
        self._add_external_ids(message, values, child_data)

        return values

    def _process_field_mapping(self, nesto_field, mapping, message, values, context, child_data=None):
        """
        Procesa un mapeo de campo individual

        Args:
            nesto_field: Nombre del campo en Nesto
            mapping: Dict con configuración del mapeo
            message: Mensaje original
            values: Dict donde se añaden los valores procesados
            context: Dict con contexto de ejecución
            child_data: Datos del child si aplica
        """
        # Campos fijos
        if mapping.get('type') == 'fixed':
            values[mapping['odoo_field']] = mapping['value']
            return

        # Campos de contexto (evaluados dinámicamente)
        if mapping.get('type') == 'context':
            try:
                # Evaluar expresión en contexto seguro
                values[mapping['odoo_field']] = eval(
                    mapping['source'],
                    {'env': self.env},
                    {}
                )
            except Exception as e:
                _logger.error(f"Error evaluando campo de contexto {nesto_field}: {e}")
                values[mapping['odoo_field']] = None
            return

        # Si el campo no viene en el mensaje, no tocar el valor existente
        source_data = child_data if child_data else message
        if not self._field_present_in_data(source_data, nesto_field):
            return

        # Obtener valor del mensaje
        nesto_value = self._get_nested_value(source_data, nesto_field)

        # Aplicar default si es None y hay default
        if nesto_value is None and 'default' in mapping:
            nesto_value = mapping['default']

        # Validar campo requerido
        if mapping.get('required') and not nesto_value:
            raise ValueError(f"Campo requerido faltante: {nesto_field}")

        # Mapeo simple (sin transformer)
        if 'odoo_field' in mapping and 'transformer' not in mapping:
            values[mapping['odoo_field']] = nesto_value
            return

        # Mapeo con transformer
        if 'transformer' in mapping:
            self._apply_transformer(mapping['transformer'], nesto_value, values, context)

    def _apply_transformer(self, transformer_name, value, values, context):
        """
        Aplica un transformer a un valor

        Args:
            transformer_name: Nombre del transformer
            value: Valor a transformar
            values: Dict donde se añaden los valores transformados
            context: Dict con contexto
        """
        try:
            transformer = FieldTransformerRegistry.get(transformer_name)
            transformed = transformer.transform(value, context)

            # Procesar resultado del transformer
            for key, val in transformed.items():
                if key.startswith('_append_'):
                    # Campos especiales que se concatenan
                    target = key.replace('_append_', '')
                    current = values.get(target, '')
                    values[target] = (current + '\n' + val).strip() if current else val
                else:
                    values[key] = val

        except Exception as e:
            _logger.error(f"Error en transformer {transformer_name}: {e}")
            raise

    def _add_external_ids(self, message, values, child_data=None):
        """
        Añade los campos de identificación externa

        Args:
            message: Mensaje original
            values: Dict donde se añaden los IDs
            child_data: Datos del child si aplica
        """
        external_id_mapping = self.config.get('external_id_mapping', {})

        for odoo_field, nesto_path in external_id_mapping.items():
            # Determinar la fuente de datos según el campo
            if child_data:
                # Si estamos procesando un child
                if odoo_field == 'persona_contacto_externa':
                    # persona_contacto_externa viene del child_data (Id del PersonaContacto)
                    source = child_data
                else:
                    # cliente_externo y contacto_externo vienen del message (heredados del parent)
                    source = message
            else:
                # Si es parent, todo viene del message
                source = message

            value = self._get_nested_value(source, nesto_path)

            # Caso especial: mensajes PLANOS con PersonaContacto en la raíz
            # En mensajes jerárquicos, persona_contacto_externa viene de 'Id' dentro de PersonasContacto
            # En mensajes planos, viene de 'PersonaContacto' directamente en la raíz
            # RED DE SEGURIDAD: aunque no debería llegar este tipo de mensaje,
            # lo manejamos para evitar que el nombre de la persona pise el nombre del cliente
            if odoo_field == 'persona_contacto_externa' and value is None and not child_data:
                # Buscar 'PersonaContacto' en la raíz del mensaje (formato plano)
                value = message.get('PersonaContacto')
                if value:
                    _logger.debug(
                        f"Mensaje plano detectado: usando PersonaContacto={value} "
                        f"como persona_contacto_externa"
                    )

            values[odoo_field] = value

    def _process_children(self, message, parent_values):
        """
        Procesa children (relaciones jerárquicas)

        Args:
            message: Mensaje original
            parent_values: Valores del parent ya procesados

        Returns:
            Lista de dicts con valores de cada child
        """
        hierarchy_config = self.config.get('hierarchy', {})
        child_types = hierarchy_config.get('child_types', [])

        children_values_list = []

        for child_type in child_types:
            # Obtener lista de children de este tipo del mensaje
            children_data = message.get(child_type, [])

            for child_data in children_data:
                # Procesar cada child
                child_values = self._build_values(message, is_parent=False, child_data=child_data)

                # El parent_id se asignará después en el service
                child_values['parent_id'] = None

                children_values_list.append(child_values)

        return children_values_list

    def _run_post_processors(self, parent_values, children_values_list, message):
        """
        Ejecuta post_processors configurados

        Args:
            parent_values: Valores del parent
            children_values_list: Lista de valores de children
            message: Mensaje original

        Returns:
            Tuple (parent_values, children_values_list) modificados
        """
        post_processor_names = self.config.get('post_processors', [])

        context = {
            'env': self.env,
            'message': message,
            'entity_config': self.config
        }

        for processor_name in post_processor_names:
            try:
                processor = PostProcessorRegistry.get(processor_name)
                parent_values, children_values_list = processor.process(
                    parent_values, children_values_list, context
                )
            except Exception as e:
                _logger.error(f"Error en post_processor {processor_name}: {e}")
                raise

        return parent_values, children_values_list

    def _run_validators(self, message, values):
        """
        Ejecuta validadores personalizados

        Args:
            message: Mensaje original
            values: Valores procesados

        Raises:
            Exception: Si algún validador falla
        """
        validator_names = self.config.get('validators', [])

        context = {
            'env': self.env,
            'entity_config': self.config
        }

        for validator_name in validator_names:
            try:
                validator = ValidatorRegistry.get(validator_name)
                validator.validate(message, values, context)
            except Exception as e:
                _logger.error(f"Error en validador {validator_name}: {e}")
                raise

    def _validate_required_fields(self, message):
        """
        Validación básica de campos requeridos a nivel de mensaje

        Args:
            message: Mensaje a validar

        Raises:
            ValueError: Si falta un campo requerido
        """
        # Esto se complementa con validate_required_fields validator
        # pero aquí hacemos una validación básica del mensaje en sí
        pass

    def _get_nested_value(self, data, path):
        """
        Obtiene valor de un path anidado (ej: 'PersonaContacto.Id')

        Args:
            data: Dict con datos
            path: String con path (puede tener puntos para anidamiento)

        Returns:
            Valor encontrado o None
        """
        if not path:
            return None

        if '.' not in path:
            return data.get(path)

        keys = path.split('.')
        value = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

        return value

    def _field_present_in_data(self, data, path):
        """
        Comprueba si un campo existe como clave en los datos,
        sin confundir ausencia con valor None.

        Args:
            data: Dict con datos
            path: String con path (puede tener puntos para anidamiento)

        Returns:
            True si el campo existe en los datos
        """
        if not path or not isinstance(data, dict):
            return False

        if '.' not in path:
            return path in data

        keys = path.split('.')
        current = data
        for key in keys[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        return isinstance(current, dict) and keys[-1] in current
