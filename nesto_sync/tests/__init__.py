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
