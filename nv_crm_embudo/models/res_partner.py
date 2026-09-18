from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    nv_lead_revisado = fields.Boolean(
        string='Lead de origen revisado', default=False, copy=False, index=True,
        help='Marca que la tarea programada del embudo ya ha buscado el lead de origen de este '
             'cliente de Nesto. Evita repetir el trabajo y, mientras está a False, permite '
             'reintentarlo cuando las personas de contacto llegan en mensajes posteriores.',
    )

    def _nv_marcar_lead_revisado(self):
        """Marca los clientes como revisados sin publicar nada hacia Nesto.

        `nv_lead_revisado` no está en los field_mappings de nesto_sync, pero el mixin
        bidireccional publica el registro entero en cuanto detecta un cambio real en un
        partner con cliente_externo. skip_sync=True lo evita.
        """
        return self.sudo().with_context(skip_sync=True).write({'nv_lead_revisado': True})
