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
| `Producto` | `producto_externo` | ID | Identificador único |
| `Nombre` | `name` | Texto | Requerido |
| `Precio` | `list_price` | Decimal | Precio de venta |
| `Tamano` | `volume` | Decimal | Opcional (fase minimalista) |

#### Campos Fijos

- `type`: Siempre `'product'` (producto almacenable)
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
      "Producto": "PROD001",
      "Nombre": "Producto de Prueba",
      "Precio": 19.99,
      "Tamano": 1.5
    }
  }'
```

### Verificar en Base de Datos

```sql
SELECT id, name, list_price, producto_externo, volume
FROM product_template
WHERE producto_externo = 'PROD001';
```

### Actualizar desde Odoo (UI)

1. Ir a Inventario > Productos
2. Buscar producto con `producto_externo = 'PROD001'`
3. Modificar nombre o precio
4. Guardar
5. Verificar que se publica mensaje a PubSub

## Logs y Debugging

Los logs de sincronización están en:
- `/opt/odoo16/logs/odoo.log` (servidor)
- Endpoint: `https://tu-odoo.com/nesto_sync/logs` (últimos 100 logs en memoria)

Buscar por:
- `producto` (entidad)
- `product.template` (modelo)
- `producto_externo` (campo)

## Referencias

- Arquitectura general: [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md)
- Config de entidades: [config/entity_configs.py](config/entity_configs.py)
- Mixin bidireccional: [models/bidirectional_sync_mixin.py](models/bidirectional_sync_mixin.py)
