"""
Transformer para UnidadMedida y Tamaño

Este transformer detecta el tipo de unidad de medida (peso, volumen, longitud)
y mapea el campo Tamaño al campo correcto en Odoo (weight, volume, product_length).

También busca la unidad de medida en product.uom y la asigna a uom_id.
"""

import logging

_logger = logging.getLogger(__name__)


class UnidadMedidaConfig:
    """Configuración de unidades de medida y conversiones"""

    # Categorías de unidades de medida
    PESO_UNITS = {
        'g': {'factor': 0.001, 'uom_search': ['g', 'gr', 'gram', 'gramo']},
        'gr': {'factor': 0.001, 'uom_search': ['g', 'gr', 'gram', 'gramo']},
        'kg': {'factor': 1, 'uom_search': ['kg', 'kilogram', 'kilogramo']},
        'lb': {'factor': 0.453592, 'uom_search': ['lb', 'pound', 'libra']},
        'oz': {'factor': 0.0283495, 'uom_search': ['oz', 'ounce', 'onza']},
        'mg': {'factor': 0.000001, 'uom_search': ['mg', 'milligram', 'miligramo']},
    }

    VOLUMEN_UNITS = {
        'l': {'factor': 0.001, 'uom_search': ['l', 'liter', 'litro']},
        'ml': {'factor': 0.000001, 'uom_search': ['ml', 'milliliter', 'mililitro']},
        'cl': {'factor': 0.00001, 'uom_search': ['cl', 'centiliter', 'centilitro']},
        'm3': {'factor': 1, 'uom_search': ['m3', 'm³', 'cubic meter', 'metro cúbico']},
        'cm3': {'factor': 0.000001, 'uom_search': ['cm3', 'cm³', 'cubic centimeter', 'centímetro cúbico']},
    }

    LONGITUD_UNITS = {
        'mm': {'factor': 0.001, 'uom_search': ['mm', 'millimeter', 'milímetro']},
        'cm': {'factor': 0.01, 'uom_search': ['cm', 'centimeter', 'centímetro']},
        'm': {'factor': 1, 'uom_search': ['m', 'meter', 'metro']},
        'km': {'factor': 1000, 'uom_search': ['km', 'kilometer', 'kilómetro']},
        'in': {'factor': 0.0254, 'uom_search': ['in', 'inch', 'pulgada']},
        'ft': {'factor': 0.3048, 'uom_search': ['ft', 'foot', 'pie']},
    }

    @classmethod
    def get_unit_type(cls, unit_str):
        """
        Detecta el tipo de unidad (peso, volumen, longitud)

        Args:
            unit_str: String de la unidad (ej: "kg", "m", "l")

        Returns:
            Tuple (type, factor) donde type es 'weight', 'volume', 'length' o None
        """
        if not unit_str:
            return None, None

        unit_lower = unit_str.strip().lower()

        # Buscar en unidades de peso
        if unit_lower in cls.PESO_UNITS:
            return 'weight', cls.PESO_UNITS[unit_lower]['factor']

        # Buscar en unidades de volumen
        if unit_lower in cls.VOLUMEN_UNITS:
            return 'volume', cls.VOLUMEN_UNITS[unit_lower]['factor']

        # Buscar en unidades de longitud
        if unit_lower in cls.LONGITUD_UNITS:
            return 'length', cls.LONGITUD_UNITS[unit_lower]['factor']

        return None, None

    @classmethod
    def get_uom_search_terms(cls, unit_str):
        """
        Obtiene términos de búsqueda para encontrar la UoM en Odoo

        Args:
            unit_str: String de la unidad

        Returns:
            List de términos de búsqueda
        """
        if not unit_str:
            return []

        unit_lower = unit_str.strip().lower()

        # Buscar en todas las categorías
        for category in [cls.PESO_UNITS, cls.VOLUMEN_UNITS, cls.LONGITUD_UNITS]:
            if unit_lower in category:
                return category[unit_lower]['uom_search']

        # Si no se encuentra, usar el string original
        return [unit_str.strip()]


