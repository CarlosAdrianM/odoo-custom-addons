"""
Post Processors - Procesamiento posterior a la transformación de campos

Los post_processors ejecutan lógica después de procesar todos los campos.
Útil para lógica que depende de múltiples campos o de relaciones.
"""


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
