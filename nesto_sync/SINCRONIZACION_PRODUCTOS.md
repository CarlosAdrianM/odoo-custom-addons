# Sincronización de Productos - Fase Minimalista

## Resumen

Se ha implementado la sincronización bidireccional de productos entre Nesto y Odoo siguiendo un enfoque minimalista. Esta es la **Fase 1** que establece la base para futuras expansiones.

## Fecha de Implementación

**Versión**: 2.3.0
**Fecha**: 2025-11-13

## Componentes Implementados

### 1. Modelo Extendido: `product.template`

**Ubicación**: [models/product_template.py](models/product_template.py)

Se extiende el modelo estándar de Odoo `product.template` para:
- Heredar de `bidirectional.sync.mixin` (sincronización automática Odoo → Nesto)
- Añadir campo `producto_externo` (referencia al ID de producto en Nesto)
- Validación de unicidad para `producto_externo`

```python
class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['bidirectional.sync.mixin', 'product.template']

    producto_externo = fields.Char(
        string="Producto Externo",
        index=True,
        help="Referencia externa del producto en Nesto"
    )
```

### 2. Configuración de Entidad

**Ubicación**: [config/entity_configs.py](config/entity_configs.py:228-312)

Se configuró la entidad `producto` con:

#### Campos Mapeados (Nesto → Odoo)

| Campo Nesto | Campo Odoo | Tipo | Observaciones |
|------------|-----------|------|---------------|
| `Producto` | `producto_externo` + `default_code` | ID | Identificador único + Referencia interna |
| `Nombre` | `name` | Texto | Requerido |
| `PrecioProfesional` | `list_price` | Decimal | Precio de venta |
| `Tamanno` | `volume` | Decimal | Opcional |
| `CodigoBarras` | `barcode` | Texto | Código de barras EAN |
| `Ficticio` + `Grupo` | `detailed_type` | Selection | Ver lógica abajo |

#### Lógica de `detailed_type` (Transformer)

El campo `detailed_type` se determina usando el transformer `ficticio_to_detailed_type`:

- **Si `Ficticio == 0`** → `'product'` (Producto almacenable)
- **Si `Ficticio == 1` y `Grupo == "CUR"`** → `'service'` (Servicio)
- **Si `Ficticio == 1` y `Grupo != "CUR"`** → `'consu'` (Consumible)

#### Campos Fijos

- `company_id`: ID de la compañía del usuario actual

#### Configuración de Sincronización Bidireccional

- **Habilitada**: `bidirectional: True`
- **Topic PubSub**: `sincronizacion-tablas`
- **Tabla Nesto**: `Productos`

### 3. Base de Datos

El campo `producto_externo` se añadió automáticamente a la tabla `product_template` con:
- Tipo: `VARCHAR`
- Índice: `product_template_producto_externo_index`
- Constraint: Unicidad validada a nivel de modelo

## Campos Pendientes para Fase 2

Los siguientes campos están documentados pero NO implementados en esta fase:

### UnidadMedida
- **Campo Nesto**: `UnidadMedida`
- **Campo Odoo**: `uom_id`, `uom_po_id`
- **Requiere**: Transformer para mapear texto → `product.uom` (Many2one)
- **Ejemplo**: "kg", "unidad", "litro" → búsqueda en tabla `uom`

### Relaciones con Categorías
- **Campo Nesto**: `Grupo`, `Subgrupo`, `Familia`
- **Campo Odoo**: `categ_id` (Many2one a `product.category`)
- **Requiere**:
  - Transformer para mapear jerarquía Nesto → categorías Odoo
  - Lógica para crear categorías si no existen
  - Posible estructura jerárquica: Grupo > Subgrupo > Familia

### Proveedor
- **Campo Nesto**: `Proveedor`
- **Campo Odoo**: Relación con `product.supplierinfo`
- **Requiere**:
  - Búsqueda de proveedor en `res.partner` (supplier_rank > 0)
  - Creación de registro en `product.supplierinfo`
  - Mapeo de precios de compra

