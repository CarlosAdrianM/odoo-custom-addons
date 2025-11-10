"""
Event Publisher Interface - Interface para publicar eventos de sincronización

Similar a ISincronizacionEventPublisher en NestoAPI
"""

from abc import ABC, abstractmethod


class IEventPublisher(ABC):
    """
    Interface para publicar eventos de sincronización

    Implementaciones:
    - GooglePubSubPublisher: Publica a Google Cloud Pub/Sub
    - AzureServiceBusPublisher: Publica a Azure Service Bus (futuro)
    - RabbitMQPublisher: Publica a RabbitMQ (futuro)
    """

    @abstractmethod
    def publish_event(self, topic, message):
        """
        Publica un evento de sincronización

        Args:
            topic (str): Nombre del topic/queue donde publicar
            message (dict): Mensaje a publicar (será serializado a JSON)

        Returns:
            bool: True si se publicó correctamente, False en caso contrario

        Raises:
            Exception: Si hay error al publicar
        """
        pass
