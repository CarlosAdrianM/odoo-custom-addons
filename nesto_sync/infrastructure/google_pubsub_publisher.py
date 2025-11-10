"""
Google Cloud Pub/Sub Publisher - Implementación de IEventPublisher para Google Pub/Sub

Similar a GooglePubSubEventPublisher en NestoAPI
"""

import json
import logging
from google.cloud import pubsub_v1
from google.api_core.exceptions import GoogleAPIError

from ..interfaces.event_publisher import IEventPublisher

_logger = logging.getLogger(__name__)


class GooglePubSubPublisher(IEventPublisher):
    """
    Implementación de IEventPublisher usando Google Cloud Pub/Sub

    Esta clase publica mensajes a Google Cloud Pub/Sub de manera asíncrona.
    """

    def __init__(self, project_id, credentials_path=None):
        """
        Inicializa el publisher de Google Pub/Sub

        Args:
            project_id (str): ID del proyecto de Google Cloud
            credentials_path (str, optional): Path al archivo de credenciales JSON
                Si no se proporciona, usa las credenciales por defecto del sistema
        """
        self.project_id = project_id

        # Configurar credenciales si se proporcionan
        if credentials_path:
            import os
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

        # Crear cliente publisher (lazy initialization)
        self._publisher = None

    @property
    def publisher(self):
        """Lazy initialization del publisher client"""
        if self._publisher is None:
            self._publisher = pubsub_v1.PublisherClient()
        return self._publisher

    def publish_event(self, topic, message):
        """
        Publica un evento a Google Pub/Sub

        Args:
            topic (str): Nombre del topic (sin incluir project_id)
            message (dict): Mensaje a publicar (será serializado a JSON)

        Returns:
            bool: True si se publicó correctamente

        Raises:
            GoogleAPIError: Si hay error al publicar
            ValueError: Si el mensaje no es serializable
        """
        try:
            # Serializar mensaje a JSON
            message_json = json.dumps(message, ensure_ascii=False)
            message_bytes = message_json.encode('utf-8')

            # Construir topic path completo
            topic_path = self.publisher.topic_path(self.project_id, topic)

            # Publicar mensaje
            future = self.publisher.publish(topic_path, message_bytes)

            # Esperar confirmación (blocking)
            message_id = future.result(timeout=30)

            _logger.info(
                f"Mensaje publicado a {topic}: message_id={message_id}, "
                f"size={len(message_bytes)} bytes"
            )

            return True

        except GoogleAPIError as e:
            _logger.error(f"Error de Google API publicando a {topic}: {str(e)}")
            raise

        except ValueError as e:
            _logger.error(f"Error serializando mensaje a JSON: {str(e)}")
            raise

        except Exception as e:
            _logger.error(f"Error inesperado publicando a {topic}: {str(e)}", exc_info=True)
            raise

    def publish_event_async(self, topic, message, callback=None):
        """
        Publica un evento de manera asíncrona (no blocking)

        Args:
            topic (str): Nombre del topic
            message (dict): Mensaje a publicar
            callback (callable, optional): Función a llamar cuando se complete

        Returns:
            Future: Objeto future para tracking asíncrono
        """
        try:
            message_json = json.dumps(message, ensure_ascii=False)
            message_bytes = message_json.encode('utf-8')

            topic_path = self.publisher.topic_path(self.project_id, topic)
            future = self.publisher.publish(topic_path, message_bytes)

            if callback:
                future.add_done_callback(callback)

            return future

        except Exception as e:
            _logger.error(f"Error iniciando publicación asíncrona a {topic}: {str(e)}")
            raise
