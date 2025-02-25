{
    'name': 'HelpDesk Machine',
    'version': '1.0',
    'summary': 'Manage machines and associate them with HelpDesk tickets.',
    'description': 'A module to track machines and their serial numbers in HelpDesk tickets.',
    'category': 'Helpdesk',
    'author': 'Carlos Adrián Martínez',
    'depends': ['helpdesk_mgmt'],
    'data': [
        'security/ir.model.access.csv',
        'views/machine_views.xml',
        'views/helpdesk_ticket_views.xml',  
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
