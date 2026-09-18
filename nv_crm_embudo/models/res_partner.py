from odoo import fields, models

# Fechas de nesto_sync (#8) que mueven el embudo. fecha_ultimo_pedido no mueve nada:
# es para segmentar clientes que llevan tiempo sin comprar.
CAMPOS_FECHAS_EMBUDO = ('fecha_primer_presupuesto', 'fecha_primer_pedido')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    nv_lead_revisado = fields.Boolean(
        string='Lead de origen revisado', default=False, copy=False, index=True,
        help='Marca que la tarea programada del embudo ya ha buscado el lead de origen de este '
             'cliente de Nesto. Evita repetir el trabajo y, mientras está a False, permite '
             'reintentarlo cuando las personas de contacto llegan en mensajes posteriores.',
    )

    def write(self, vals):
        """Cuando Nesto cambia las fechas de compras, el embudo avanza solo (#9, paso 2).

        La lógica del CRM vive aquí y no en nesto_sync, que solo sincroniza. Nesto publica un
        mensaje por contacto, así que la misma fecha llega varias veces: se agrupa por cliente
        principal (commercial_partner_id) para no repetir el trabajo.
        """
        campos = [campo for campo in CAMPOS_FECHAS_EMBUDO if campo in vals]
        antes = {p.id: tuple(p[campo] for campo in campos) for p in self} if campos else {}

        resultado = super().write(vals)

        if campos:
            cambiados = self.filtered(
                lambda p: tuple(p[campo] for campo in campos) != antes[p.id])
            clientes = cambiados.commercial_partner_id
            if clientes:
                self.env['crm.lead'].sudo()._nv_avanzar_por_fechas(clientes)
        return resultado

    def _nv_marcar_lead_revisado(self):
        """Marca los clientes como revisados sin publicar nada hacia Nesto.

        `nv_lead_revisado` no está en los field_mappings de nesto_sync, pero el mixin
        bidireccional publica el registro entero en cuanto detecta un cambio real en un
        partner con cliente_externo. skip_sync=True lo evita.
        """
        return self.sudo().with_context(skip_sync=True).write({'nv_lead_revisado': True})
