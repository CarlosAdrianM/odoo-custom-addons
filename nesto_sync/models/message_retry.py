# -*- coding: utf-8 -*-
"""
Sistema de tracking de reintentos para mensajes de PubSub.

Esta tabla temporal almacena el contador de reintentos por messageId,
permitiendo detectar mensajes que fallan repetidamente.
"""

from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class NestoSyncMessageRetry(models.Model):
    """Tracking temporal de reintentos de mensajes."""

    _name = 'nesto.sync.message.retry'
    _description = 'Tracking de reintentos de mensajes PubSub'
    _order = 'last_retry_date desc'

    # Configuración de límites
    MAX_RETRIES = 3  # Número máximo de reintentos antes de mover a DLQ
    CLEANUP_DAYS = 7  # Días para mantener registros de reintentos exitosos

    message_id = fields.Char(
        string='Message ID',
        help='ID único del mensaje de Google PubSub',
        required=True,
        index=True
    )

    retry_count = fields.Integer(
        string='Contador de reintentos',
        default=0,
        help='Número de veces que ha fallado el procesamiento'
    )

    first_retry_date = fields.Datetime(
        string='Primer intento',
        default=fields.Datetime.now,
        required=True
    )

    last_retry_date = fields.Datetime(
        string='Último reintento',
        default=fields.Datetime.now,
        required=True
    )

    last_error = fields.Text(
        string='Último error',
        help='Mensaje del último error encontrado'
    )

    entity_type = fields.Char(
        string='Tipo de entidad',
        help='Tipo de entidad que se intentó procesar'
    )

    state = fields.Selection([
        ('retrying', 'Reintentando'),
        ('moved_to_dlq', 'Movido a DLQ'),
        ('success', 'Éxito')
    ], string='Estado', default='retrying', required=True)

    @api.model
    def increment_retry(self, message_id, error_message, entity_type=None):
        """
        Incrementa el contador de reintentos para un mensaje.

        Args:
            message_id: ID del mensaje de PubSub
            error_message: Mensaje de error
            entity_type: Tipo de entidad (opcional)

        Returns:
            dict con keys:
                - retry_count: Número actual de reintentos
                - should_move_to_dlq: Si se debe mover a DLQ
                - retry_record: Registro de reintento
        """
        retry_record = self.search([('message_id', '=', message_id)], limit=1)

        if retry_record:
            # Incrementar contador existente
            new_count = retry_record.retry_count + 1
            retry_record.write({
                'retry_count': new_count,
                'last_retry_date': fields.Datetime.now(),
                'last_error': error_message,
                'entity_type': entity_type or retry_record.entity_type
            })
        else:
            # Primer intento fallido
            new_count = 1
            retry_record = self.create({
                'message_id': message_id,
                'retry_count': new_count,
                'last_error': error_message,
                'entity_type': entity_type,
                'state': 'retrying'
            })

        # Determinar si se debe mover a DLQ
        should_move_to_dlq = new_count > self.MAX_RETRIES

        _logger.info(
            f"Mensaje {message_id}: reintento {new_count}/{self.MAX_RETRIES}. "
            f"Mover a DLQ: {should_move_to_dlq}"
        )

        return {
            'retry_count': new_count,
            'should_move_to_dlq': should_move_to_dlq,
            'retry_record': retry_record
        }

    @api.model
    def mark_success(self, message_id):
        """
        Marca un mensaje como procesado exitosamente.

        Args:
            message_id: ID del mensaje de PubSub
        """
        retry_record = self.search([('message_id', '=', message_id)], limit=1)

        if retry_record:
            retry_record.write({
                'state': 'success',
                'last_retry_date': fields.Datetime.now()
            })
            _logger.debug(f"Mensaje {message_id} marcado como exitoso después de {retry_record.retry_count} reintentos")

    @api.model
    def mark_moved_to_dlq(self, message_id):
        """
        Marca un mensaje como movido a DLQ.

        Args:
            message_id: ID del mensaje de PubSub
        """
        retry_record = self.search([('message_id', '=', message_id)], limit=1)

        if retry_record:
            retry_record.write({
                'state': 'moved_to_dlq',
                'last_retry_date': fields.Datetime.now()
            })
            _logger.info(f"Mensaje {message_id} marcado como movido a DLQ")

    @api.model
    def get_retry_count(self, message_id):
        """
        Obtiene el contador de reintentos actual para un mensaje.

        Args:
            message_id: ID del mensaje de PubSub

        Returns:
            int: Número de reintentos (0 si no existe registro)
        """
        retry_record = self.search([('message_id', '=', message_id)], limit=1)
        return retry_record.retry_count if retry_record else 0

    @api.model
    def cleanup_old_records(self):
        """
        Limpia registros antiguos de reintentos exitosos.

        Se ejecuta mediante cron job para mantener la tabla ligera.
        Solo elimina registros en estado 'success' más antiguos que CLEANUP_DAYS.
        """
        cleanup_date = datetime.now() - timedelta(days=self.CLEANUP_DAYS)

        old_records = self.search([
            ('state', '=', 'success'),
            ('last_retry_date', '<', cleanup_date)
        ])

        count = len(old_records)
        if count > 0:
            old_records.unlink()
            _logger.info(f"Limpieza de tracking de reintentos: {count} registros eliminados")

        return count

    @api.model
    def get_retry_stats(self):
        """
        Obtiene estadísticas de reintentos para el dashboard.

        Returns:
            dict con estadísticas de reintentos
        """
        return {
            'total_retrying': self.search_count([('state', '=', 'retrying')]),
            'total_moved_to_dlq': self.search_count([('state', '=', 'moved_to_dlq')]),
            'total_success_with_retries': self.search_count([
                ('state', '=', 'success'),
                ('retry_count', '>', 0)
            ])
        }
