{
    'name': 'Nesto Sync',
    'version': '2.9.2',  # 2.9.2: Los clientes nuevos vuelven a entrar con país
    'summary': 'Sincronización bidireccional de tablas entre Nesto y Odoo via Google Pub/Sub',
    'description': '''
        Módulo de sincronización bidireccional entre Nesto y Odoo

        Versión 2.9.2 (2026-09-23):
        - Los clientes nuevos vuelven a entrar con país (issue #30). Los mapeos
          sintéticos (clave que empieza por '_') ya no pasan por la comprobación
          de presencia que trajo el arreglo de mensajes parciales: no vienen
          nunca en el mensaje, así que '_country' salía siempre antes de escribir
          y country_id no se ponía jamás. 2.541 clientes creados sin país desde
          febrero, con provincia española puesta. Los que ya están se arreglan
          solos cuando Nesto los republique, o con el write puntual del PR

        Versión 2.9.1 (2026-09-23):
        - Un cambio de vendedor que llega de Nesto ya no manda el correo «Ha
          sido asignado/a» (issue #36): el contexto de escritura lleva
          mail_auto_subscribe_no_notify. La carga masiva del 23/09 mandó 412
          en 23 minutos. El vendedor sigue quedando como seguidor y el cambio
          sigue en el historial; lo asignado a mano en Odoo sigue avisando

        Versión 2.9.0 (2026-09-22):
        - Un dato malo de Nesto ya no tira el mensaje ENTERO. Cuatro causas que
          entre las cuatro tenían 431 entidades atascadas en la DLQ (issue #23):
          - NIF que no pasa base_vat (177, issue #18): se escribe con
            no_vat_validation. Nesto es la fuente de verdad del NIF, y Odoo
            perdía el cliente entero por rechazarlo. Lo que se edite a mano en
            Odoo sigue validándose
          - Nombre vacío "" (91, issue #19): un campo requerido que llega vacío
            se trata como si no viniera, y Odoo conserva lo que tenga. El
            default pasa a aplicarse SOLO al crear: aplicarlo al actualizar
            renombraba productos buenos a '<Nombre producto no proporcionado>'.
            Las personas de contacto sin nombre se resuelven con su correo o su
            cargo, y si no hay ninguno se deja fuera esa persona y el resto del
            mensaje sigue
          - Cliente principal archivado (55, issue #20): la búsqueda del padre
            va con active_test=False. Antes, cada dirección o persona de
            contacto de ese cliente se iba a la DLQ, y para siempre, porque el
            archivado no cambia solo. El hijo se cuelga del archivado sin
            desarchivarlo
          - Código de barras repetido o basura (108 productos y 26 kits, issue
            #21): "0" y "1" se traducen a «sin código», que es lo que significan
            en Nesto; un EAN que ya tiene otro producto deja intacto el que Odoo
            tuviera, y el resto del mensaje entra
        - VendedorEmail nulo ya no borra el vendedor del cliente (issue #25).
          Se adopta la convención de NestoAPI: ausente y null son «no
          modificar», y solo '' quita el vendedor. Como NestoAPI serializa
          incluyendo los nulos, cualquier vendedor sin Mail dejaba al cliente
          sin vendedor, en silencio, en cada republicación. Y quitar vendedor no
          avisa a nadie: ahora queda warning en el log con el vendedor que se
          pierde
        - CI: los tests de Odoo se pasan en cada PR y salta la alarma si un
          módulo ejecuta menos tests de los esperados o aparece un fallo nuevo
          (issue #22)

        Versión 2.8.2 (2026-09-22):
        - La BOM de los kits vuelve a sincronizarse (Issue #12). Tres fallos que
          llevaban en producción desde 2.8.0:
          1) Si el mensaje solo cambiaba ProductosKit, GenericService lo daba por
             «sin cambios» (el kit no es un campo del modelo) y la BOM no se
             tocaba: ni se actualizaba, ni se borraba cuando Nesto la vaciaba
          2) Un ProductosKit serializado como JSON se recorría carácter a carácter
             y la BOM se creaba VACÍA, sin avisar
          3) Un ProductosKit con identificadores en texto (['COMP001', ...]) se
             descartaba entero al intentar leer cada item como JSON
          ProductosKit se normaliza ahora una sola vez, en _normalize_kit_items
        - DLQ: last_attempt_date recibía la cadena 'UTC' al reintentar un mensaje
          que ya estaba en la DLQ, sobre un campo Datetime
        - Personas de contacto: el teléfono es 'Telefonos', en plural, confirmado
          por NestoAPI el 22/09/2026. En la raíz del mensaje el cliente lleva
          'Telefono', en singular: son dos claves distintas, no una errata.
          El mensaje del test end-to-end usaba el singular y por eso fallaba
        - Tests: los 13 en rojo de #12 en verde, y se ejecutan los de
          test_dlq_system, que no estaban importados y no corrían nunca

        Versión 2.8.1 (2026-08-27):
        - GUARDA CRÍTICA: CantidadMontable de Stocks[] NUNCA llega a los quants (Issue #6)
        - CantidadMontable es un derivado VIRTUAL (kits montables desde componentes),
          no stock físico: sumarlo duplicaría el inventario de los componentes
        - Nuevo módulo core/stock_guard.py con ALLOWLIST de campos de Stocks[]
          (contrato confirmado con NestoAPI el 27/08/2026) y dos capas:
          1) assert_stock_mapping_is_safe: falla al construir el processor si alguna
             entidad mapea un campo virtual o un campo de Stocks[] fuera de la
             allowlist, tanto entrante como inverso
          2) sanitize_message: deja en Stocks[] solo los campos permitidos antes de
             mapear nada, sin mutar el original (logs/DLQ intactos)
        - Campo documentado para quants físicos: Stock (por almacén)
        - Documentado el centinela FechaEstimadaRecepcion = 9999-12-31 (sin compras
          pendientes): no es una fecha real, no usar en cálculos de plazos
        - Un campo nuevo no previsto se descarta y se avisa por log (fail-safe)
        - Tests: 23 tests de la guarda (allowlist, config, saneado y regresión con
          mensaje real de kit con montables > 0)

        Versión 2.8.0 (2025-11-20):
        - NUEVA FUNCIONALIDAD: Sincronización bidireccional de BOMs (Bills of Materials)
        - ProductosKit de Nesto → mrp.bom de Odoo (creación/actualización/eliminación automática)
        - BOMs de Odoo → ProductosKit en mensajes publicados a Nesto
        - Validación estricta: Componentes faltantes → DLQ (evita sincronizaciones incompletas)
        - Detección de ciclos infinitos con DFS (máx. 10 niveles de profundidad)
        - BOM tipo 'normal' (no phantom) para gestión correcta de stock y facturación
        - Soporte múltiples formatos ProductosKit: objetos, arrays de IDs, JSON strings
        - Productos MTP (Materias Primas): sale_ok=False automático (no vendibles, solo para BOMs)
        - Transformer GrupoTransformer: Mapea Grupo='MTP' → sale_ok=False
        - Sin conversión inversa sale_ok → Grupo (relación unidireccional)
        - Manejo de permisos: sudo() en búsquedas/creación de BOMs para webhook
        - Post-processor SyncProductBom: Ejecuta después de crear/actualizar producto
        - Optimización: Compara BOM existente vs nueva para evitar updates innecesarios
        - Tests unitarios: 11 tests para validaciones, formatos, y casos edge
        - Tests integración: 8 tests end-to-end para flujos completos

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
