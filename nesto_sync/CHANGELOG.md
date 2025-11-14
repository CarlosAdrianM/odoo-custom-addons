# Changelog - Nesto Sync

Todos los cambios notables en este proyecto están documentados en este archivo.

## [2.4.1] - 2025-11-14 🔧 FIX CRÍTICO

### 🐛 Fixed - Jerarquía de Categorías
- **Grupo > Subgrupo ahora es jerárquico (dependiente)**
  - Antes: Grupos y Subgrupos eran independientes
  - Problema: "Desechables" se creaba bajo "Subgrupos" genérico
  - Ahora: Subgrupo se crea bajo su Grupo correspondiente
  - Ejemplos:
    - ✅ ACC > Desechables
    - ✅ Cosméticos > Aceites
    - ✅ Aparatos > IPL

### 🔧 Technical Changes
- `GrupoTransformer`: `parent_category_name = None` (categorías raíz)
- `SubgrupoTransformer`: Usa `nesto_data['Grupo']` como nombre de padre
- `ProductCategoryTransformer`: Búsqueda correcta para categorías raíz con `parent_id = False`
- `GenericProcessor`: Añadido `context['nesto_data']` para acceso desde transformers

### 🧪 Testing
- ✅ Cosméticos (raíz) > Aceites (hijo)
- ✅ ACC (raíz) > Desechables (hijo)
- ✅ Familias/Marcas (raíz) > Eva Visnú (hijo)

---

## [2.4.0] - 2025-11-14 🆕 LISTO PARA PRODUCCIÓN

### ✨ Added - Enriquecimiento de Productos
- **Mapeo de Estado a active**
  - `Estado >= 0` → `active = true` (producto activo)
  - `Estado < 0` → `active = false` (producto inactivo)
  - Usa transformer existente `estado_to_active`

- **Campos de categorización**
  - `Grupo` → `grupo_id` (Many2one a product.category)
  - `Subgrupo` → `subgrupo_id` (Many2one a product.category)
  - `Familia` → `familia_id` (Many2one a product.category)
  - Creación automática de categorías bajo padres específicos:
    - "Grupos" → Cosméticos, Aparatos, Accesorios
    - "Subgrupos" → Cremas Faciales, IPL, Depilación, etc.
    - "Familias/Marcas" → Eva Visnú, L'Oréal, etc.

- **Descarga automática de imágenes**
  - `UrlImagen` → `image_1920` (campo binario)
  - Descarga desde URL con timeout 10s
  - Validación con Pillow (PIL)
  - Conversión a base64
  - Manejo robusto de errores (timeout, 404, formato inválido)
  - Genera automáticamente 5 resoluciones

### 🔧 New Transformers
- `grupo` - Busca/crea categoría de Grupo bajo "Grupos"
- `subgrupo` - Busca/crea categoría de Subgrupo bajo "Subgrupos"
- `familia` - Busca/crea categoría de Familia/Marca bajo "Familias/Marcas"
- `url_to_image` - Descarga y procesa imágenes desde URL
- `product_category` - Transformer genérico para categorías (base de los anteriores)

### 📦 Model Changes
- Añadidos campos en `product.template`:
  - `grupo_id` (Many2one a product.category)
  - `subgrupo_id` (Many2one a product.category)
  - `familia_id` (Many2one a product.category)
  - Todos con `ondelete='restrict'` para prevenir borrados accidentales

### 🔄 OdooPublisher
- Campo `Usuario` ahora usa formato `ODOO\{login}`
- Ejemplos: `ODOO\admin`, `ODOO\carlosadrian`
- Mantiene consistencia con formato Nesto (`NUEVAVISION\Carlos`)

### 🔐 Security
- Todos los transformers usan `.sudo()` para compatibilidad con endpoint público
- Sin problemas de permisos en producción

### 📋 Dependencies
- Pillow (PIL) - Para validación de imágenes
- requests - Para descarga de imágenes
- Ambas ya instaladas en entorno virtual

### 🧪 Testing
- ✅ Prueba completa con producto TEST001
- ✅ Creación de 6 categorías automáticas
- ✅ Descarga de imagen (8684 bytes)
- ✅ Todos los campos mapeados correctamente
- ✅ Sin errores de permisos

### 📄 Documentation
- Añadido `DESPLIEGUE_V2.4.0.md` con instrucciones completas
- Checklist de despliegue en producción
- Tests post-despliegue
- Guía de rollback

---

## [2.3.4] - 2025-11-13 ✅ EN PRODUCCIÓN

### 🔴 CRÍTICO - Fixed
- **Manejo de estructuras de mensaje con/sin wrapper**
  - Añadido `_extract_entity_data()` para compatibilidad con ambos formatos
  - Clientes: `{"Cliente": {...}, "Origen": "...", "Usuario": "..."}`
  - Productos: `{"Producto": "123", "Nombre": "...", ...}` (plano)
  - Detecta automáticamente el tipo de estructura y extrae datos correctamente

