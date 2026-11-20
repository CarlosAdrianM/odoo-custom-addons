from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HelpDeskMachine(models.Model):
    _name = 'helpdesk.machine'
    _description = 'Machines for HelpDesk'

    name = fields.Char(string="Name", required=True)
    serial_number = fields.Char(string="Serial Number", required=False)
    description = fields.Text(string="Description")
    purchase_date = fields.Date(string="Purchase Date")
    brand_id = fields.Many2one(
        "helpdesk.machine.brand",
        string="Marca",
        compute="_compute_brand_id",
        store=True,
        readonly=False,
        ondelete="set null",
        help="Se propone sola por el nombre del modelo; se puede cambiar a mano. "
        "Sin marca, el informe de reparación sale con el logo de la empresa.",
    )

    @api.depends("name")
    def _compute_brand_id(self):
        Marca = self.env["helpdesk.machine.brand"]
        for machine in self:
            machine.brand_id = Marca._marca_para(machine.name)

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
