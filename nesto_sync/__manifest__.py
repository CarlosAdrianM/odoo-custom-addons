{
    'name': 'Nesto Sync',
    'version': '2.7.0',  # 2.7.0: Sistema DLQ para evitar mensajes infinitos
    'summary': 'Sincronización bidireccional de tablas entre Nesto y Odoo via Google Pub/Sub',
    'description': '''
        Módulo de sincronización bidireccional entre Nesto y Odoo

        Versión 2.7.0 (2025-11-19):
        - NUEVA FUNCIONALIDAD: Dead Letter Queue (DLQ) para mensajes que fallan repetidamente
        - Sistema de tracking de reintentos con límite configurable (3 reintentos por defecto)
        - Modelo nesto.sync.failed.message: Almacena mensajes que no se pudieron procesar
        - Modelo nesto.sync.message.retry: Tracking temporal de reintentos por messageId
        - Controller mejorado: Extrae messageId de PubSub y gestiona reintentos automáticamente
        - Nuevas vistas Odoo: Gestión visual de mensajes fallidos con acciones de reprocesamiento
        - Botones de acción: Reprocesar, Marcar como Resuelto, Marcar como Fallo Permanente
        - Cron job automático: Limpieza de registros de reintentos antiguos (7 días)
        - Menú "Dead Letter Queue" en Odoo con dos vistas: Mensajes Fallidos y Tracking de Reintentos
        - Evita bucles infinitos: Después de N intentos, mensaje se mueve a DLQ y se hace ACK
        - Logs enriquecidos: Cada mensaje incluye [messageId] para mejor trazabilidad
        - Información completa del error: Mensaje, stack trace, datos crudos, número de reintentos
        - Permisos de seguridad: Admins pueden gestionar, usuarios pueden ver
        - Arquitectura autocontenida: Toda la funcionalidad dentro del módulo nesto_sync

        Versión 2.6.0 (2025-11-18):
        - FIX CRÍTICO: Redondeo de volumen - nuevo campo volume_ml para precisión exacta
        - Campo volume_ml (Float) almacena volumen en mililitros sin pérdida de precisión
        - Campo volume (m³) se mantiene por compatibilidad pero puede sufrir redondeo
        - volume_display ahora prioriza volume_ml sobre volume para cálculos
        - Productos: Transformers inversos completos para sincronización Odoo → Nesto
        - Reverse transformer: ficticio_to_detailed_type (detailed_type → Ficticio)
        - Reverse transformer: grupo (grupo_id → nombre Grupo)
        - Reverse transformer: subgrupo (subgrupo_id → nombre Subgrupo)
        - Reverse transformer: familia (familia_id → nombre Familia)
        - Reverse transformer: url_to_image (url_imagen_actual → UrlFoto)
        - Reverse transformer: unidad_medida_y_tamanno (volume_ml/weight/length → Tamaño + UnidadMedida)
        - Soporte multi-campo en transformers inversos (devolver dict con múltiples campos)

        Versión 2.5.0 (2025-11-17):
        - Productos: UnidadMedida + Tamaño → weight/volume/product_length (según tipo)
        - Productos: Conversiones automáticas a unidades base (kg, m³, m)
        - Productos: Mapeo UnidadMedida → uom_id (búsqueda en product.uom)
        - Productos: Soporte de dimensiones (product_length) via módulo OCA product_dimension
        - Productos: UrlImagen optimizada (solo descarga si cambió la URL)
        - Productos: Campo url_imagen_actual para cachear URL y evitar descargas repetidas
        - Productos: Vistas mejoradas con campos Grupo, Subgrupo, Familia visibles
        - Transformer: unidad_medida_y_tamanno (detecta tipo: peso/volumen/longitud)
        - Dependencia: Módulo product_dimension (OCA) para campos de dimensiones

        Versión 2.4.1 (2025-11-14):
        - FIX: Jerarquía correcta Grupo > Subgrupo (dependiente)
        - Grupos ahora son categorías raíz (sin padre)
        - Subgrupos se crean bajo su Grupo correspondiente
        - Ejemplo: ACC > Desechables, Cosméticos > Aceites

        Versión 2.4.0 (2025-11-14):
        - Productos: Mapeo de Estado → active (≥0 activo, <0 inactivo)
        - Productos: Campos de categorización (Grupo, Subgrupo, Familia → product.category)
        - Productos: Descarga automática de imágenes desde UrlImagen → image_1920
        - Transformers: grupo, subgrupo, familia (buscar/crear categorías automáticamente)
        - Transformer: url_to_image (descarga, validación PIL, conversión base64)
        - OdooPublisher: Campo Usuario con formato ODOO\\login
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
    'depends': ['base', 'product', 'mail', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/failed_message_views.xml',
        'wizards/failed_message_wizard_views.xml',
        'data/cron_jobs.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3'
}
