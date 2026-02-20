"""
conftest.py para ejecutar tests de nesto_sync sin Odoo/PostgreSQL.

Parchea la metaclase de Odoo para permitir importar modelos fuera
del contexto odoo.addons.*, y registra nesto_sync bajo odoo.addons.
"""
import sys

# Parchear la metaclase de odoo.models ANTES de que se importen los modelos
import odoo.models

_original_new = odoo.models.MetaModel.__new__

def _patched_new(meta, name, bases, attrs):
    # Desactivar la aserción de módulo para tests standalone
    attrs.setdefault('_register', False)
    return _original_new(meta, name, bases, attrs)

odoo.models.MetaModel.__new__ = _patched_new

# Registrar nesto_sync bajo odoo.addons para que imports como
# 'from odoo.addons.nesto_sync...' funcionen
import nesto_sync
sys.modules['odoo.addons.nesto_sync'] = nesto_sync

# Registrar subpaquetes
for subpkg in ['core', 'config', 'models', 'transformers', 'tests', 'controllers']:
    full = f'nesto_sync.{subpkg}'
    if full in sys.modules:
        sys.modules[f'odoo.addons.{full}'] = sys.modules[full]
