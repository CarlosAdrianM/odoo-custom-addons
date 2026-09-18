{
    'name': 'NV CRM Embudo',
    'version': '16.0.1.1.0',
    'summary': 'Personalizaciones del CRM de Nueva Visión para los embudos: enlace de baja, leads vivos por vendedora y enlace automatico con los clientes de Nesto',
    'author': 'Nueva Visión',
    'depends': ['crm', 'mail', 'nesto_sync'],
    'data': [
        'data/crm_stage_data.xml',
        'data/ir_cron_data.xml',
        'views/leads_vivos_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
