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

        # Marcar como reprocesando
        self.write({'state': 'reprocessing'})
        self.env.cr.commit()

        try:
            # Importar aquí para evitar dependencias circulares
            from odoo.addons.nesto_sync.controllers.controllers import NestoSyncController

            controller = NestoSyncController()

            # Reprocesar el mensaje
            # Convertir raw_data de nuevo a bytes para simular request
            import json
            raw_bytes = self.raw_data.encode('utf-8')

            # Procesar usando la lógica del controller
            # Nota: Esto es un procesamiento manual, no viene de PubSub
            response = controller._process_message_internal(
                raw_bytes,
                self.env,
                force_reprocess=True  # Flag para indicar que es reprocesamiento manual
            )

            if response.get('status') == 200:
                # Éxito
                self.write({
                    'state': 'resolved',
                    'resolved_date': fields.Datetime.now(),
                    'resolved_by': self.env.user.id,
                    'resolution_notes': 'Reprocesado manualmente con éxito'
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'message': 'Mensaje reprocesado con éxito',
                        'sticky': False,
                    }
                }
            else:
                # Falló de nuevo
                error_msg = response.get('message', 'Error desconocido')
                self.write({
                    'state': 'failed',
                    'error_message': f"{self.error_message}\n\n[Reintento manual falló: {error_msg}]",
                    'last_attempt_date': fields.Datetime.now()
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'danger',
                        'message': f'Error al reprocesar: {error_msg}',
                        'sticky': True,
                    }
                }

        except Exception as e:
            _logger.error(f"Error al reprocesar mensaje {self.message_id}: {str(e)}", exc_info=True)

            self.write({
                'state': 'failed',
                'error_message': f"{self.error_message}\n\n[Reintento manual falló: {str(e)}]",
                'last_attempt_date': fields.Datetime.now()
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': f'Error al reprocesar: {str(e)}',
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
