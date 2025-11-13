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
        # Filtrar recordsets vacíos
        if not self.ids:
            _logger.debug(f"Saltando write() con recordset vacío en {self._name}")
            return super(BidirectionalSyncMixin, self).write(vals)

        _logger.debug(
            f"BidirectionalSyncMixin.write() llamado en {self._name} con vals: {vals}, "
            f"IDs: {self.ids}"
        )

        # Guardar valores originales ANTES del write para detectar cambios
        # Mapeamos {record.id: {field: old_value}}
        original_values = {}
        for record in self:
            original_values[record.id] = {}
            for field in vals.keys():
                if field not in ('write_date', 'write_uid', '__last_update'):
                    if hasattr(record, field):
                        old_value = getattr(record, field, None)
                        # Serializar Many2one
                        if hasattr(old_value, 'id'):
                            old_value = old_value.id
                        original_values[record.id][field] = old_value

        # Ejecutar write original
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

        # Sincronizar cambios (pasando valores originales para comparación)
        self._sync_to_nesto(entity_type, vals, original_values)

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

        # Sincronizar nuevos registros (sin valores originales porque son nuevos)
        records._sync_to_nesto(entity_type, vals_list[0] if len(vals_list) == 1 else {}, original_values={})

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

    def _sync_to_nesto(self, entity_type, vals, original_values=None):
        """
        Sincroniza registros a Nesto en bloques

        Args:
            entity_type (str): Tipo de entidad ('cliente', 'producto', etc.)
            vals (dict): Valores que se están actualizando/creando
            original_values (dict): Valores originales antes del write {record.id: {field: old_value}}
        """
        if original_values is None:
            original_values = {}
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
                        # Pasar valores originales para comparación correcta
                        record_original_values = original_values.get(record.id, {})
                        if self._should_sync_record(record, vals, record_original_values):
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

    def _should_sync_record(self, record, vals, original_values=None):
        """
        Determina si un registro específico debe sincronizarse

        Verifica que:
        1. El registro tenga los campos de identificación necesarios (usando entity_configs)
        2. Los valores que se están modificando realmente cambiaron en ESTE registro

        Args:
            record: Registro a evaluar
            vals (dict): Valores que se están modificando
            original_values (dict): Valores originales {field: old_value}

        Returns:
            bool: True si debe sincronizarse
        """
        if original_values is None:
            original_values = {}

        # 1. Verificar identificadores externos usando configuración de la entidad
        entity_type = self._get_entity_type_for_sync()
        if entity_type:
            config = ENTITY_CONFIGS.get(entity_type, {})
            id_fields = config.get('id_fields', [])

            # Verificar que TODOS los id_fields requeridos tengan valor
            missing_fields = []
            id_values = {}
            for id_field in id_fields:
                if hasattr(record, id_field):
                    field_value = getattr(record, id_field, None)
                    id_values[id_field] = field_value
                    if not field_value:
                        missing_fields.append(id_field)
                else:
                    # El campo no existe en el modelo (configuración incorrecta)
                    _logger.warning(
                        f"Campo '{id_field}' definido en id_fields de '{entity_type}' "
                        f"pero no existe en modelo {record._name}"
                    )
                    missing_fields.append(id_field)

            if missing_fields:
                id_debug = ', '.join([f"{k}={v}" for k, v in id_values.items()])
                _logger.debug(
                    f"Saltando {entity_type} ID {record.id}: "
                    f"campos requeridos sin valor: {missing_fields} ({id_debug})"
                )
                return False

        # 2. Verificar si los valores en vals REALMENTE cambiaron en este registro
        # Esto evita publicar registros que están en el recordset pero no fueron modificados
        if vals:
            has_real_changes = False
            for field, new_value in vals.items():
                # Saltar campos de sistema
                if field in ('write_date', 'write_uid', '__last_update'):
                    continue

                # Obtener valor ORIGINAL (antes del write)
                # Si tenemos original_values, usarlo; sino obtener del registro actual
                if field in original_values:
                    old_value = original_values[field]
                elif hasattr(record, field):
                    # Fallback: obtener del registro (puede ya estar actualizado)
                    old_value = getattr(record, field, None)
                    # Serializar valores Many2one para comparación
                    if hasattr(old_value, 'id'):
                        old_value = old_value.id
                else:
                    old_value = None

                # Serializar new_value si es Many2one
                if hasattr(new_value, 'id'):
                    new_value = new_value.id

                # Comparar
                if old_value != new_value:
                    has_real_changes = True
                    _logger.debug(
                        f"Cambio detectado en registro ID {record.id}, "
                        f"campo '{field}': {old_value} → {new_value}"
                    )
                    break

            if not has_real_changes:
                # Construir mensaje de debug con los id_fields de la entidad
                entity_type = self._get_entity_type_for_sync()
                if entity_type:
                    config = ENTITY_CONFIGS.get(entity_type, {})
                    id_fields = config.get('id_fields', [])
                    id_debug = ', '.join([
                        f"{k}={getattr(record, k, None)}"
                        for k in id_fields if hasattr(record, k)
                    ])
                else:
                    id_debug = f"ID {record.id}"

                _logger.debug(
                    f"Saltando {record._name} {id_debug}: sin cambios reales"
                )
                return False

        return True
