"""
Stock Guard - Protege los quants de Odoo frente a cantidades VIRTUALES de Nesto

Issue #6 (espejo de NestoAPI#412): desde el 27/08/2026 cada entrada de `Stocks`
del mensaje `Tabla="Productos"` incluye el campo `CantidadMontable`: unidades
ADICIONALES del kit que se podrían montar a partir del stock de sus componentes.

`CantidadMontable` es un derivado VIRTUAL pensado para la tienda online, NO es
stock físico. Sumarlo a los quants duplicaría inventario, porque el físico de
los componentes ya está contabilizado en los quants de los propios componentes.

Contrato de `Stocks[]` (una entrada por almacén: ALG, REI, ALC), confirmado con
NestoAPI el 27/08/2026 contra la base de datos:

    Almacen                 str       código de almacén
    Stock                   int       FÍSICO real (suma del extracto de producto)
    PendienteEntregar       int       comprometido en pedidos de venta pendientes
    PendienteRecibir        int       pedidos de compra enviados, sin recibir
    PendienteReposicion     int       traspasos internos en camino al almacén
    FechaEstimadaRecepcion  datetime  ver FECHA_SIN_RECEPCION_PENDIENTE
    CantidadDisponible      int       DERIVADO: Stock - PendienteEntregar
                                      + PendienteReposicion (mínimo 0)
    CantidadMontable        int       VIRTUAL: el único que "inventa" unidades

Si algún día se mapea el stock a quants, el campo a usar es `Stock` por almacén
(ver QUANT_SOURCE_FIELD). `CantidadDisponible` es aritmética de los otros: no
inventa stock, pero tampoco es físico.

La guarda es una ALLOWLIST (la lista de campos es corta y estable, así que un
campo nuevo se descarta por defecto en vez de colarse), con dos capas:

1. `assert_stock_mapping_is_safe()`: falla al arrancar si alguna configuración
   de entidad mapea un campo virtual o un campo de `Stocks[]` fuera de la
   allowlist, tanto entrante como inverso.
2. `sanitize_message()`: deja en cada entrada de `Stocks` solo los campos
   permitidos ANTES de construir valores para Odoo, de modo que ni transformers
   ni post-processors puedan ver un campo virtual aunque se escriba un mapeo de
   stocks más adelante.
"""

import logging

_logger = logging.getLogger(__name__)

# Campos de `Stocks[]` con un valor real detrás
STOCK_FIELDS_REALES = frozenset({
    'Almacen',
    'Stock',
    'PendienteEntregar',
    'PendienteRecibir',
    'PendienteReposicion',
    'FechaEstimadaRecepcion',
})

# Derivados aritméticos de los anteriores: no inventan stock, pero no son físicos
STOCK_FIELDS_DERIVADOS = frozenset({'CantidadDisponible'})

# Campos VIRTUALES: inventan unidades. NUNCA deben llegar a un quant de Odoo
VIRTUAL_STOCK_FIELDS = frozenset({'CantidadMontable'})

# Allowlist: lo único que se deja pasar de cada entrada de `Stocks[]`
STOCK_FIELDS_PERMITIDOS = STOCK_FIELDS_REALES | STOCK_FIELDS_DERIVADOS

# Clave del mensaje de Nesto que contiene la lista de stocks por almacén
STOCKS_KEY = 'Stocks'

# Campo a usar como origen del stock físico si algún día se mapean quants
QUANT_SOURCE_FIELD = 'Stock'

# `FechaEstimadaRecepcion` usa este centinela cuando NO hay compras pendientes.
# No es una fecha real: no se debe mostrar ni usar en cálculos de plazos.
FECHA_SIN_RECEPCION_PENDIENTE = '9999-12-31'


def strip_virtual_stock_fields(stock_entry):
    """
    Devuelve una entrada de stock con solo los campos permitidos

    Args:
        stock_entry: Dict con los datos de stock de un almacén

    Returns:
        Dict sin campos virtuales ni desconocidos (el mismo objeto si no había
        nada que quitar, para no copiar sin necesidad)
    """
    if not isinstance(stock_entry, dict):
        return stock_entry

    descartados = set(stock_entry) - STOCK_FIELDS_PERMITIDOS
    if not descartados:
        return stock_entry

    virtuales = descartados & VIRTUAL_STOCK_FIELDS
    if virtuales:
        _logger.debug(
            "Ignorando campos de stock virtuales %s: son cantidades derivadas "
            "de los componentes, no stock físico (Issue #6)",
            sorted(virtuales)
        )

    desconocidos = descartados - VIRTUAL_STOCK_FIELDS
    if desconocidos:
        # Un campo nuevo en el contrato de Nesto: se descarta por seguridad,
        # pero se avisa para poder añadirlo a la allowlist si procede
        _logger.warning(
            "Campos de stock no reconocidos, descartados por la allowlist: %s. "
            "Si son legítimos, añádelos a STOCK_FIELDS_REALES o "
            "STOCK_FIELDS_DERIVADOS en core/stock_guard.py",
            sorted(desconocidos)
        )

    return {
        key: value
        for key, value in stock_entry.items()
        if key in STOCK_FIELDS_PERMITIDOS
    }


