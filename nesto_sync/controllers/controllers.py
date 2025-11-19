from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response
import logging
import json
import traceback

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
        Endpoint genérico de sincronización con sistema de DLQ

        Determina el tipo de entidad y usa el processor/service apropiado.
        Implementa tracking de reintentos y Dead Letter Queue para mensajes
        que fallan repetidamente.
        """
        raw_data = request.httprequest.data
        message_id = None
        entity_type = None

        try:
            # Decodificar mensaje PubSub completo (incluyendo messageId)
            adapter = GooglePubSubMessageAdapter()
            message = adapter.decode_message(raw_data)

            # Extraer messageId del envelope de PubSub
            pubsub_envelope = json.loads(raw_data.decode('utf-8'))
            message_id = pubsub_envelope.get('message', {}).get('messageId')

            if not message_id:
                _logger.warning("Mensaje sin messageId, no se puede trackear reintentos")

            # Determinar tipo de entidad
            entity_type = self._detect_entity_type(message)
            _logger.info(f"[{message_id}] Sincronizando entidad de tipo: {entity_type}")

            # Extraer datos anidados si existen (ej: {"Cliente": {...}, "Origen": "..."})
            # Nesto envía clientes con wrapper, pero productos planos
            message_data = self._extract_entity_data(message, entity_type)

            # Obtener processor y service configurados para esta entidad
            processor = self.entity_registry.get_processor(entity_type, request.env)
            service = self.entity_registry.get_service(entity_type, request.env)

            # Procesar mensaje (transformar a formato Odoo)
            processed_data = processor.process(message_data)

            # Crear o actualizar en Odoo
            response = service.create_or_update_contact(processed_data)

            # Si llegamos aquí, el procesamiento fue exitoso
            if message_id:
                self._mark_message_success(message_id)

            return response

        except RequirePrincipalClientError as e:
            # Este error es esperado cuando un cliente secundario llega antes que el principal
            # DECISIÓN: Reintentarlo algunas veces antes de mover a DLQ
            error_msg = str(e)
            _logger.warning(f"[{message_id}] Cliente principal no existe: {error_msg}")

            if message_id:
                retry_info = self._handle_retry(
                    message_id=message_id,
                    raw_data=raw_data,
                    error_message=error_msg,
                    error_traceback=traceback.format_exc(),
                    entity_type=entity_type
                )

                if retry_info['should_move_to_dlq']:
                    # Después de varios reintentos, mover a DLQ y hacer ACK
                    _logger.error(
                        f"[{message_id}] Cliente principal no existe después de "
                        f"{retry_info['retry_count']} intentos. Moviendo a DLQ."
                    )
                    return Response(status=200, response=error_msg)
                else:
                    # Reintentar (NACK)
                    _logger.info(
                        f"[{message_id}] Reintento {retry_info['retry_count']} de "
                        f"{request.env['nesto.sync.message.retry'].MAX_RETRIES}"
                    )
                    return Response(status=500, response=error_msg)

            # Sin messageId, no podemos trackear, hacer ACK para evitar loop infinito
            return Response(status=200, response=error_msg)

        except ValueError as e:
            # Errores de validación (datos malformados, campos requeridos faltantes, etc.)
            error_msg = str(e)
            _logger.error(f"[{message_id}] Error de validación: {error_msg}")

            if message_id:
                retry_info = self._handle_retry(
                    message_id=message_id,
                    raw_data=raw_data,
                    error_message=error_msg,
                    error_traceback=traceback.format_exc(),
                    entity_type=entity_type
                )

                if retry_info['should_move_to_dlq']:
                    # Mover a DLQ y hacer ACK para que PubSub deje de reintentar
                    _logger.error(
                        f"[{message_id}] Error de validación persistente después de "
                        f"{retry_info['retry_count']} intentos. Moviendo a DLQ."
                    )
                    return Response(status=200, response=error_msg)
                else:
                    # Reintentar (NACK)
                    return Response(status=500, response=error_msg)

            # Sin messageId, hacer ACK para evitar loop infinito
            return Response(status=200, response=error_msg)

        except Exception as e:
            # Errores inesperados (bugs, excepciones no controladas, errores de BD, etc.)
            error_msg = str(e)
            error_trace = traceback.format_exc()
            _logger.error(
                f"[{message_id}] Error inesperado en sincronización: {error_msg}",
                exc_info=True
            )

            if message_id:
                retry_info = self._handle_retry(
                    message_id=message_id,
                    raw_data=raw_data,
                    error_message=error_msg,
                    error_traceback=error_trace,
                    entity_type=entity_type
                )

                if retry_info['should_move_to_dlq']:
                    # Mover a DLQ y hacer ACK
                    _logger.error(
                        f"[{message_id}] Error persistente después de "
                        f"{retry_info['retry_count']} intentos. Moviendo a DLQ."
                    )
                    return Response(status=200, response=error_msg)
                else:
                    # Reintentar (NACK)
                    return Response(status=500, response=error_msg)

            # Sin messageId, hacer ACK para evitar loop infinito
            return Response(status=200, response=error_msg)

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

    def _extract_entity_data(self, message, entity_type):
        """
        Extrae los datos de la entidad del mensaje

        Nesto envía mensajes con diferentes estructuras:
        - Clientes: {"Cliente": {...datos...}, "Origen": "...", "Usuario": "..."}
        - Productos: {"Producto": "123", "Nombre": "...", ...} (plano)

        Args:
            message: Mensaje decodificado
            entity_type: Tipo de entidad detectado

        Returns:
            dict: Datos de la entidad (extraídos o el mensaje completo si es plano)
        """
        # Mapeo de entity_type a clave de wrapper
        wrapper_keys = {
            'cliente': 'Cliente',
            'proveedor': 'Proveedor',
            'producto': 'Producto',
        }

        wrapper_key = wrapper_keys.get(entity_type)

        # Si existe la clave como objeto anidado, extraer
        if wrapper_key and wrapper_key in message:
            nested_data = message.get(wrapper_key)

            # Verificar si es un objeto (dict) o un valor simple
            if isinstance(nested_data, dict):
                _logger.debug(
                    f"Extrayendo datos anidados de clave '{wrapper_key}' "
                    f"(estructura con wrapper)"
                )
                return nested_data
            else:
                # Es un valor simple (ej: "Producto": "123"), mensaje plano
                _logger.debug(
                    f"Mensaje plano detectado - '{wrapper_key}' contiene valor simple"
                )
                return message
        else:
            # No hay wrapper, mensaje plano
            _logger.debug("Mensaje plano detectado - sin wrapper")
            return message

    def _handle_retry(self, message_id, raw_data, error_message, error_traceback, entity_type):
        """
        Maneja el sistema de reintentos y DLQ

        Args:
            message_id: ID del mensaje de PubSub
            raw_data: Datos crudos del mensaje
            error_message: Mensaje de error
            error_traceback: Stack trace del error
            entity_type: Tipo de entidad

        Returns:
            dict con keys:
                - retry_count: Número de reintentos
                - should_move_to_dlq: Si se debe mover a DLQ
        """
        # Obtener modelo de tracking de reintentos
        MessageRetry = request.env['nesto.sync.message.retry'].sudo()

        # Incrementar contador de reintentos
        retry_info = MessageRetry.increment_retry(
            message_id=message_id,
            error_message=error_message,
            entity_type=entity_type
        )

        # Si se debe mover a DLQ, crear registro
        if retry_info['should_move_to_dlq']:
            self._move_to_dlq(
                message_id=message_id,
                raw_data=raw_data,
                error_message=error_message,
                error_traceback=error_traceback,
                entity_type=entity_type,
                retry_count=retry_info['retry_count']
            )

            # Marcar en tracking como movido a DLQ
            MessageRetry.mark_moved_to_dlq(message_id)

        return retry_info

    def _move_to_dlq(self, message_id, raw_data, error_message, error_traceback, entity_type, retry_count):
        """
        Mueve un mensaje a la Dead Letter Queue

        Args:
            message_id: ID del mensaje de PubSub
            raw_data: Datos crudos del mensaje
            error_message: Mensaje de error
            error_traceback: Stack trace del error
            entity_type: Tipo de entidad
            retry_count: Número de reintentos realizados
        """
        FailedMessage = request.env['nesto.sync.failed.message'].sudo()

        # Verificar si ya existe (para evitar duplicados)
        existing = FailedMessage.search([('message_id', '=', message_id)], limit=1)

        if existing:
            # Actualizar registro existente
            existing.write({
                'error_message': error_message,
                'error_traceback': error_traceback,
                'retry_count': retry_count,
                'last_attempt_date': http.request.env.context.get('tz') or 'UTC',
                'state': 'failed'
            })
            _logger.info(f"[{message_id}] Registro DLQ actualizado")
        else:
            # Crear nuevo registro en DLQ
            from odoo import fields
            FailedMessage.create({
                'message_id': message_id,
                'raw_data': raw_data.decode('utf-8') if isinstance(raw_data, bytes) else str(raw_data),
                'entity_type': entity_type,
                'error_message': error_message,
                'error_traceback': error_traceback,
                'retry_count': retry_count,
                'state': 'failed',
                'first_attempt_date': fields.Datetime.now(),
                'last_attempt_date': fields.Datetime.now()
            })
            _logger.info(f"[{message_id}] Mensaje movido a DLQ después de {retry_count} intentos")

        # Commit para persistir el registro en DLQ
        request.env.cr.commit()

    def _mark_message_success(self, message_id):
        """
        Marca un mensaje como procesado exitosamente

        Args:
            message_id: ID del mensaje de PubSub
        """
        MessageRetry = request.env['nesto.sync.message.retry'].sudo()
        MessageRetry.mark_success(message_id)

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