def transform_unidad_medida_y_tamanno(env, nesto_data):
    """
    Transforma UnidadMedida y Tamaño a los campos correspondientes de Odoo

    Args:
        env: Environment de Odoo
        nesto_data: Dict con los datos del mensaje de Nesto

    Returns:
        Dict con los campos mapeados:
        - weight (si es unidad de peso)
        - volume (si es unidad de volumen)
        - product_length (si es unidad de longitud)
        - dimensional_uom_id (si es longitud)
        - uom_id (unidad de medida del producto)
    """
    result = {}

    # Obtener valores del mensaje
    tamanno = nesto_data.get('Tamanno')
    unidad_medida_str = nesto_data.get('UnidadMedida')

    # Si no hay tamaño o es 0, no hacer nada
    if not tamanno or tamanno == 0:
        _logger.debug("No hay Tamanno o es 0, no se mapean dimensiones")
        return result

    # Si no hay unidad de medida, loguear warning y no mapear
    if not unidad_medida_str:
        _logger.warning(f"Producto con Tamanno={tamanno} pero sin UnidadMedida. No se puede determinar el tipo de medida.")
        return result

    # Detectar tipo de unidad y factor de conversión
    unit_type, conversion_factor = UnidadMedidaConfig.get_unit_type(unidad_medida_str)

    if not unit_type:
        _logger.warning(f"UnidadMedida '{unidad_medida_str}' no reconocida. No se mapea a ningún campo.")
        return result

    # Convertir Tamaño a unidades base de Odoo
    tamanno_float = float(tamanno) if tamanno else 0.0
    valor_convertido = tamanno_float * conversion_factor

    # Mapear al campo correcto según el tipo
    if unit_type == 'weight':
        result['weight'] = valor_convertido
        _logger.info(f"Tamanno {tamanno} {unidad_medida_str} → weight = {valor_convertido} kg")

    elif unit_type == 'volume':
        result['volume'] = valor_convertido
        _logger.info(f"Tamanno {tamanno} {unidad_medida_str} → volume = {valor_convertido} m³")

    elif unit_type == 'length':
        result['product_length'] = valor_convertido
        _logger.info(f"Tamanno {tamanno} {unidad_medida_str} → product_length = {valor_convertido} m")

        # NOTA: No seteamos dimensional_uom_id aquí porque es un campo relacionado
        # El módulo product_dimension lo maneja automáticamente con valor por defecto 'metros'

    # Buscar la unidad de medida en product.uom
    uom_id = buscar_uom(env, unidad_medida_str)
    if uom_id:
        result['uom_id'] = uom_id
        result['uom_po_id'] = uom_id  # Unidad de medida de compra igual que la de venta
        _logger.info(f"UnidadMedida '{unidad_medida_str}' → uom_id = {uom_id}")
    else:
        _logger.warning(f"No se encontró UoM en Odoo para '{unidad_medida_str}'. Se deja uom_id sin mapear.")

    return result


def buscar_uom(env, unidad_medida_str):
    """
    Busca una unidad de medida en product.uom

    Args:
        env: Environment de Odoo
        unidad_medida_str: String de la unidad de medida

    Returns:
        ID de la UoM encontrada o None
    """
    if not unidad_medida_str:
        return None

    # Obtener términos de búsqueda
    search_terms = UnidadMedidaConfig.get_uom_search_terms(unidad_medida_str)

    # Buscar en product.uom por name o symbol
    for term in search_terms:
        uom = env['uom.uom'].sudo().search([
            '|',
            ('name', '=ilike', term),
            ('name', '=ilike', f"{term}%"),  # Matches "meter", "meters", etc.
        ], limit=1)

        if uom:
            _logger.debug(f"UoM encontrada: '{term}' → ID {uom.id} ({uom.name})")
            return uom.id

    # Si no se encontró, buscar por similitud en nombre
    unit_clean = unidad_medida_str.strip().lower()
    uom = env['uom.uom'].sudo().search([
        ('name', 'ilike', unit_clean)
    ], limit=1)

    if uom:
        _logger.debug(f"UoM encontrada por similitud: '{unit_clean}' → ID {uom.id} ({uom.name})")
        return uom.id

    return None
