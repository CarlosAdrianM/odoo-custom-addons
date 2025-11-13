# Changelog - Nesto Sync

Todos los cambios notables en este proyecto están documentados en este archivo.

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
