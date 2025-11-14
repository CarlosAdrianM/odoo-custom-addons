from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['bidirectional.sync.mixin', 'product.template']

    producto_externo = fields.Char(
        string="Producto Externo",
        index=True,
        help="Referencia externa del producto en Nesto"
    )

    # Campos de categorización adicionales desde Nesto
    grupo_id = fields.Many2one(
        'product.category',
        string="Grupo",
        help="Grupo principal del producto (Cosméticos, Aparatos, Accesorios)",
        ondelete='restrict'
    )

    subgrupo_id = fields.Many2one(
        'product.category',
        string="Subgrupo",
        help="Subgrupo del producto dentro del grupo (Cremas, IPL, Depilación, etc.)",
        ondelete='restrict'
    )

    familia_id = fields.Many2one(
        'product.category',
        string="Familia/Marca",
        help="Marca o familia del producto (Eva Visnú, L'Oréal, etc.)",
        ondelete='restrict'
    )

    @api.constrains('producto_externo')
    def _check_unique_producto_externo(self):
        """Validar que producto_externo sea único si está definido"""
        for record in self:
            if record.producto_externo:
                duplicates = self.search([
                    ('id', '!=', record.id),
                    ('producto_externo', '=', record.producto_externo)
                ])
                if duplicates:
                    raise ValidationError(
                        f"El Producto Externo '{record.producto_externo}' ya existe en el sistema."
                    )
