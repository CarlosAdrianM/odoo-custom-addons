# Sincronización de BOMs (Bills of Materials)

## Introducción

El módulo `nesto_sync` v2.8.0 incluye sincronización bidireccional completa de Listas de Materiales (BOMs) entre Nesto y Odoo, permitiendo gestionar productos tipo "kit" automáticamente.

## Funcionalidades

### ✅ Sincronización Nesto → Odoo

Cuando Nesto envía un mensaje con el campo `ProductosKit`, el módulo:

1. **Crea/actualiza BOM automáticamente** en Odoo (módulo MRP)
2. **Valida componentes** - Si falta alguno → DLQ (no se sincroniza parcialmente)
3. **Detecta ciclos infinitos** - Evita BOMs circulares (A → B → A)
4. **Elimina BOM** si ProductosKit está vacío

### ✅ Sincronización Odoo → Nesto

Cuando se modifica una BOM en Odoo:

1. **Publica mensaje a PubSub** con campo `ProductosKit` actualizado
2. **Valida componentes** - Todos deben tener `producto_externo`
3. **Formato estándar** - `[{"ProductoId": "...", "Cantidad": ...}]`

## Formatos Soportados

El campo `ProductosKit` acepta **3 formatos diferentes**:

### 1. Array de Objetos (Recomendado)
```json
{
  "Tabla": "Productos",
  "Producto": "KIT001",
  "ProductosKit": [
    {"ProductoId": "123", "Cantidad": 2},
    {"ProductoId": "456", "Cantidad": 1},
    {"ProductoId": "789", "Cantidad": 3}
  ]
}
```

### 2. Array de IDs (Simplificado)
```json
{
  "Tabla": "Productos",
  "Producto": "KIT002",
  "ProductosKit": [123, 456, 789]
}
```
**Nota:** Cuando se usa este formato, la cantidad de cada componente es 1.

### 3. JSON String (Legacy)
```json
{
  "Tabla": "Productos",
  "Producto": "KIT003",
  "ProductosKit": "[{\"ProductoId\": \"123\", \"Cantidad\": 2}]"
}
```

## Productos MTP (Materias Primas)

Los productos con `Grupo = "MTP"` tienen comportamiento especial:

- ✅ **Se sincronizan normalmente**
- ✅ **Pueden usarse como componentes en BOMs**
- ❌ **NO son vendibles** (`sale_ok = False`)
- 💡 **No aparecen en catálogos de venta**

### Ejemplo: Producto MTP

**Mensaje de Nesto:**
```json
{
  "Tabla": "Productos",
  "Producto": "MP001",
  "Nombre": "Aceite Base",
  "Grupo": "MTP"
}
```

**Resultado en Odoo:**
- `name = "Aceite Base"`
- `producto_externo = "MP001"`
- `sale_ok = False` ← Automático
- Puede usarse en BOMs de otros productos

## Validaciones

### 1. Componentes Faltantes
Si un componente del `ProductosKit` no existe en Odoo:
- ❌ Error: `ValueError`
- 📥 Mensaje va a **Dead Letter Queue (DLQ)**
- 🔄 No se sincroniza parcialmente

**Ejemplo de error:**
```
Componentes de BOM no encontrados para producto KIT001: COMP999, COMP888.
Asegúrate de que estos productos existen en Odoo antes de sincronizar el kit.
```

### 2. Detección de Ciclos

El sistema detecta ciclos infinitos en BOMs usando **DFS** (Depth-First Search):

#### Ciclo Directo (A → A)
```
Producto KIT001 se contiene a sí mismo
```

#### Ciclo Indirecto (A → B → A)
```
KIT_A → KIT_B → KIT_A
```

**Configuración:** Profundidad máxima = 10 niveles

### 3. Validación de producto_externo

Todos los productos en una BOM **deben tener** `producto_externo`:
- ✅ Al sincronizar desde Nesto: Siempre tienen `producto_externo`
- ❌ Al publicar desde Odoo: Error si falta `producto_externo`

## Casos de Uso

### Caso 1: Crear Kit desde Nesto

**Mensaje:**
```json
{
  "Tabla": "Productos",
  "Producto": "KIT_BIENVENIDA",
  "Nombre": "Kit de Bienvenida",
  "ProductosKit": [
    {"ProductoId": "TOALLA", "Cantidad": 2},
    {"ProductoId": "JABON", "Cantidad": 3},
    {"ProductoId": "CHAMPU", "Cantidad": 1}
  ]
}
```

**Resultado:**
- Crea producto `KIT_BIENVENIDA`
- Crea BOM con 3 líneas
- BOM tipo `normal` (no phantom)

### Caso 2: Actualizar Kit desde Nesto

**Mensaje actualizado:**
```json
{
  "Tabla": "Productos",
  "Producto": "KIT_BIENVENIDA",
  "ProductosKit": [
    {"ProductoId": "TOALLA", "Cantidad": 5},  // Cantidad cambiada
    {"ProductoId": "GEL", "Cantidad": 2}      // Componente nuevo
    // JABON y CHAMPU eliminados
  ]
}
```

**Resultado:**
- Actualiza BOM existente
- Elimina líneas antiguas (JABON, CHAMPU)
- Añade línea nueva (GEL)
- Actualiza cantidad de TOALLA

### Caso 3: Convertir Kit a Producto Simple

