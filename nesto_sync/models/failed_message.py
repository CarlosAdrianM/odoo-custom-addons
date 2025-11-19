# -*- coding: utf-8 -*-
"""
Dead Letter Queue (DLQ) para mensajes que fallan repetidamente.

Este modelo almacena mensajes de PubSub que no pudieron procesarse después de
varios reintentos, permitiendo su revisión y reprocesamiento manual.
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class NestoSyncFailedMessage(models.Model):
    """Almacena mensajes de PubSub que fallaron al procesarse."""

    _name = 'nesto.sync.failed.message'
    _description = 'Mensajes fallidos de sincronización Nesto'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identificación del mensaje
    message_id = fields.Char(
        string='Message ID',
        help='ID único del mensaje de Google PubSub',
        index=True,
        readonly=True
    )

    # Datos del mensaje
    raw_data = fields.Text(
        string='Datos crudos',
        help='Mensaje original completo de PubSub en formato JSON',
        required=True,
        readonly=True
    )

    entity_type = fields.Char(
        string='Tipo de entidad',
        help='Tipo de entidad que se intentó procesar (contact, product, etc.)',
        index=True,
        readonly=True
    )

    # Información del error
    error_message = fields.Text(
        string='Mensaje de error',
        help='Mensaje de error legible para humanos',
        required=True,
        readonly=True
    )

    error_traceback = fields.Text(
        string='Stack trace',
        help='Stack trace completo del error para debugging',
        readonly=True
    )

    retry_count = fields.Integer(
        string='Número de reintentos',
        help='Cuántas veces se intentó procesar antes de mover a DLQ',
        default=0,
        readonly=True
    )

    # Estado y gestión
    state = fields.Selection([
        ('failed', 'Fallido'),
        ('resolved', 'Resuelto'),
        ('reprocessing', 'Reprocesando'),
        ('permanently_failed', 'Fallo permanente')
    ], string='Estado', default='failed', required=True, index=True)

    resolution_notes = fields.Text(
        string='Notas de resolución',
        help='Notas sobre cómo se resolvió el problema o por qué falló permanentemente'
    )

    resolved_date = fields.Datetime(
        string='Fecha de resolución',
        readonly=True
    )

    resolved_by = fields.Many2one(
        'res.users',
        string='Resuelto por',
        readonly=True
    )

    # Metadatos
    first_attempt_date = fields.Datetime(
        string='Primera vez que falló',
        readonly=True
    )

    last_attempt_date = fields.Datetime(
        string='Último intento',
        readonly=True
    )

    # Relación con registro creado (si existe)
    related_record_model = fields.Char(
        string='Modelo relacionado',
        help='Modelo Odoo relacionado (res.partner, product.template, etc.)'
    )

    related_record_id = fields.Integer(
        string='ID de registro relacionado',
        help='ID del registro creado/actualizado (si existe)'
    )

    def action_reprocess(self):
        """Reintenta procesar el mensaje manualmente."""
        self.ensure_one()

        if self.state not in ['failed', 'permanently_failed']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': 'Solo se pueden reprocesar mensajes en estado "Fallido" o "Fallo permanente"',
                    'sticky': False,
                }
            }

        # Por ahora, mostrar mensaje indicando que debe corregirse manualmente
        # TODO: Implementar reprocesamiento automático en versión futura
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'title': 'Reprocesamiento Manual',
                'message': 'Por favor, corrija el problema en Odoo o Nesto y use "Marcar como Resuelto". El reprocesamiento automático estará disponible en una versión futura.',
                'sticky': True,
            }
        }

    def action_mark_permanently_failed(self):
        """Marca el mensaje como fallo permanente (no se puede resolver)."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Marcar como fallo permanente',
            'res_model': 'nesto.sync.failed.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_failed_message_id': self.id,
                'default_resolution_notes': self.resolution_notes or ''
            }
        }

    def action_mark_resolved(self):
        """Marca el mensaje como resuelto (se arregló manualmente en Odoo)."""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Marcar como resuelto',
            'res_model': 'nesto.sync.failed.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_failed_message_id': self.id,
                'default_resolution_notes': self.resolution_notes or '',
                'default_action': 'resolved'
            }
        }
