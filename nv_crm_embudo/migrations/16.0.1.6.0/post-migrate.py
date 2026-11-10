"""Bloques de reactivación: el embudo general no hace esperar 15 días a los leads de un
bloque y deja fuera a las personas con la baja del boletín de Nesto. Se puede repetir sin
daño: ver crm.lead._nv_preparar_embudo_bloques.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['crm.lead']._nv_preparar_embudo_bloques()
