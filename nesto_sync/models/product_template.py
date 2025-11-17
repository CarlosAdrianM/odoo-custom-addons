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

    # Campo para cachear la URL de la imagen (para evitar descargas innecesarias)
    url_imagen_actual = fields.Char(
        string="URL Imagen Actual",
        help="URL de la imagen actualmente cargada. Se usa para detectar si cambió la imagen."
    )

    # Campo calculado para mostrar volumen en unidades legibles (ml o l)
    volume_display = fields.Char(
        string="Volumen",
        compute='_compute_volume_display',
        store=False,
        help="Volumen en mililitros (ml) o litros (l) para mejor legibilidad"
    )

    @api.depends('volume')
    def _compute_volume_display(self):
        """
        Calcula la visualización del volumen en unidades legibles

        Convierte de m³ a:
        - ml si < 1 litro (0.001 m³)
        - l si >= 1 litro

        Ejemplos:
        - 0.0001 m³ → "100 ml"
        - 0.002 m³ → "2 l"
        - 0.0025 m³ → "2.5 l"
        - 0 m³ → "" (vacío)
        """
        for product in self:
            if not product.volume or product.volume == 0:
                product.volume_display = ""
            else:
                # Convertir m³ a litros (1 m³ = 1000 l)
                volume_liters = product.volume * 1000

                if volume_liters < 1:
                    # Mostrar en mililitros si es menos de 1 litro
                    volume_ml = volume_liters * 1000
                    # Usar :g para eliminar ceros innecesarios (.00 → , .50 → .5)
                    if volume_ml == int(volume_ml):
                        product.volume_display = f"{int(volume_ml)} ml"
                    else:
                        product.volume_display = f"{volume_ml:g} ml"
                else:
                    # Mostrar en litros
                    if volume_liters == int(volume_liters):
                        product.volume_display = f"{int(volume_liters)} l"
                    else:
                        product.volume_display = f"{volume_liters:g} l"

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
