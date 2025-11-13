{
    'name': 'Nesto Sync',
    'version': '2.3.0',  # 2.3.0: Sincronización de Productos (fase minimalista)
    'summary': 'Sincronización bidireccional de tablas entre Nesto y Odoo via Google Pub/Sub',
    'description': '''
        Módulo de sincronización bidireccional entre Nesto y Odoo

        Versión 2.3.0 (2025-11-13):
        - Nueva entidad: Productos (tabla Productos de Nesto → product.template)
        - Campo producto_externo para mapear con referencia de Nesto
        - Campos básicos: Nombre, Precio, Tamaño (fase minimalista)
        - Sincronización bidireccional habilitada para productos
        - Fase 2 pendiente: UnidadMedida, Grupo, Subgrupo, Familia, Proveedor

        Versión 2.2.3 (2025-11-11):
        - Fix detección de cambios: guardar valores originales ANTES del write
        - _should_sync_record comparaba valores ya actualizados (siempre iguales)
        - Ahora guarda valores antes del write para comparación correcta
        - Detecta correctamente cambios en Odoo → Nesto

        Versión 2.2.2 (2025-11-11):
        - Fix bucle infinito: mapear PersonaContacto desde mensajes planos
        - Nesto envía mensajes con PersonaContacto en la raíz (no en array)
        - Ahora se mapea correctamente a persona_contacto_externa
        - Evita que se actualice el registro equivocado

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
    'depends': ['base', 'product'],
    'data': [
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3'
}
