"""Los leads con rebote dejan de recibir los correos 02 en adelante del embudo general.
Se puede repetir sin daño: ver crm.lead._nv_excluir_rebotados_del_embudo.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['crm.lead']._nv_excluir_rebotados_del_embudo()