### Imagen del Producto
- **Campo Nesto**: `UrlFoto`
- **Campo Odoo**: `image_1920` (imagen principal en base64)
- **Requiere**:
  - Transformer `url_to_image` para descargar imagen desde URL
  - Conversión a base64
  - Manejo de errores (timeout, 404, etc.)
  - Caché opcional para evitar descargas repetidas
- **Ejemplo URL**: `https://www.productosdeesteticaypeluqueriaprofesional.com/1279-home_default/rollo-papel-camilla.jpg`

## Flujo de Sincronización

### Nesto → Odoo

1. Mensaje llega a `/nesto_sync/webhook` con tabla `"Productos"`
2. `MessageProcessor` identifica la entidad `producto`
3. `EntityProcessor` aplica mapeos de campos según `entity_configs.py`
4. Se busca producto por `producto_externo`
5. Si existe: actualización. Si no: creación
6. Se valida unicidad de `producto_externo`

### Odoo → Nesto

1. Usuario modifica producto en Odoo (via UI o código)
2. `BidirectionalSyncMixin.write()` intercepta el cambio
3. Se verifica si realmente hubo cambios (anti-bucle)
4. `OdooPublisher` serializa el cambio
5. Se publica mensaje a PubSub con estructura:
```json
{
  "Tabla": "Productos",
  "Operacion": "Update",
  "DatosActualizados": {
    "Producto": "123",
    "Nombre": "Producto modificado",
    "Precio": 99.99,
    ...
  }
}
```

## Módulos de Odoo Instalados

Para tener vistas operativas completas:

- **product** (base de productos)
- **stock** (inventario y almacenes)

Estos módulos proporcionan:
- Vistas de lista/formulario de productos
- Gestión de stock
- Ubicaciones de almacén
- Movimientos de inventario

## Arquitectura de Decisión

### ¿Por qué `producto_externo` en lugar de `default_code`?

Se decidió usar un campo personalizado `producto_externo` por:

1. **Consistencia**: Sigue el patrón de `cliente_externo`, `contacto_externo`
2. **Separación de concerns**: `default_code` puede usarse para SKUs internos
3. **Claridad**: Inmediatamente obvio qué campo es para sincronización
4. **Flexibilidad futura**: Sin conflictos si se necesita `default_code` para otra cosa

### ¿Por qué `product.template` en lugar de `product.product`?

- `product.template`: Plantilla de producto (ej: "Camiseta")
- `product.product`: Variantes (ej: "Camiseta Roja M", "Camiseta Azul L")

Se eligió `product.template` porque:
1. Nesto envía productos simples, no variantes
2. Es el modelo principal en Odoo
3. Más simple para la fase minimalista
4. Si en el futuro se necesitan variantes, se puede migrar

## Próximos Pasos

### Fase 2: Enriquecimiento de Campos

1. **Implementar transformer para UnidadMedida**
   - Crear `transformers/unidad_medida.py`
   - Mapear strings a `product.uom`
   - Manejar casos no encontrados

2. **Implementar transformer para Categorías**
   - Crear `transformers/product_category.py`
   - Mapear Grupo/Subgrupo/Familia a `product.category`
   - Crear categorías automáticamente si no existen

3. **Implementar relación con Proveedores**
   - Crear `transformers/proveedor.py`
   - Buscar/crear proveedor en `res.partner`
   - Gestionar `product.supplierinfo`

4. **Implementar descarga de imágenes**
   - Crear transformer `url_to_image`
   - Descargar imagen desde `UrlFoto`
   - Convertir a base64 y asignar a `image_1920`
   - Manejo robusto de errores (timeout, 404, formato inválido)
   - Considerar caché para evitar descargas repetidas del mismo producto

### Fase 3: Testing

