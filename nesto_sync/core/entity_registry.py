"""
Entity Registry - Registro central de entidades configuradas

El registry es el punto de entrada para obtener processors y services
configurados para cada tipo de entidad.
"""

from .generic_processor import GenericEntityProcessor
from .generic_service import GenericEntityService


class EntityRegistry:
    """Registry central de entidades sincronizables"""

    def __init__(self):
        """Inicializa el registry con las configuraciones disponibles"""
        from ..config.entity_configs import ENTITY_CONFIGS
        self.configs = ENTITY_CONFIGS

    def get_config(self, entity_type):
        """
        Obtiene la configuración de una entidad

        Args:
            entity_type: Tipo de entidad (ej: 'cliente', 'proveedor')

        Returns:
            Dict con la configuración de la entidad

        Raises:
            ValueError: Si la entidad no está configurada
        """
        if entity_type not in self.configs:
            raise ValueError(f"Entidad no configurada: {entity_type}")
        return self.configs[entity_type]

    def get_processor(self, entity_type, env):
        """
        Obtiene un processor configurado para una entidad

        Args:
            entity_type: Tipo de entidad
            env: Environment de Odoo

        Returns:
            Instancia de GenericEntityProcessor configurada
        """
        config = self.get_config(entity_type)
        return GenericEntityProcessor(env, config)

    def get_service(self, entity_type, env, test_mode=False):
        """
        Obtiene un service configurado para una entidad

        Args:
            entity_type: Tipo de entidad
            env: Environment de Odoo
            test_mode: Si True, no hace commits a la BD

        Returns:
            Instancia de GenericEntityService configurada
        """
        config = self.get_config(entity_type)
        return GenericEntityService(env, config, test_mode)

    def register_entity(self, entity_type, config):
        """
        Registra una nueva entidad dinámicamente

        Args:
            entity_type: Tipo de entidad
            config: Dict con la configuración de la entidad

        Útil para módulos que extiendan nesto_sync y quieran añadir
        sus propias entidades sin modificar entity_configs.py
        """
        self.configs[entity_type] = config

    def get_registered_entities(self):
        """
        Devuelve lista de tipos de entidad registrados

        Returns:
            List con nombres de entidades disponibles
        """
        return list(self.configs.keys())

    def is_registered(self, entity_type):
        """
        Verifica si una entidad está registrada

        Args:
            entity_type: Tipo de entidad

        Returns:
            bool: True si la entidad está registrada
        """
        return entity_type in self.configs
