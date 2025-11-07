"""
Validators - Validadores personalizados para entidades

Los validadores comprueban lógica de negocio compleja antes de crear/actualizar.
"""


class RequirePrincipalClientError(Exception):
    """Excepción cuando se requiere crear primero el cliente principal"""
    pass


class ValidatorRegistry:
    """Registry central de validadores disponibles"""

    _validators = {}

    @classmethod
    def register(cls, name):
        """Decorador para registrar un validador"""
        def decorator(validator_class):
            cls._validators[name] = validator_class
            return validator_class
        return decorator

    @classmethod
    def get(cls, name):
        """Obtiene una instancia de un validador por nombre"""
        validator_class = cls._validators.get(name)
        if not validator_class:
            raise ValueError(f"Validador no encontrado: {name}")
        return validator_class()

    @classmethod
    def get_all(cls):
        """Devuelve todos los validadores registrados"""
        return cls._validators.keys()


@ValidatorRegistry.register('validate_cliente_principal_exists')
class ValidateClientePrincipalExists:
    """Valida que existe el cliente principal antes de crear un contacto de entrega"""

    def validate(self, message, values, context):
        """
        Verifica que el cliente principal existe si no es cliente principal

        Args:
            message: Mensaje original de Nesto
            values: Valores procesados para Odoo
            context: Dict con env y otros datos

        Raises:
            RequirePrincipalClientError: Si no existe el cliente principal
        """
        # Si es cliente principal, no hay que validar
        cliente_principal = message.get('ClientePrincipal', False)
        if cliente_principal:
            return

        # Si no es principal, verificar que existe el parent
        env = context.get('env')
        cliente_externo = values.get('cliente_externo')

        parent_partner = env['res.partner'].sudo().search([
            ('cliente_externo', '=', cliente_externo),
            ('parent_id', '=', False)
        ], limit=1)

        if not parent_partner:
            raise RequirePrincipalClientError(
                f"Es necesario crear primero el cliente principal para el cliente {cliente_externo}"
            )

        # Si existe, asignar el parent_id
        values['parent_id'] = parent_partner.id


@ValidatorRegistry.register('validate_required_fields')
class ValidateRequiredFields:
    """Valida que los campos requeridos estén presentes"""

    def validate(self, message, values, context):
        """
        Verifica campos obligatorios

        Args:
            message: Mensaje original de Nesto
            values: Valores procesados para Odoo
            context: Dict con config de la entidad

        Raises:
            ValueError: Si falta un campo requerido
        """
        entity_config = context.get('entity_config', {})
        field_mappings = entity_config.get('field_mappings', {})

        for nesto_field, mapping in field_mappings.items():
            if mapping.get('required'):
                # Obtener valor del mensaje
                nesto_value = self._get_nested_value(message, nesto_field)

                # Verificar si está presente y no está vacío
                if nesto_value is None or (isinstance(nesto_value, str) and not nesto_value.strip()):
                    raise ValueError(f"Campo requerido faltante: {nesto_field}")

    def _get_nested_value(self, data, path):
        """Obtiene valor de un path anidado (ej: 'PersonaContacto.Id')"""
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


@ValidatorRegistry.register('validate_nif_format')
class ValidateNifFormat:
    """Valida formato de NIF/CIF español (ejemplo)"""

    def validate(self, message, values, context):
        """
        Verifica formato básico de NIF/CIF

        Args:
            message: Mensaje original de Nesto
            values: Valores procesados para Odoo
            context: Dict con contexto

        Raises:
            ValueError: Si el formato no es válido
        """
        nif = values.get('vat')
        if not nif:
            return

        # Validación básica: longitud entre 8 y 10 caracteres
        if len(nif) < 8 or len(nif) > 10:
            raise ValueError(f"Formato de NIF inválido: {nif}")

        # Aquí se podría añadir lógica más compleja de validación de NIF
        # (algoritmo de verificación de letra, etc.)
