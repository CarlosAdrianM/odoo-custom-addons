"""Embudo automático: las tareas de automation_oca corren cada 10 minutos, para que el
correo 01 de un bloque salga poco después de la hora de envío elegida.
Se puede repetir sin daño: ver crm.lead._nv_acelerar_tareas_del_embudo.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['crm.lead']._nv_acelerar_tareas_del_embudo()
