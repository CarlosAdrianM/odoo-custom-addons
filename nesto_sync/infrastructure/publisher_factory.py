"""
Publisher Factory - Factory para crear publishers según configuración

Permite cambiar de proveedor (Google Pub/Sub, Azure Service Bus, RabbitMQ, etc.)
solo cambiando parámetros de configuración en Odoo
"""

import logging
from ..interfaces.event_publisher import IEventPublisher
from .google_pubsub_publisher import GooglePubSubPublisher

_logger = logging.getLogger(__name__)


class PublisherFactory:
    """
    Factory para crear publishers de eventos

    Lee la configuración de Odoo (ir.config_parameter) y crea
    el publisher apropiado según el proveedor configurado
    """

    @staticmethod
    def create_publisher(env) -> IEventPublisher:
        """
        Crea un publisher según configuración de Odoo

        Lee los parámetros:
        - nesto_sync.event_publisher: Proveedor a usar (google_pubsub, azure_servicebus, rabbitmq)
        - nesto_sync.google_project_id: ID del proyecto de Google Cloud (si usa google_pubsub)
        - nesto_sync.google_credentials_path: Path a credenciales (opcional)

        Args:
            env: Odoo environment

        Returns:
            IEventPublisher: Implementación configurada

        Raises:
            ValueError: Si el proveedor no está soportado o falta configuración
        """
        config = env['ir.config_parameter'].sudo()

        # Obtener proveedor configurado (por defecto: google_pubsub)
        provider = config.get_param('nesto_sync.event_publisher', 'google_pubsub')

        _logger.info(f"Creando publisher para proveedor: {provider}")

        if provider == 'google_pubsub':
            return PublisherFactory._create_google_pubsub_publisher(config)

        elif provider == 'azure_servicebus':
            raise NotImplementedError(
                "Azure Service Bus no está implementado aún. "
                "Usa 'google_pubsub' o implementa AzureServiceBusPublisher"
            )

        elif provider == 'rabbitmq':
            raise NotImplementedError(
                "RabbitMQ no está implementado aún. "
                "Usa 'google_pubsub' o implementa RabbitMQPublisher"
            )

        else:
            raise ValueError(
                f"Proveedor no soportado: {provider}. "
                f"Valores válidos: google_pubsub, azure_servicebus, rabbitmq"
            )

    @staticmethod
    def _create_google_pubsub_publisher(config) -> GooglePubSubPublisher:
        """
        Crea publisher de Google Pub/Sub

        Args:
            config: Objeto ir.config_parameter para leer configuración

        Returns:
            GooglePubSubPublisher: Publisher configurado

        Raises:
            ValueError: Si falta configuración obligatoria
        """
        project_id = config.get_param('nesto_sync.google_project_id')

        if not project_id:
            raise ValueError(
                "Falta configuración obligatoria: nesto_sync.google_project_id. "
                "Configúralo en Configuración → Parámetros del Sistema"
            )

        credentials_path = config.get_param('nesto_sync.google_credentials_path')

        _logger.info(
            f"Configurando Google Pub/Sub Publisher: "
            f"project_id={project_id}, "
            f"credentials={'custom' if credentials_path else 'default'}"
        )

        return GooglePubSubPublisher(
            project_id=project_id,
            credentials_path=credentials_path
        )

    # Métodos para crear otros publishers (futuro)

    @staticmethod
    def _create_azure_servicebus_publisher(config):
        """
        Crea publisher de Azure Service Bus (futuro)

        Parámetros necesarios:
        - nesto_sync.azure_connection_string
        """
        raise NotImplementedError("Azure Service Bus publisher no implementado")

    @staticmethod
    def _create_rabbitmq_publisher(config):
        """
        Crea publisher de RabbitMQ (futuro)

        Parámetros necesarios:
        - nesto_sync.rabbitmq_host
        - nesto_sync.rabbitmq_port
        - nesto_sync.rabbitmq_username
        - nesto_sync.rabbitmq_password
        """
        raise NotImplementedError("RabbitMQ publisher no implementado")
