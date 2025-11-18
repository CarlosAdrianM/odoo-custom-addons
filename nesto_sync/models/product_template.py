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

    # Campo para almacenar el volumen en mililitros (evita problemas de redondeo)
    # Este campo se usa como fuente de verdad para volúmenes pequeños
    volume_ml = fields.Float(
        string="Volumen (ml)",
        digits=(16, 2),  # Precisión suficiente para almacenar decimales
        help="Volumen en mililitros. Se usa para productos con volúmenes pequeños que el campo 'volume' (m³) no puede representar con precisión"
    )

    # Campo calculado para mostrar volumen en unidades legibles (ml o l)
    volume_display = fields.Char(
        string="Volumen",
        compute='_compute_volume_display',
        store=False,
        help="Volumen en mililitros (ml) o litros (l) para mejor legibilidad"
    )

    @api.depends('volume', 'volume_ml')
    def _compute_volume_display(self):
        """
        Calcula la visualización del volumen en unidades legibles

        PRIORIDAD:
        1. Si volume_ml tiene valor, usarlo (más preciso para volúmenes pequeños)
        2. Si no, usar volume (m³)

        Ejemplos:
        - volume_ml = 50 → "50 ml"
        - volume_ml = 1500 → "1.5 l"
        - volume = 0.002 m³ → "2 l"
        - Ambos en 0 → "" (vacío)
        """
        for product in self:
            # PRIORIDAD 1: Usar volume_ml si está definido
            if product.volume_ml and product.volume_ml > 0:
                volume_ml = product.volume_ml

                if volume_ml < 1000:
                    # Mostrar en mililitros
                    if volume_ml == int(volume_ml):
                        product.volume_display = f"{int(volume_ml)} ml"
                    else:
                        product.volume_display = f"{volume_ml:g} ml"
                else:
                    # Convertir a litros y mostrar
                    volume_l = volume_ml / 1000
                    if volume_l == int(volume_l):
                        product.volume_display = f"{int(volume_l)} l"
                    else:
                        product.volume_display = f"{volume_l:g} l"

            # PRIORIDAD 2: Usar volume (m³) si está definido
            elif product.volume and product.volume > 0:
                # Convertir m³ a litros (1 m³ = 1000 l)
                volume_liters = product.volume * 1000

                if volume_liters < 1:
                    # Mostrar en mililitros si es menos de 1 litro
                    volume_ml = volume_liters * 1000
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

            else:
                # Sin volumen
                product.volume_display = ""

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
