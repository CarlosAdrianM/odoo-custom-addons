from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response
import logging

from ..models.google_pubsub_message_adapter import GooglePubSubMessageAdapter
from ..core.entity_registry import EntityRegistry
from ..transformers.validators import RequirePrincipalClientError

_logger = logging.getLogger(__name__)


class NestoSyncController(http.Controller):
    """
    Controller para sincronización con Nesto vía Google PubSub

    Ahora usa el sistema genérico basado en EntityRegistry
    """

    def __init__(self):
        super().__init__()
        self.entity_registry = EntityRegistry()

    @http.route('/nesto_sync', auth='public', methods=['POST'], csrf=False)
    def sync_nesto(self, **post):
        """
        Endpoint genérico de sincronización

        Determina el tipo de entidad y usa el processor/service apropiado
        """
        try:
            # Decodificar mensaje PubSub
            adapter = GooglePubSubMessageAdapter()
            raw_data = request.httprequest.data
            message = adapter.decode_message(raw_data)

            # Determinar tipo de entidad
            entity_type = self._detect_entity_type(message)
            _logger.info(f"Sincronizando entidad de tipo: {entity_type}")

            # Obtener processor y service configurados para esta entidad
            processor = self.entity_registry.get_processor(entity_type, request.env)
            service = self.entity_registry.get_service(entity_type, request.env)

            # Procesar mensaje (transformar a formato Odoo)
            processed_data = processor.process(message)

            # Crear o actualizar en Odoo
            response = service.create_or_update_contact(processed_data)

            return response

        except RequirePrincipalClientError as e:
            # Este error es esperado, retornar 200 para que PubSub no reintente
            _logger.warning(f"Cliente principal no existe: {str(e)}")
            return Response(status=200, response=str(e))

        except ValueError as e:
            # Errores de validación
            _logger.error(f"Error de validación: {str(e)}")
            return Response(status=400, response=str(e))

        except Exception as e:
            # Errores inesperados
            _logger.error(f"Error inesperado en sincronización: {str(e)}", exc_info=True)
            return Response(status=500, response=str(e))

    def _detect_entity_type(self, message):
        """
        Detecta el tipo de entidad del mensaje

        Args:
            message: Dict con datos decodificados del mensaje

        Returns:
            str: Tipo de entidad ('cliente', 'proveedor', 'producto', etc.)

        Raises:
            ValueError: Si no se puede determinar el tipo
        """
        # Opción 1: Campo explícito en el mensaje
        if 'entity_type' in message:
            return message['entity_type']

        # Opción 2: Detectar por campos presentes
        # (útil para mantener compatibilidad con mensajes existentes)
        if 'Cliente' in message:
            return 'cliente'
        elif 'Proveedor' in message:
            return 'proveedor'
        elif 'Producto' in message:
            return 'producto'

        # Si no se pudo detectar, error
        raise ValueError(
            "No se pudo determinar el tipo de entidad. "
            "El mensaje debe incluir 'entity_type' o campos identificables."
        )