### Verified
- ✅ Productos sincronizando correctamente desde Nesto
- ✅ Logs de producción: "Mensaje plano detectado - 'Producto' contiene valor simple"
- ✅ Product.template creado con ID: 3
- ✅ Anti-bucle funcionando

---

## [2.3.3] - 2025-11-13

### 🔴 CRÍTICO - Fixed
- **Detección de entidad usando campo "Tabla" como fuente de verdad**
  - Antes: Detectaba por presencia de campos (`if 'Cliente' in message`)
  - Problema: Productos se procesaban como clientes (ID 15355 afectado)
  - Ahora: Usa campo "Tabla" como prioridad 1
  - Mapeo: `Clientes→cliente`, `Productos→producto`, `Proveedores→proveedor`

### Changed
- `_detect_entity_type()` refactorizado con 3 niveles de detección:
  1. Campo "Tabla" (más confiable)
  2. Campo "entity_type" explícito
  3. Fallback: Detección por campos presentes

---

## [2.3.2] - 2025-11-13

### Refactored
- **Validación genérica de id_fields usando entity_configs**
  - Eliminado código hardcoded de `cliente_externo`, `contacto_externo`
  - `_should_sync_record()` ahora usa `id_fields` de configuración
  - Funciona para cualquier entidad sin modificar código
  - Logs mejorados con información específica de cada entidad

### Developer Experience
- Sin más código spaghetti con `if` específicos por entidad
- Arquitectura más limpia y mantenible

---

## [2.3.1] - 2025-11-13

### Added
- **Enriquecimiento de mapeo de productos**
  - Campo `PrecioProfesional` → `list_price`
  - Campo `Tamanno` → `volume`
  - Campo `CodigoBarras` → `barcode`
  - Transformer `ficticio_to_detailed_type`:
    - `Ficticio=0` → `'product'` (almacenable)
    - `Ficticio=1 + Grupo='CUR'` → `'service'` (servicio)
    - `Ficticio=1 + Grupo!='CUR'` → `'consu'` (consumible)

### Changed
- `Producto` ahora mapea a **ambos** `producto_externo` y `default_code`

---

## [2.3.0] - 2025-11-13

### 🎉 Added - Nueva Entidad: Productos
- Sincronización bidireccional de productos (Nesto ↔ Odoo)
- Modelo: `product.template`
- Campo `producto_externo` para identificación única
- Mapeo básico de campos (fase minimalista):
  - `Producto` → `producto_externo` + `default_code`
  - `Nombre` → `name`
  - `Precio` → `list_price`
  - `Tamaño` → `volume`

### Dependencies
- Módulo `product` añadido a dependencias

### Documentation
- Nuevo archivo: `SINCRONIZACION_PRODUCTOS.md`
- Roadmap de Fase 2: UnidadMedida, Categorías, Proveedor, Imagen

---

## [2.2.3] - 2025-11-11

### 🔴 CRÍTICO - Fixed
- **Detección de cambios incorrecta**
  - Problema: `_should_sync_record()` comparaba valores ya actualizados
  - Solución: Guardar valores originales ANTES del `write()`
  - Previene bucles infinitos por comparaciones siempre iguales

---

## [2.2.2] - 2025-11-11

### Fixed
- Optimización de logs para prevenir bucle infinito por jerarquías recursivas
- Reducción de verbosidad en logs de sincronización

---

## [2.2.1] - 2025-11-11

### 🔴 CRÍTICO - Fixed
- **Bucle infinito Odoo ↔ Nesto**
  - Añadido `skip_sync=True` en GenericService para evitar re-publicación
  - Context propagado correctamente en `create()` y `write()`

---

## [2.2.0] - 2025-11-10

### Added
- Sincronización bidireccional de clientes
- Sistema genérico de configuración (entity_configs.py)
- Transformers reutilizables (phone, country_state, etc.)
- Anti-bucle mediante detección de cambios
- Jerarquía parent/children (PersonasContacto)

---

## [2.1.x] - Octubre 2025

### Initial Release
- Sincronización unidireccional Nesto → Odoo
- Clientes básicos
- Integración con Google Cloud Pub/Sub

---

## Roadmap

### 🔜 Fase 2 - Productos (Próxima)
- [ ] UnidadMedida → `uom_id` (transformer)
- [ ] Grupo/Subgrupo/Familia → `categ_id` (categorías jerárquicas)
- [ ] Proveedor → `product.supplierinfo`
- [ ] UrlFoto → `image_1920` (descarga + base64)

### 🔮 Fase 3 - Testing
- [ ] Tests unitarios Nesto → Odoo
- [ ] Tests Odoo → Nesto
- [ ] Tests anti-bucle
- [ ] Benchmarks de rendimiento

### 🚀 Futuro
- [ ] Sincronización de pedidos
- [ ] Sincronización de stock
- [ ] Dashboard de métricas
- [ ] Webhook de confirmación a Nesto

---

**Leyenda:**
- 🔴 CRÍTICO: Fix que previene errores graves o pérdida de datos
- 🎉 NEW: Nueva funcionalidad
- ✅ VERIFIED: Verificado en producción
- 🔜 NEXT: Próxima funcionalidad planificada
