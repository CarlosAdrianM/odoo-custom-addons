"""Leads de Meta (issue #43): exclusión en el embudo general y secuencia de Harmonia.

Saca del «Embudo de conversión» a los clientes que no aceptan comunicaciones y a los de
la campaña META-HARMONIA-0926, y crea la secuencia de Harmonia en borrador. Se puede
repetir sin daño: ver crm.lead._nv_preparar_embudos_origen.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['crm.lead']._nv_preparar_embudos_origen()
