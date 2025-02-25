from odoo import models, fields

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    machine_id = fields.Many2one(
        'helpdesk.machine',  # Nombre del modelo de máquina
        string='Machine',    # Etiqueta del campo
        help='Select the machine associated with this ticket.'
    )
    serial_number = fields.Char(
        related='machine_id.serial_number',  # Campo relacionado
        string='Serial Number',              # Etiqueta del campo
        readonly=True                        # Solo lectura
    )