1. Crear tests para sincronización Nesto → Odoo
2. Crear tests para sincronización Odoo → Nesto
3. Validar anti-bucle infinito
4. Pruebas de rendimiento con volumen alto

## Testing Manual

### Crear Producto desde Nesto

```bash
curl -X POST https://tu-odoo.com/nesto_sync/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "Tabla": "Productos",
    "Operacion": "Insert",
    "Datos": {
      "Producto": "17404",
      "Nombre": "ROLLO PAPEL CAMILLA",
      "PrecioProfesional": 7.49,
      "Tamanno": 100,
      "CodigoBarras": "0",
      "Ficticio": 0,
      "Grupo": "ACC"
    }
  }'
```

### Ejemplo Completo de Mensaje desde Nesto

```json
{
  "$id": "1",
  "Producto": "17404",
  "Nombre": "ROLLO PAPEL CAMILLA",
  "Tamanno": 100,
  "UnidadMedida": "m",
  "Familia": "Productos Genéricos",
  "PrecioProfesional": 7.49,
  "PrecioPublicoFinal": 12.95,
  "Estado": 0,
  "Grupo": "ACC",
  "Subgrupo": "Desechables",
  "CodigoBarras": "0",
  "Ficticio": 0
}
```

**Campos procesados en esta fase:**
- `Producto` → `producto_externo` + `default_code`
- `Nombre` → `name`
- `PrecioProfesional` → `list_price`
- `Tamanno` → `volume`
- `CodigoBarras` → `barcode`
- `Ficticio` + `Grupo` → `detailed_type`

**Campos ignorados (fase 2):**
- `UnidadMedida`, `Familia`, `Subgrupo`, `PrecioPublicoFinal`, `Estado`

### Verificar en Base de Datos

```sql
SELECT id, name, default_code, list_price, producto_externo, volume, barcode, detailed_type
FROM product_template
WHERE producto_externo = '17404';
```

### Actualizar desde Odoo (UI)

1. Ir a Inventario > Productos
2. Buscar producto con `producto_externo = '17404'`
3. Modificar nombre o precio
4. Guardar
5. Verificar que se publica mensaje a PubSub

## Nuevos Componentes (v2.3.1)

### Transformer: `ficticio_to_detailed_type`

**Ubicación**: [transformers/field_transformers.py](transformers/field_transformers.py:251-288)

Este transformer lee dos campos del mensaje de Nesto (`Ficticio` y `Grupo`) y determina el tipo de producto en Odoo:

```python
@FieldTransformerRegistry.register('ficticio_to_detailed_type')
class FicticioToDetailedTypeTransformer:
    def transform(self, value, context):
        ficticio = bool(value) if value is not None else False

        if not ficticio:
            return {'detailed_type': 'product'}  # Almacenable

        nesto_data = context.get('nesto_data', {})
        grupo = nesto_data.get('Grupo', '')

        if grupo == 'CUR':
            return {'detailed_type': 'service'}  # Servicio
        else:
            return {'detailed_type': 'consu'}  # Consumible
```

**Uso en `entity_configs.py`:**

```python
'Ficticio': {
    'transformer': 'ficticio_to_detailed_type',
    'odoo_fields': ['detailed_type']
}
```

## Logs y Debugging

Los logs de sincronización están en:
- `/opt/odoo16/logs/odoo.log` (servidor)
- Endpoint: `https://tu-odoo.com/nesto_sync/logs` (últimos 100 logs en memoria)

Buscar por:
- `producto` (entidad)
- `product.template` (modelo)
- `producto_externo` (campo)

## Fixes Críticos Implementados

### v2.3.3 - Fix Detección de Entidad por Campo "Tabla"

**Fecha:** 2025-11-13

**Problema Identificado:**
El método `_detect_entity_type()` detectaba el tipo de entidad verificando la presencia de campos en orden secuencial:
```python
if 'Cliente' in message:
    return 'cliente'  # ❌ Siempre se ejecutaba primero
elif 'Producto' in message:
    return 'producto'
```

