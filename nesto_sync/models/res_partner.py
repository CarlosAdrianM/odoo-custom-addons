from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['bidirectional.sync.mixin', 'res.partner']

    cliente_externo = fields.Char(string="Cliente Externo", index=True, search="_search_cliente_externo")
    contacto_externo = fields.Char(string="Contacto Externo", index=True)
    persona_contacto_externa = fields.Char(string="Persona de Contacto Externa", index=True)

    def write(self, vals):
        """Override para debug - verificar que se llama"""
        _logger.info(f"⭐ ResPartner.write() llamado con vals: {vals}")
        return super(ResPartner, self).write(vals)

    @api.constrains('cliente_externo', 'contacto_externo', 'persona_contacto_externa')
    def _check_unique_combinations(self):
        for record in self:
            # Si persona_contacto_externa es None, validar unicidad solo de cliente_externo y contacto_externo
            if not record.persona_contacto_externa:
                duplicates = self.search([
                    ('id', '!=', record.id),
                    ('cliente_externo', '=', record.cliente_externo),
                    ('contacto_externo', '=', record.contacto_externo),
                    ('persona_contacto_externa', '=', False)
                ])
                if duplicates:
                    raise ValidationError(
                        "La combinación de Cliente Externo y Contacto Externo debe ser única si no se especifica una Persona de Contacto Externa."
                    )
            # Si persona_contacto_externa no es None, validar unicidad de cliente_externo, contacto_externo y persona_contacto_externa
            else:
                duplicates = self.search([
                    ('id', '!=', record.id),
                    ('cliente_externo', '=', record.cliente_externo),
                    ('contacto_externo', '=', record.contacto_externo),
                    ('persona_contacto_externa', '=', record.persona_contacto_externa)
                ])
                if duplicates:
                    raise ValidationError(
                        "La combinación de Cliente Externo, Contacto Externo y Persona de Contacto Externa debe ser única."
                    )

    @api.model
    def _search_cliente_externo(self, operator, value):
        if value and value.isdigit():
            return [('cliente_externo', '=', value)]
        return [('cliente_externo', operator, value)]

    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        # Modificar args si contiene una búsqueda por nombre/display_name
        new_args = []
        for arg in args:
            if isinstance(arg, (list, tuple)) and len(arg) == 3:
                field, operator, value = arg
                if field in ['name', 'display_name'] and value and str(value).isdigit():
                    new_args.extend(['|',
                        ('cliente_externo', '=', value),
                        (field, operator, value)
                    ])
                else:
                    new_args.append(arg)
            else:
                new_args.append(arg)
        
        return super()._search(new_args, offset=offset, limit=limit, order=order, 
                             count=count, access_rights_uid=access_rights_uid)