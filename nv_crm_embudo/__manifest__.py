{
    'name': 'NV CRM Embudo',
    'version': '16.0.1.3.0',
    'summary': 'Personalizaciones del CRM de Nueva Vision para los embudos: enlace de baja, leads vivos por vendedora y avance automatico de los leads con los clientes y las compras de Nesto',
    'author': 'Nueva Visión',
    'depends': ['crm', 'mail', 'nesto_sync'],
    'data': [
        'data/crm_stage_data.xml',
        'data/ir_cron_data.xml',
        'views/leads_vivos_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'license': 'LGPL-3',
}
