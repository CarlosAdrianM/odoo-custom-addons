# tests/__init__.py
# Tests legacy
from . import test_message_parser
from . import test_google_pubsub_adapter
from . import test_client_service
from . import test_client_processor

# Tests nueva arquitectura
from . import test_transformers
from . import test_validators
from . import test_post_processors
from . import test_generic_service
from . import test_integration_end_to_end

# Tests sincronización bidireccional
from . import test_bidirectional_sync

# Tests BOM (Bills of Materials)
from . import test_bom_sync
from . import test_bom_integration

# Tests OdooPublisher (Odoo → Nesto)
from . import test_odoo_publisher

# Tests de regresión críticos
from . import test_nombre_regression

# Tests mensajes parciales (Issue #3)
from . import test_partial_messages

# Tests guarda stock virtual (Issue #6)
from . import test_stock_virtual_guard

# Tests fechas de compras (Issue #8)
from . import test_fechas_compras

# Tests del sistema de DLQ. El fichero existe desde hace tiempo, pero no estaba
# importado aquí, así que sus TransactionCase no se han ejecutado nunca bajo
# Odoo: el mismo agujero que #12, solo que en silencio y sin fallar.
from . import test_dlq_system

# Tests del filtrado de CodigoBarras (Issue #21)
from . import test_codigo_barras

# Tests del NIF sin validar (Issue #18)
from . import test_nif

# Tests del Nombre vacío (Issue #19)
from . import test_nombre_vacio
