{
    'name': 'NV CRM Embudo - envíos fiables con automation_oca',
    'version': '16.0.1.0.0',
    'summary': 'Puente entre nv_crm_embudo y automation_oca: no repite un correo del embudo que ya salió, '
               'reintenta los fallos pasajeros del servidor de correo y no sigue la secuencia con quien '
               'nunca recibió el correo anterior',
    'author': 'Nueva Visión',
    'depends': ['nv_crm_embudo', 'automation_oca'],
    'data': ['data/ir_cron_data.xml'],
    'auto_install': True,
    'installable': True,
    'license': 'LGPL-3',
}
