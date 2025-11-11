{
    'name': 'Nesto Sync',
    'version': '2.2.1',  # 2.2.1: Fix bucle infinito en comparación case-sensitive de nombres
    'summary': 'Sincronización bidireccional de tablas entre Nesto y Odoo via Google Pub/Sub',
    'description': '''
        Módulo de sincronización bidireccional entre Nesto y Odoo

        Versión 2.2.1 (2025-11-11):
        - Fix bucle infinito: comparación case-insensitive para campo 'name'
        - Nesto cambia internamente mayúsculas/minúsculas provocando bucles
        - Ahora 'BEATRIZ' y 'beatriz' se consideran iguales

        Versión 2.2.0 (2025-11-11):
        - Endpoint /nesto_sync/logs para consultar logs en memoria
        - Logs detallados con IDs, nombres y contexto en write()
        - Fix anti-bucle: solo publicar registros que realmente cambiaron
        - _should_sync_record() compara valores antes/después

        Versión 2.1.0 (2025-11-11):
        - Fix doble serialización JSON (Odoo → Nesto)
        - Estructura ExternalSyncMessageDTO correcta
        - Método _wrap_in_sync_message() para envolver mensajes

        Versión 2.0.0 (2025-11-10):
        - Sincronización bidireccional (Odoo → Nesto)
        - BidirectionalSyncMixin para interceptar cambios
        - OdooPublisher con serialización de Many2one
        - Anti-bucle sin flags de origen

        Versión 1.0.0:
        - Sincronización unidireccional (Nesto → Odoo)
        - Arquitectura extensible con entity_configs
        - Soporte para jerarquías (Clientes + PersonasContacto)
    ''',
    'author': 'Carlos Adrián Martínez',
    'depends': ['base'],
    'data': [
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3'
}