**Mensaje:**
```json
{
  "Tabla": "Productos",
  "Producto": "KIT_BIENVENIDA",
  "ProductosKit": []
}
```

**Resultado:**
- Elimina BOM completamente
- Producto se convierte en simple (no-kit)

### Caso 4: Modificar BOM desde Odoo

1. Usuario edita BOM en Odoo (app Manufacturing)
2. Al guardar, el sistema:
   - Detecta cambio automáticamente
   - Construye mensaje con `ProductosKit`
   - Publica a PubSub topic `sincronizacion-tablas`

## Arquitectura

### Flujo Nesto → Odoo

```
┌─────────────────────┐
│ Mensaje PubSub      │
│ ProductosKit: [...]│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ GenericProcessor    │
│ SyncProductBom      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ GenericService      │
│ Crea/actualiza      │
│ producto            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ SyncProductBom      │
│ sync_bom_after_save │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Valida componentes  │
│ Valida ciclos       │
│ Crea/actualiza BOM  │
└─────────────────────┘
```

### Flujo Odoo → Nesto

```
┌─────────────────────┐
│ Usuario modifica    │
│ BOM en Odoo         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ BidirectionalSync   │
│ Mixin.write()       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ OdooPublisher       │
│ _add_productos_kit  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Mensaje PubSub      │
│ ProductosKit: [...]│
└─────────────────────┘
```

## Configuración

### Profundidad Máxima de BOM

Editar `transformers/post_processors.py`:

```python
class SyncProductBom:
    MAX_BOM_DEPTH = 10  # Cambiar según necesidad
```

### Tipo de BOM

Por defecto: `type = 'normal'`

Para cambiar a phantom, editar `_create_bom()`:

```python
bom_vals = {
    'type': 'phantom',  # En lugar de 'normal'
    ...
}
```

## Monitoreo

### Ver mensajes fallidos por BOMs

**SQL:**
```sql
SELECT id, error_message, raw_data, retry_count
FROM nesto_sync_failed_message
WHERE error_message LIKE '%BOM%' OR error_message LIKE '%ProductosKit%'
ORDER BY create_date DESC;
```

**Odoo UI:**
1. Ir a **Dead Letter Queue** → **Mensajes Fallidos**
2. Filtrar por `error_message contains "BOM"`

### Logs en tiempo real

```bash
sudo journalctl -u odoo16 -f | grep -i "bom\|productoskit"
```

### Revisar BOMs creadas

**SQL:**
```sql
SELECT
    pt.producto_externo,
    pt.name,
    COUNT(bl.id) as num_componentes
FROM mrp_bom b
JOIN product_template pt ON b.product_tmpl_id = pt.id
JOIN mrp_bom_line bl ON bl.bom_id = b.id
WHERE b.active = true
GROUP BY pt.id, pt.producto_externo, pt.name
ORDER BY pt.producto_externo;
```

## Troubleshooting

### Problema: "Componentes de BOM no encontrados"

**Solución:** Asegurarse de que todos los componentes existen en Odoo antes de sincronizar el kit.

```bash
# Verificar si producto existe
SELECT id, name, producto_externo
FROM product_template
WHERE producto_externo = 'COMP_FALTANTE';
```

### Problema: "Ciclo detectado"

**Solución:** Revisar la estructura de BOMs y eliminar referencias circulares.

**Ejemplo:**
- KIT_A contiene KIT_B
- KIT_B contiene KIT_A
- ❌ Esto crea un ciclo infinito

### Problema: BOM no se actualiza

**Verificar:**
1. ¿Hay cambios reales en ProductosKit?
2. ¿El producto tiene `producto_externo`?
3. Revisar logs por errores de validación

```bash
sudo journalctl -u odoo16 -n 100 | grep -A 5 -B 5 "KIT001"
```

### Problema: AccessError en producción

Si aparece error de permisos:

```
AccessError: No puede ingresar a los registros 'Variante de producto'
```

**Solución:** Ya implementado con `.sudo()` en v2.8.0. Actualizar módulo:

```bash
sudo systemctl restart odoo16
```

## Performance

### Optimizaciones Implementadas

1. **Detección de cambios:** No actualiza BOM si no cambió
2. **Batch processing:** Procesa múltiples kits eficientemente
3. **Validación con caché:** Reutiliza búsquedas de componentes

### Benchmarks (Aproximados)

- **Kit simple (3 componentes):** ~200ms
- **Kit complejo (20 componentes):** ~800ms
- **Kit anidado (3 niveles):** ~1.5s

## Roadmap

### Versiones Futuras

- [ ] Soporte para BOMs phantom
- [ ] Versionado de BOMs (histórico)
- [ ] Optimización de validación de ciclos
- [ ] Soporte para operaciones de BOM (routings)
- [ ] Dashboard de BOMs en Odoo

## Referencias

- **Documentación completa:** [SESSION_SUMMARY_2025-11-20.md](./SESSION_SUMMARY_2025-11-20.md)
- **Tests:** [test_bom_sync.py](../tests/test_bom_sync.py)
- **Tests integración:** [test_bom_integration.py](../tests/test_bom_integration.py)
- **Código principal:** [post_processors.py](../transformers/post_processors.py)

## Soporte

Para reportar problemas o sugerir mejoras:
- Revisar logs en `/var/log/odoo/odoo.log`
- Consultar Dead Letter Queue en Odoo
- Contactar al equipo de desarrollo
