# tests/__init__.py
# Tests legacy
from . import test_message_parser
from . import test_google_pubsub_adapter
from . import test_client_service
from . import test_controller
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
