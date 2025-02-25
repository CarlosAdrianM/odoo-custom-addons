from odoo import models, fields, api

class HelpDeskMachine(models.Model):
    _name = 'helpdesk.machine'
    _description = 'Machines for HelpDesk'

    name = fields.Char(string="Name", required=True)
    serial_number = fields.Char(string="Serial Number", required=False)

    description = fields.Text(string="Description")

    def name_get(self):
        result = []
        for machine in self:
            display_name = f"{machine.name} ({machine.serial_number})"
            result.append((machine.id, display_name))
        return result

    @api.constrains('serial_number')
    def _check_unique_serial_number(self):
        for machine in self:
            if machine.serial_number:
                existing_machine = self.search([
                    ('serial_number', '=', machine.serial_number),
                    ('id', '!=', machine.id)
                ], limit=1)
                if existing_machine:
                    raise ValidationError("The serial number must be unique!")