Esto causaba que mensajes de **productos se procesaran como clientes** si contenían algún campo "Cliente" (por ejemplo, en logs del error se observó que el ID 15355 se actualizaba tanto para clientes como para productos).

**Solución:**
Ahora `_detect_entity_type()` usa el campo **"Tabla"** como prioridad 1:

```python
if 'Tabla' in message:
    tabla = message['Tabla']
    tabla_to_entity = {
        'Clientes': 'cliente',
        'Proveedores': 'proveedor',
        'Productos': 'producto',
    }
    return tabla_to_entity[tabla]
```

**Resultado:**
- ✅ Detección correcta de tipo de entidad usando metadata explícita
- ✅ Fallback a detección por campos si no existe "Tabla"
- ✅ Mensajes de error descriptivos

**Ubicación:** [controllers/controllers.py:82-98](controllers/controllers.py#L82-L98)

---

### v2.3.4 - Manejo de Estructuras con/sin Wrapper

**Fecha:** 2025-11-13

**Contexto:**
El usuario identificó que Nesto podría enviar mensajes con estructuras diferentes:
- **Clientes:** `{"Cliente": {...datos...}, "Origen": "...", "Usuario": "..."}`
- **Productos:** `{"Producto": "15191", "Nombre": "...", ...}` (plano)

**Solución:**
Añadido método `_extract_entity_data()` que maneja ambos casos automáticamente:

```python
def _extract_entity_data(self, message, entity_type):
    wrapper_key = wrapper_keys.get(entity_type)  # 'Cliente', 'Producto', etc.

    if wrapper_key and wrapper_key in message:
        nested_data = message.get(wrapper_key)

        if isinstance(nested_data, dict):
            # Wrapper con objeto anidado
            return nested_data
        else:
            # Valor simple, mensaje plano
            return message
    else:
        # Sin wrapper, mensaje plano
        return message
```

**Resultado (verificado en producción):**
```
"Mensaje plano detectado - 'Producto' contiene valor simple"
"product.template creado con ID: 3"
```

- ✅ Compatibilidad con estructuras con wrapper (clientes)
- ✅ Compatibilidad con estructuras planas (productos)
- ✅ Logs de debug para identificar estructura detectada
- ✅ Código defensivo y robusto

**Ubicación:** [controllers/controllers.py:119-163](controllers/controllers.py#L119-L163)

---

## Estado Actual en Producción

**Versión Desplegada:** 2.3.4
**Fecha de Despliegue:** 2025-11-13
**Estado:** ✅ Operativo

### Logs de Producción (Verificados)

```json
{
  "totalLogs": 18,
  "logs": [
    "INFO: Sincronizando entidad de tipo: producto",
    "DEBUG: Mensaje plano detectado - 'Producto' contiene valor simple",
    "INFO: Procesando mensaje de tipo producto",
    "INFO: Creando nuevo product.template",
    "INFO: product.template creado con ID: 3",
    "DEBUG: Saltando sincronización para 1 nuevos registros (contexto skip_sync)"
  ]
}
```

### Verificación de Funcionalidad

✅ **Nesto → Odoo:**
- Detección correcta por campo "Tabla": "Productos"
- Estructura plana manejada correctamente
- Producto creado con ID 3
- Campos mapeados: default_code='15191', volume=500

✅ **Anti-bucle:**
- `skip_sync=True` funcionando
- No se publica el registro recién creado de vuelta a Nesto

✅ **Sincronización Bidireccional:**
- Configurada y lista para Odoo → Nesto
- Pendiente de testing cuando se modifique un producto desde Odoo UI

## Referencias

- Arquitectura general: [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md)
- Config de entidades: [config/entity_configs.py](config/entity_configs.py)
- Mixin bidireccional: [models/bidirectional_sync_mixin.py](models/bidirectional_sync_mixin.py)
