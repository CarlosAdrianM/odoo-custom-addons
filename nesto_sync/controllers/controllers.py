from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response
import logging
import json

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
        # Opción 1: Campo explícito "Tabla" (más confiable)
        # Este campo lo añade Nesto y también _wrap_in_sync_message()
        if 'Tabla' in message:
            tabla = message['Tabla']
            # Mapear nombre de tabla a entity_type
            tabla_to_entity = {
                'Clientes': 'cliente',
                'Proveedores': 'proveedor',
                'Productos': 'producto',
            }
            if tabla in tabla_to_entity:
                return tabla_to_entity[tabla]
            else:
                raise ValueError(
                    f"Tabla '{tabla}' no está configurada. "
                    f"Tablas disponibles: {list(tabla_to_entity.keys())}"
                )

        # Opción 2: Campo entity_type explícito
        if 'entity_type' in message:
            return message['entity_type']

        # Opción 3 (fallback): Detectar por campos presentes
        # NOTA: Este método es menos confiable si el mensaje contiene múltiples entidades
        if 'Cliente' in message:
            return 'cliente'
        elif 'Proveedor' in message:
            return 'proveedor'
        elif 'Producto' in message:
            return 'producto'

        # Si no se pudo detectar, error
        raise ValueError(
            "No se pudo determinar el tipo de entidad. "
            "El mensaje debe incluir 'Tabla', 'entity_type' o campos identificables."
        )

    @http.route('/nesto_sync/logs', auth='public', methods=['GET'], csrf=False)
    def get_logs(self, limit=100, **kwargs):
        """
        Endpoint para obtener logs del módulo nesto_sync

        Similar al endpoint de logs de NestoAPI

        Args:
            limit: Número máximo de logs a retornar (default: 100)

        Returns:
            JSON con los últimos logs
        """
        try:
            from ..infrastructure.log_buffer import InMemoryLogHandler
            from datetime import datetime

            # Obtener handler singleton
            handler = InMemoryLogHandler()

            # Obtener logs
            limit_int = int(limit) if limit else 100
            logs = handler.get_logs(limit=limit_int)

            # Formatear respuesta similar a Nesto
            response_data = {
                '$id': '1',
                'totalLogs': len(logs),
                'logs': [log['message'] for log in logs],
                'timestamp': datetime.now().isoformat() + 'Z'
            }

            return Response(
                response=json.dumps(response_data, ensure_ascii=False, indent=2),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error obteniendo logs: {str(e)}", exc_info=True)
            return Response(
                response=json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )