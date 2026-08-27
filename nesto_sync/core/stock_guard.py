"""
Stock Guard - Protege los quants de Odoo frente a cantidades VIRTUALES de Nesto

Issue #6 (espejo de NestoAPI#412): desde el 27/08/2026 cada entrada de `Stocks`
del mensaje `Tabla="Productos"` incluye el campo `CantidadMontable`: unidades
ADICIONALES del kit que se podrían montar a partir del stock de sus componentes.

`CantidadMontable` es un derivado VIRTUAL pensado para la tienda online, NO es
stock físico. Sumarlo a los quants duplicaría inventario, porque el físico de
los componentes ya está contabilizado en los quants de los propios componentes.

El stock físico del kit sigue viajando en `Stock` / `CantidadDisponible`.

Este módulo implementa la guarda en dos capas:

1. `assert_config_ignores_virtual_stock()`: falla al arrancar si alguna
   configuración de entidad llega a mapear un campo virtual (entrante o
   saliente). Impide que nadie lo "cablee" por descuido en el futuro.
2. `sanitize_message()`: elimina los campos virtuales del mensaje ANTES de
   construir valores para Odoo, de modo que ni transformers ni post-processors
   puedan verlos aunque se escriba un mapeo de stocks más adelante.
"""

import logging

_logger = logging.getLogger(__name__)

# Campos de `Stocks[]` que NUNCA deben llegar a un quant de Odoo
VIRTUAL_STOCK_FIELDS = frozenset({'CantidadMontable'})

# Clave del mensaje de Nesto que contiene la lista de stocks por almacén
STOCKS_KEY = 'Stocks'


def strip_virtual_stock_fields(stock_entry):
    """
    Devuelve una entrada de stock sin los campos virtuales

    Args:
        stock_entry: Dict con los datos de stock de un almacén

    Returns:
        Dict sin los campos de VIRTUAL_STOCK_FIELDS (el mismo objeto si no los
        tenía, para no copiar sin necesidad)
    """
    if not isinstance(stock_entry, dict):
        return stock_entry

    if not VIRTUAL_STOCK_FIELDS.intersection(stock_entry):
        return stock_entry

    return {
        key: value
        for key, value in stock_entry.items()
        if key not in VIRTUAL_STOCK_FIELDS
    }


def sanitize_stocks(stocks):
    """
    Devuelve la lista de stocks sin los campos virtuales

    Args:
        stocks: Lista de dicts de stock por almacén

    Returns:
        Lista saneada (el mismo objeto si no había nada que quitar)
    """
    if not isinstance(stocks, list):
        return stocks

    if not any(
        isinstance(entry, dict) and VIRTUAL_STOCK_FIELDS.intersection(entry)
        for entry in stocks
    ):
        return stocks

    return [strip_virtual_stock_fields(entry) for entry in stocks]


def sanitize_message(message):
    """
    Devuelve el mensaje sin los campos de stock virtuales

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

    _logger.debug(
        "Ignorando campos de stock virtuales %s: son cantidades derivadas de "
        "los componentes, no stock físico (Issue #6)",
        sorted(VIRTUAL_STOCK_FIELDS)
    )

    sanitized = dict(message)
    sanitized[STOCKS_KEY] = sanitized_stocks
    return sanitized


def assert_config_ignores_virtual_stock(entity_config):
    """
    Verifica que una configuración de entidad no mapea campos virtuales

    Se comprueban tanto los mapeos entrantes (Nesto → Odoo) como los inversos
    (Odoo → Nesto): Odoo tampoco debe publicar `CantidadMontable`, lo calcula
    Nesto a partir de los componentes.

    Args:
        entity_config: Dict con la configuración de la entidad

    Raises:
        ValueError: Si algún mapeo referencia un campo de VIRTUAL_STOCK_FIELDS
    """
    incoming = list(entity_config.get('field_mappings', {})) + \
        list(entity_config.get('child_field_mappings', {}))

    outgoing = [
        mapping.get('nesto_field')
        for mappings_key in ('reverse_field_mappings', 'reverse_child_field_mappings')
        for mapping in entity_config.get(mappings_key, {}).values()
        if isinstance(mapping, dict)
    ]

    for nesto_field in incoming + outgoing:
        if not nesto_field:
            continue
        if VIRTUAL_STOCK_FIELDS.intersection(str(nesto_field).split('.')):
            raise ValueError(
                f"La entidad '{entity_config.get('message_type')}' mapea el campo "
                f"virtual de stock '{nesto_field}'. Los campos "
                f"{sorted(VIRTUAL_STOCK_FIELDS)} NUNCA deben llegar a los quants "
                f"de Odoo: duplicarían el inventario de los componentes del kit "
                f"(Issue #6). El stock físico viaja en Stock/CantidadDisponible."
            )
