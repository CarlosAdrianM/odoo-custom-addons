{
    'name': 'HelpDesk Machine',
    'version': '1.1',
    'summary': 'Máquinas en los tickets del servicio técnico e informe de reparación para el cliente.',
    'description': 'Máquinas y números de serie en los tickets de HelpDesk, '
                   'e informe de reparación en PDF redactado con IA y aprobado por una persona.',
    'category': 'Helpdesk',
    'author': 'Carlos Adrián Martínez',
    'depends': ['helpdesk_mgmt', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/informe_data.xml',
        'views/machine_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/informe_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
