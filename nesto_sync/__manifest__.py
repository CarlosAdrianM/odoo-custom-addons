{
    'name': 'Nesto Sync',
    'version': '2.4.0',  # 2.4.0: Enriquecimiento de sincronización de productos
    'summary': 'Sincronización bidireccional de tablas entre Nesto y Odoo via Google Pub/Sub',
    'description': '''
        Módulo de sincronización bidireccional entre Nesto y Odoo

        Versión 2.4.0 (2025-11-14):
        - Productos: Mapeo de Estado → active (≥0 activo, <0 inactivo)
        - Productos: Campos de categorización (Grupo, Subgrupo, Familia → product.category)
        - Productos: Descarga automática de imágenes desde UrlImagen → image_1920
        - Transformers: grupo, subgrupo, familia (buscar/crear categorías automáticamente)
        - Transformer: url_to_image (descarga, validación PIL, conversión base64)
        - OdooPublisher: Campo Usuario con formato ODOO\login
        - Modelo: Nuevos campos grupo_id, subgrupo_id, familia_id en product.template

        Versión 2.3.4 (2025-11-13):
        - CRÍTICO: Añadido _extract_entity_data() para manejar diferentes estructuras
        - Clientes: {"Cliente": {...}, "Origen": "...", "Usuario": "..."} (con wrapper)
        - Productos: {"Producto": "123", "Nombre": "...", ...} (plano)
        - Detecta automáticamente si hay wrapper y extrae datos correctamente

        Versión 2.3.3 (2025-11-13):
        - CRÍTICO: Fix detección de entity_type - ahora usa campo "Tabla" como fuente de verdad
        - Antes detectaba por presencia de campos (Cliente, Producto) causando errores
        - Mapeo: Clientes→cliente, Productos→producto, Proveedores→proveedor

        Versión 2.3.2 (2025-11-13):
        - Refactor: _should_sync_record() usa id_fields de entity_configs
        - Eliminado código hardcoded de campos específicos (cliente_externo, etc.)
        - Validación genérica que funciona para cualquier entidad
        - Logs mejorados con info específica de cada entidad

        Versión 2.3.1 (2025-11-13):
        - Mapeo enriquecido de productos: Producto→default_code, PrecioProfesional, CodigoBarras
        - Transformer ficticio_to_detailed_type (Ficticio + Grupo → detailed_type)
        - Tamanno (en lugar de Tamano)
        - Lógica: Ficticio=0→product, Ficticio=1+Grupo=CUR→service, otros→consu

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
