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

    # Fechas de compras (issue #8). Las calcula Nesto sobre LinPedidoVta y son del cliente
    # (Nº_Cliente), así que llegan iguales en todos sus contactos. Solo entran: nunca se
    # devuelven a Nesto (ver 'reverse': False en entity_configs.py).
    fecha_primer_presupuesto = fields.Date(
        string="Fecha del primer presupuesto", readonly=True, copy=False, index=True,
        help="Primer presupuesto del cliente en Nesto (LinPedidoVta con Estado -3). "
             "La calcula y la mantiene Nesto; en Odoo es de solo lectura.")
    fecha_primer_pedido = fields.Date(
        string="Fecha del primer pedido", readonly=True, copy=False, index=True,
        help="Primer pedido real del cliente en Nesto (LinPedidoVta con Estado > -3). "
             "Sin fecha = el cliente todavía no ha comprado nunca.")
    fecha_ultimo_pedido = fields.Date(
        string="Fecha del último pedido", readonly=True, copy=False, index=True,
        help="Último pedido real del cliente en Nesto. La calcula y la mantiene Nesto.")

    # Nota: NO usamos vendedor_externo. El mapeo de vendedores se hace
    # exclusivamente por email (VendedorEmail). Cada sistema resuelve
    # el código de vendedor desde el email de forma independiente.

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