def sanitize_stocks(stocks):
    """
    Devuelve la lista de stocks con solo los campos permitidos

    Args:
        stocks: Lista de dicts de stock por almacén

    Returns:
        Lista saneada (el mismo objeto si no había nada que quitar)
    """
    if not isinstance(stocks, list):
        return stocks

    saneados = [strip_virtual_stock_fields(entry) for entry in stocks]

    if all(saneado is original for saneado, original in zip(saneados, stocks)):
        return stocks

    return saneados


def sanitize_message(message):
    """
    Devuelve el mensaje con los stocks saneados

    No muta el mensaje original (se conserva íntegro para logs y DLQ) y
    devuelve el mismo objeto si no había nada que sanear.

    Args:
        message: Dict con el mensaje de Nesto

    Returns:
        Dict saneado
    """
    if not isinstance(message, dict):
        return message

    stocks = message.get(STOCKS_KEY)
    sanitized_stocks = sanitize_stocks(stocks)

    if sanitized_stocks is stocks:
        return message

    sanitized = dict(message)
    sanitized[STOCKS_KEY] = sanitized_stocks
    return sanitized


def _iter_mapped_nesto_fields(entity_config):
    """
    Recorre los nombres de campo de Nesto que una entidad mapea

    Incluye los mapeos entrantes (Nesto → Odoo) y los inversos (Odoo → Nesto):
    Odoo tampoco debe publicar campos virtuales, los calcula Nesto a partir de
    los componentes.

    Args:
        entity_config: Dict con la configuración de la entidad

    Yields:
        String con el nombre (o path) del campo de Nesto
    """
    for mappings_key in ('field_mappings', 'child_field_mappings'):
        for nesto_field in entity_config.get(mappings_key, {}):
            yield nesto_field

    for mappings_key in ('reverse_field_mappings', 'reverse_child_field_mappings'):
        for mapping in entity_config.get(mappings_key, {}).values():
            if isinstance(mapping, dict) and mapping.get('nesto_field'):
                yield mapping['nesto_field']


def assert_stock_mapping_is_safe(entity_config):
    """
    Verifica que una configuración de entidad no mapea stock inseguro

    Rechaza dos cosas:
    - Cualquier referencia a un campo de VIRTUAL_STOCK_FIELDS
    - Cualquier campo bajo `Stocks.` que no esté en la allowlist

    Args:
        entity_config: Dict con la configuración de la entidad

    Raises:
        ValueError: Si algún mapeo referencia un campo de stock inseguro
    """
    entidad = entity_config.get('message_type')

    for nesto_field in _iter_mapped_nesto_fields(entity_config):
        segmentos = str(nesto_field).split('.')

        if VIRTUAL_STOCK_FIELDS.intersection(segmentos):
            raise ValueError(
                f"La entidad '{entidad}' mapea el campo virtual de stock "
                f"'{nesto_field}'. Los campos {sorted(VIRTUAL_STOCK_FIELDS)} "
                f"NUNCA deben llegar a los quants de Odoo: duplicarían el "
                f"inventario de los componentes del kit (Issue #6). El stock "
                f"físico está en '{QUANT_SOURCE_FIELD}' por almacén."
            )

        if segmentos[0] == STOCKS_KEY and len(segmentos) > 1:
            if segmentos[-1] not in STOCK_FIELDS_PERMITIDOS:
                raise ValueError(
                    f"La entidad '{entidad}' mapea '{nesto_field}', que no está "
                    f"en la allowlist de campos de stock "
                    f"{sorted(STOCK_FIELDS_PERMITIDOS)}. Si el campo es "
                    f"legítimo, añádelo a STOCK_FIELDS_REALES o "
                    f"STOCK_FIELDS_DERIVADOS en core/stock_guard.py (Issue #6)."
                )
