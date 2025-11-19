from . import bidirectional_sync_mixin  # Importar mixin PRIMERO
from . import res_partner  # Luego el modelo que lo hereda
from . import product_template  # Modelo de productos
from . import google_pubsub_message_adapter
from . import failed_message  # DLQ para mensajes fallidos
from . import message_retry  # Tracking de reintentos

# Los imports de client_service y client_processor ya no son necesarios
# porque ahora usamos el sistema genérico (core/)