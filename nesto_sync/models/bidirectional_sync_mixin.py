"""
Bidirectional Sync Mixin - Mixin para sincronización bidireccional automática

Este mixin añade sincronización automática Odoo → Nesto a cualquier modelo.
Solo hay que:
1. Heredar de este mixin
2. Configurar la entidad en entity_configs.py con bidirectional=True

Ejemplo:
    class ResPartner(models.Model):
        _inherit = ['res.partner', 'bidirectional.sync.mixin']
"""

import logging
from odoo import models
from ..config.entity_configs import ENTITY_CONFIGS
from ..core.odoo_publisher import OdooPublisher

_logger = logging.getLogger(__name__)


class BidirectionalSyncMixin(models.AbstractModel):
    """
    Mixin abstracto para sincronización bidireccional

    Intercepta write() y create() para publicar cambios a PubSub
    """

    _name = 'bidirectional.sync.mixin'
    _description = 'Mixin para sincronización bidireccional Odoo → Nesto'

    def write(self, vals):
        """
        Override de write() para sincronizar cambios a Nesto

        Procesa en bloques para no saturar si son muchos registros
        """
        _logger.info(f"🔔 BidirectionalSyncMixin.write() llamado en {self._name} con vals: {vals}")

        # Ejecutar write original primero
        result = super(BidirectionalSyncMixin, self).write(vals)

        # Obtener entity_type para este modelo
        entity_type = self._get_entity_type_for_sync()

        if not entity_type:
            # Este modelo no tiene sincronización bidireccional configurada
            return result

        # Verificar si debemos saltarnos la sincronización
        if self._should_skip_sync():
            _logger.debug(
                f"Saltando sincronización para {len(self)} registros "
                f"(contexto skip_sync o modo instalación)"
            )
            return result

        # Sincronizar cambios
        self._sync_to_nesto(entity_type, vals)

        return result

    def create(self, vals_list):
        """
        Override de create() para sincronizar nuevos registros a Nesto

        Args:
            vals_list (list or dict): Valores para crear (puede ser dict o lista de dicts)
        """
        # Normalizar vals_list a lista
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # Ejecutar create original
        records = super(BidirectionalSyncMixin, self).create(vals_list)

        # Obtener entity_type
        entity_type = records._get_entity_type_for_sync()

        if not entity_type:
            return records

        # Verificar si debemos saltarnos la sincronización
        if records._should_skip_sync():
            _logger.debug(
                f"Saltando sincronización para {len(records)} nuevos registros "
                f"(contexto skip_sync o modo instalación)"
            )
            return records

        # Sincronizar nuevos registros
        records._sync_to_nesto(entity_type, vals_list[0] if len(vals_list) == 1 else {})

        return records

    def _get_entity_type_for_sync(self):
        """
        Determina el entity_type basado en el modelo actual

        Busca en ENTITY_CONFIGS qué entidad corresponde a este modelo
        y si tiene sincronización bidireccional activada

        Returns:
            str or None: entity_type si está configurado, None si no
        """
        for entity_type, config in ENTITY_CONFIGS.items():
            # Verificar que el modelo coincida
            if config.get('odoo_model') == self._name:
                # Verificar que tenga bidireccional activado
                if config.get('bidirectional', False):
                    return entity_type

        return None

    def _should_skip_sync(self):
        """
        Determina si debemos saltarnos la sincronización

        Casos donde NO sincronizamos:
        1. Contexto explícito skip_sync=True
        2. Estamos en modo instalación/actualización del módulo

        NOTA: NO filtramos por origen (from_nesto, from_prestashop, etc.)
        El anti-bucle se maneja mediante detección de cambios en GenericService

        Returns:
            bool: True si debemos saltar sincronización
        """
        # 1. Skip explícito (para importaciones masivas controladas)
        if self.env.context.get('skip_sync'):
            return True

        # 2. Modo instalación/actualización
        if self.env.context.get('install_mode') or self.env.context.get('module'):
            return True

        return False

    def _sync_to_nesto(self, entity_type, vals):
        """
        Sincroniza registros a Nesto en bloques

        Args:
            entity_type (str): Tipo de entidad ('cliente', 'producto', etc.)
            vals (dict): Valores que se están actualizando/creando
        """
        try:
            # Obtener tamaño de bloque desde configuración
            batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
                'nesto_sync.batch_size', 50
            ))

            # Crear publisher
            publisher = OdooPublisher(entity_type, self.env)

            # Procesar en bloques
            total = len(self)
            num_batches = (total - 1) // batch_size + 1

            if total > batch_size:
                _logger.info(
                    f"Sincronizando {total} registros de {entity_type} en {num_batches} bloques"
                )

            for i in range(0, total, batch_size):
                batch = self[i:i+batch_size]

                _logger.debug(
                    f"Procesando bloque {i//batch_size + 1}/{num_batches} "
                    f"({len(batch)} registros)"
                )

                for record in batch:
                    try:
                        # Solo sincronizar si es relevante
                        if self._should_sync_record(record, vals):
                            publisher.publish_record(record)
                    except Exception as e:
                        _logger.error(
                            f"Error sincronizando {entity_type} ID {record.id}: {str(e)}"
                        )
                        # Continuar con el siguiente registro

        except Exception as e:
            _logger.error(
                f"Error en sincronización bidireccional de {entity_type}: {str(e)}",
                exc_info=True
            )

    def _should_sync_record(self, record, vals):
        """
        Determina si un registro específico debe sincronizarse

        Algunos filtros adicionales:
        - No sincronizar partners que no sean clientes/proveedores
        - No sincronizar registros inactivos (si la entidad lo requiere)

        Args:
            record: Registro a evaluar
            vals (dict): Valores que se están modificando

        Returns:
            bool: True si debe sincronizarse
        """
        # Por ahora, sincronizar todos
        # TODO: Añadir filtros específicos por entidad si es necesario
        return True
