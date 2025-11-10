"""
Field Transformers - Sistema de transformación de campos

Los transformers convierten valores del formato de Nesto al formato de Odoo.
Cada transformer es una clase con un método transform().
"""

from ..models.phone_processor import PhoneProcessor
from ..models.country_manager import CountryManager


class FieldTransformerRegistry:
    """Registry central de transformers disponibles"""

    _transformers = {}

    @classmethod
    def register(cls, name):
        """Decorador para registrar un transformer"""
        def decorator(transformer_class):
            cls._transformers[name] = transformer_class
            return transformer_class
        return decorator

    @classmethod
    def get(cls, name):
        """Obtiene una instancia de un transformer por nombre"""
        transformer_class = cls._transformers.get(name)
        if not transformer_class:
            raise ValueError(f"Transformer no encontrado: {name}")
        return transformer_class()

    @classmethod
    def get_all(cls):
        """Devuelve todos los transformers registrados"""
        return cls._transformers.keys()


@FieldTransformerRegistry.register('phone')
class PhoneTransformer:
    """Transforma cadena de teléfonos en mobile, phone y extras"""

    def transform(self, value, context):
        """
        Procesa números de teléfono

        Args:
            value: String con teléfonos separados por /
            context: Dict con contexto de ejecución

        Returns:
            Dict con campos mobile, phone y opcionalmente _append_comment
        """
        mobile, phone, extra = PhoneProcessor.process_phone_numbers(value)

        result = {
            'mobile': mobile,
            'phone': phone
        }

        # Los teléfonos extra se añaden al comment
        if extra:
            result['_append_comment'] = f"[Teléfonos extra] {extra}"

        return result


@FieldTransformerRegistry.register('country_state')
class CountryStateTransformer:
    """Transforma nombre de provincia a state_id de Odoo"""

    def transform(self, value, context):
        """
        Obtiene o crea provincia

        Args:
            value: Nombre de la provincia
            context: Dict con country_manager

        Returns:
            Dict con state_id
        """
        if not value:
            return {'state_id': None}

        country_manager = context.get('country_manager')
        if not country_manager:
            raise ValueError("CountryManager no disponible en contexto")

        state_id = country_manager.get_or_create_state(value)
        return {'state_id': state_id}


@FieldTransformerRegistry.register('estado_to_active')
class EstadoToActiveTransformer:
    """Convierte campo Estado de Nesto a active de Odoo"""

    def transform(self, value, context):
        """
        Convierte Estado >= 0 a active=True

        Args:
            value: Valor del campo Estado (int)
            context: Dict con contexto

        Returns:
            Dict con campo active
        """
        return {'active': value >= 0 if value is not None else True}


@FieldTransformerRegistry.register('cliente_principal')
class ClientePrincipalTransformer:
    """Transforma ClientePrincipal en is_company y type"""

    def transform(self, value, context):
        """
        Determina is_company y type según ClientePrincipal

        Args:
            value: Boolean indicando si es cliente principal
            context: Dict con contexto

        Returns:
            Dict con is_company y type
        """
        return {
            'is_company': value,
            'type': 'invoice' if value else 'delivery'
        }


@FieldTransformerRegistry.register('spain_country')
class SpainCountryTransformer:
    """Devuelve el ID de España usando CountryManager"""

    def transform(self, value, context):
        """
        Obtiene el ID de España desde la BD

        Args:
            value: No se usa (puede ser None)
            context: Dict con country_manager

        Returns:
            Dict con country_id de España
        """
        country_manager = context.get('country_manager')
        if not country_manager:
            raise ValueError("CountryManager no disponible en contexto")

        spain_id = country_manager.get_spain_id()
        return {'country_id': spain_id}


@FieldTransformerRegistry.register('country_code')
class CountryCodeTransformer:
    """Transforma código de país a country_id de Odoo"""

    def transform(self, value, context):
        """
        Busca país por código

        Args:
            value: Código ISO del país (ej: 'ES')
            context: Dict con env

        Returns:
            Dict con country_id
        """
        if not value:
            return {'country_id': None}

        env = context.get('env')
        if not env:
            raise ValueError("Environment no disponible en contexto")

        country = env['res.country'].search([('code', '=', value)], limit=1)
        return {'country_id': country.id if country else None}


@FieldTransformerRegistry.register('cargos')
class CargosTransformer:
    """Transforma código de cargo de Nesto a función de Odoo"""

    def transform(self, value, context):
        """
        Mapea cargo de Nesto a función de Odoo

        Args:
            value: Código de cargo (int)
            context: Dict con cargos_funciones

        Returns:
            Dict con function
        """
        from ..models.cargos import cargos_funciones

        function = cargos_funciones.get(value, None)
        return {'function': function}


# Transformer para precios (ejemplo para futuras entidades)
@FieldTransformerRegistry.register('price')
class PriceTransformer:
    """Transforma precio a formato Odoo"""

    def transform(self, value, context):
        """
        Convierte precio a float

        Args:
            value: Precio (string, int o float)
            context: Dict con contexto

        Returns:
            Dict con precio formateado
        """
        try:
            price = float(value) if value else 0.0
        except (ValueError, TypeError):
            price = 0.0

        return {'list_price': price}


# Transformer para cantidades (ejemplo para futuras entidades)
@FieldTransformerRegistry.register('quantity')
class QuantityTransformer:
    """Transforma cantidad a formato Odoo"""

    def transform(self, value, context):
        """
        Convierte cantidad a float

        Args:
            value: Cantidad (string, int o float)
            context: Dict con contexto

        Returns:
            Dict con cantidad formateada
        """
        try:
            qty = float(value) if value else 0.0
        except (ValueError, TypeError):
            qty = 0.0

        return {'qty_available': qty}
