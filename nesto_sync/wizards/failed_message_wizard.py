# -*- coding: utf-8 -*-
"""
Wizard para gestionar mensajes fallidos (marcar como resuelto o fallo permanente)
"""

from odoo import models, fields, api


class FailedMessageWizard(models.TransientModel):
    """Wizard para marcar mensajes como resueltos o con fallo permanente."""

    _name = 'nesto.sync.failed.message.wizard'
    _description = 'Wizard para gestionar mensajes fallidos'

    failed_message_id = fields.Many2one(
        'nesto.sync.failed.message',
        string='Mensaje',
        required=True
    )

    action = fields.Selection([
        ('resolved', 'Marcar como Resuelto'),
        ('permanently_failed', 'Marcar como Fallo Permanente')
    ], string='Acción', default='permanently_failed', required=True)

    resolution_notes = fields.Text(
        string='Notas',
        required=True,
        help='Explica por qué se marca de esta manera'
    )

    def action_confirm(self):
        """Confirma la acción y actualiza el mensaje."""
        self.ensure_one()

        if self.action == 'resolved':
            self.failed_message_id.write({
                'state': 'resolved',
                'resolved_date': fields.Datetime.now(),
                'resolved_by': self.env.user.id,
                'resolution_notes': self.resolution_notes
            })
        else:  # permanently_failed
            self.failed_message_id.write({
                'state': 'permanently_failed',
                'resolved_date': fields.Datetime.now(),
                'resolved_by': self.env.user.id,
                'resolution_notes': self.resolution_notes
            })

        return {'type': 'ir.actions.act_window_close'}
