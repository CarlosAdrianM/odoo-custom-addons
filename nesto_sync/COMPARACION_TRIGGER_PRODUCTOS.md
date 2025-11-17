# Comparación: Trigger Productos - Versión Anterior vs v2.5.0

## Resumen Ejecutivo

**Versión Anterior**: 5 campos sincronizados
**Versión v2.5.0**: 12 campos sincronizados (+7 campos nuevos)

---

## Campos Sincronizados

### ✅ Campos que YA existían (v2.4.x)

| Campo SQL Server | Campo Odoo | Tipo | Descripción |
|------------------|------------|------|-------------|
| `Nombre` | `name` | Text | Nombre del producto |
| `PVP` | `list_price` | Numeric | Precio profesional |
| `Estado` | `active` | Numeric | Estado del producto (0=inactivo, 1=activo) |
| `RoturaStockProveedor` | _(campo técnico)_ | Numeric | Rotura de stock |
| `CodBarras` | `barcode` | Text | Código de barras EAN |

### 🆕 Campos NUEVOS añadidos (v2.5.0)

| Campo SQL Server | Campo Odoo | Tipo | Descripción | Funcionalidad v2.5.0 |
|------------------|------------|------|-------------|----------------------|
| `Grupo` | `grupo_id` | Text | Grupo del producto (ej: "COS") | Categorización visible en UI |
| `Subgrupo` | `subgrupo_id` | Text | Subgrupo (ej: "Aceites profesionales") | Categorización visible en UI |
| `Familia` | `familia_id` | Text | Familia (ej: "Eva Visnú") | Categorización visible en UI |
| `Tamaño` | `weight`/`volume`/`product_length` | Numeric | Tamaño numérico del producto | Conversión inteligente según UnidadMedida |
| `UnidadMedida` | `uom_id` | Text | Unidad de medida (ml, g, cm, etc.) | Determina el tipo de dimensión |
| `UrlFoto` | `image_1920` + `url_imagen_actual` | Text (URL) | URL de la imagen del producto | Descarga optimizada con cache |
| `Ficticio` | `detailed_type` | Bit/Boolean | Indica si es producto ficticio | Mapeo a tipo de producto Odoo |

---

## Comparación del Código SQL

### Versión Anterior (v2.4.x)

```sql
WHERE
    -- Solo 5 campos comparados
    ISNULL(LTRIM(RTRIM(i.Nombre)), '') <> ISNULL(LTRIM(RTRIM(d.Nombre)), '') OR
    ISNULL(i.PVP, 0) <> ISNULL(d.PVP, 0) OR
    ISNULL(i.Estado, 0) <> ISNULL(d.Estado, 0) OR
    ISNULL(i.RoturaStockProveedor, 0) <> ISNULL(d.RoturaStockProveedor, 0) OR
    ISNULL(LTRIM(RTRIM(i.CodBarras)), '') <> ISNULL(LTRIM(RTRIM(d.CodBarras)), '') OR

    -- Detección NULL ↔ Valor (solo 5 campos)
    (i.Nombre IS NULL AND d.Nombre IS NOT NULL) OR
    (i.Nombre IS NOT NULL AND d.Nombre IS NULL) OR
    (i.PVP IS NULL AND d.PVP IS NOT NULL) OR
    (i.PVP IS NOT NULL AND d.PVP IS NULL) OR
    (i.Estado IS NULL AND d.Estado IS NOT NULL) OR
    (i.Estado IS NOT NULL AND d.Estado IS NULL) OR
    (i.RoturaStockProveedor IS NULL AND d.RoturaStockProveedor IS NOT NULL) OR
    (i.RoturaStockProveedor IS NOT NULL AND d.RoturaStockProveedor IS NULL) OR
    (i.CodBarras IS NULL AND d.CodBarras IS NOT NULL) OR
    (i.CodBarras IS NOT NULL AND d.CodBarras IS NULL)
```

### Versión Nueva (v2.5.0)

```sql
WHERE
    -- ========================================
    -- CAMPOS DE TEXTO (7 campos con trim)
    -- ========================================
    ISNULL(LTRIM(RTRIM(i.Nombre)), '') <> ISNULL(LTRIM(RTRIM(d.Nombre)), '') OR
    ISNULL(LTRIM(RTRIM(i.CodBarras)), '') <> ISNULL(LTRIM(RTRIM(d.CodBarras)), '') OR
    ISNULL(LTRIM(RTRIM(i.Grupo)), '') <> ISNULL(LTRIM(RTRIM(d.Grupo)), '') OR           -- NUEVO
    ISNULL(LTRIM(RTRIM(i.Subgrupo)), '') <> ISNULL(LTRIM(RTRIM(d.Subgrupo)), '') OR     -- NUEVO
    ISNULL(LTRIM(RTRIM(i.Familia)), '') <> ISNULL(LTRIM(RTRIM(d.Familia)), '') OR       -- NUEVO
    ISNULL(LTRIM(RTRIM(i.UnidadMedida)), '') <> ISNULL(LTRIM(RTRIM(d.UnidadMedida)), '') OR  -- NUEVO
    ISNULL(LTRIM(RTRIM(i.UrlFoto)), '') <> ISNULL(LTRIM(RTRIM(d.UrlFoto)), '') OR       -- NUEVO

    -- ========================================
    -- CAMPOS NUMÉRICOS (4 campos)
    -- ========================================
    ISNULL(i.PVP, 0) <> ISNULL(d.PVP, 0) OR
    ISNULL(i.Estado, 0) <> ISNULL(d.Estado, 0) OR
    ISNULL(i.RoturaStockProveedor, 0) <> ISNULL(d.RoturaStockProveedor, 0) OR
    ISNULL(i.Tamaño, 0) <> ISNULL(d.Tamaño, 0) OR                                       -- NUEVO

    -- ========================================
    -- CAMPOS BOOLEANOS (1 campo)
    -- ========================================
    ISNULL(i.Ficticio, 0) <> ISNULL(d.Ficticio, 0) OR                                   -- NUEVO

    -- ========================================
    -- DETECCIÓN EXPLÍCITA NULL ↔ VALOR (12 campos × 2)
    -- ========================================
    -- [... comparaciones NULL para TODOS los campos ...]
```

---

## Diferencias Clave

### 1. Campos de Categorización (Nuevos)

Los campos `Grupo`, `Subgrupo` y `Familia` permiten:
- Clasificación jerárquica de productos
- Visualización en formularios Odoo
- Filtros y búsquedas por categoría

**Ejemplo**:
```
Producto: ACIDO HIALURONICO RICCHEZZA
Grupo: COS
Subgrupo: Aceites, fluidos y geles profesionales
Familia: Eva Visnú
```

### 2. Campos de Dimensiones (Nuevos)

Los campos `Tamaño` y `UnidadMedida` permiten:
- Conversión automática a unidades base (kg, m³, m)
- Mapeo a campos dimensionales de Odoo (`weight`, `volume`, `product_length`)
- Integración con módulo `product_dimension` (OCA)

**Ejemplo**:
```
Tamaño: 100
UnidadMedida: ml
→ Odoo recibe: volume = 0.0001 m³
```

### 3. Campo de Imagen (Nuevo)

El campo `UrlFoto` permite:
- Descarga automática de imágenes de productos
- Cache inteligente (solo descarga si cambió la URL)
- Almacenamiento en `image_1920` de Odoo

**Ejemplo**:
```
UrlFoto: https://www.productosdeesteticaypeluqueriaprofesional.com/102148-home_default/acido-hialuronico-ricchezza-100ml.jpg
→ Odoo descarga y almacena la imagen
```

### 4. Campo Ficticio (Nuevo)

El campo `Ficticio` permite:
- Distinguir productos reales vs ficticios
- Mapeo a `detailed_type` de Odoo (`product` vs `service`)

---

## Impacto en Sincronización

### Antes (v2.4.x)

El trigger solo detectaba cambios en:
- Datos básicos: nombre, precio, estado
- Códigos: código de barras
- Stock: rotura de stock

**Total**: 5 campos

### Ahora (v2.5.0)

El trigger detecta cambios en:
- Datos básicos: nombre, precio, estado
- Códigos: código de barras
- Stock: rotura de stock
- **Categorización**: grupo, subgrupo, familia
- **Dimensiones**: tamaño, unidad de medida
- **Multimedia**: URL de foto
- **Tipo**: ficticio/real

**Total**: 12 campos (+140% más campos)

---

## Ejemplos de Cambios Detectados

### Caso 1: Cambio de Grupo

```sql
-- Antes: Producto sin categoría
UPDATE Productos SET Grupo = 'COS' WHERE Número = '35894'

-- Trigger detecta:
-- i.Grupo = 'COS', d.Grupo = NULL
-- → Se registra en Nesto_sync
```

### Caso 2: Cambio de Tamaño

```sql
-- Antes: Producto de 100ml
UPDATE Productos SET Tamaño = 250 WHERE Número = '35894'

-- Trigger detecta:
-- i.Tamaño = 250, d.Tamaño = 100
-- → Se registra en Nesto_sync
-- → Odoo recalcula: 250ml × 0.000001 = 0.00025 m³
```

### Caso 3: Cambio de Imagen

```sql
-- Antes: Producto con imagen antigua
UPDATE Productos SET UrlFoto = 'https://nueva-url.com/imagen.jpg' WHERE Número = '35894'

-- Trigger detecta:
-- i.UrlFoto <> d.UrlFoto
-- → Se registra en Nesto_sync
-- → Odoo descarga nueva imagen
```

---

## Despliegue del Trigger Actualizado

### Paso 1: Conectar a SQL Server

```bash
# Desde servidor de producción
sqlcmd -S localhost -d NestoVisionDB -U sa
```

O desde SQL Server Management Studio (SSMS):
- Conectar a la base de datos `NestoVisionDB`
- Abrir nueva consulta

### Paso 2: Aplicar el Trigger

Copiar y ejecutar el contenido de **[TRIGGER_PRODUCTOS_ACTUALIZADO.sql](TRIGGER_PRODUCTOS_ACTUALIZADO.sql)**

### Paso 3: Verificar

```sql
-- Ver que el trigger está activo
SELECT name, is_disabled
FROM sys.triggers
WHERE name = 'tr_Productos_Sync_Update';

-- Resultado esperado:
-- name                          is_disabled
-- tr_Productos_Sync_Update      0

-- Ver el código del trigger
EXEC sp_helptext 'tr_Productos_Sync_Update';
```

### Paso 4: Probar

```sql
-- Actualizar un producto de prueba
UPDATE Productos
SET Grupo = 'TEST'
WHERE Número = '35894' AND Empresa = '1';

-- Verificar que se registró en Nesto_sync
SELECT TOP 1 *
FROM Nesto_sync
WHERE Tabla = 'Productos' AND ModificadoId = '35894'
ORDER BY Id DESC;
```

---

## Verificación Post-Despliegue

### 1. Actualizar un producto en SQL Server

```sql
UPDATE Productos
SET
    Nombre = 'ACIDO HIALURONICO RICCHEZZA (EDITADO)',
    Grupo = 'COS',
    Subgrupo = 'Aceites, fluidos y geles profesionales',
    Familia = 'Eva Visnú',
    Tamaño = 100,
    UnidadMedida = 'ml',
    UrlFoto = 'https://www.productosdeesteticaypeluqueriaprofesional.com/102148-home_default/acido-hialuronico-ricchezza-100ml.jpg'
WHERE Número = '35894' AND Empresa = '1';
```

### 2. Verificar en Nesto_sync

```sql
SELECT *
FROM Nesto_sync
WHERE Tabla = 'Productos' AND ModificadoId = '35894'
ORDER BY Id DESC;
```

**Esperado**: Debe haber un registro nuevo con el ID del producto.

### 3. Verificar en Odoo (logs)

```bash
sudo journalctl -u odoo16 -f | grep -E "35894|Producto|ACIDO"
```

**Esperado**: Ver logs como:
```
INFO ... Procesando mensaje de tipo producto
INFO ... Cambio en grupo_id: 'None' -> '5'
INFO ... Cambio en volume: '0.0' -> '0.0001'
INFO ... Cambio en image_1920: 'None' -> '<image_data: 109328 bytes>'
INFO ... product.template actualizado: ID 1234
```

### 4. Verificar en UI de Odoo

1. Ir a **Ventas → Productos → Producto 35894**
2. Verificar que los campos nuevos están presentes:
   - **Grupo**: COS
   - **Subgrupo**: Aceites, fluidos y geles profesionales
   - **Familia**: Eva Visnú
   - **Volumen**: 0.0001 m³
   - **Imagen**: Visible en el formulario

---

## Notas Importantes

### ⚠️ Campos que NO se sincronizan

Los siguientes campos de la tabla `Productos` **no** se sincronizan porque no están mapeados en `entity_configs.py`:

- `Descripcion`: Descripción larga del producto
- `Stock`: Stock actual (se maneja separadamente)
- `FechaCreacion`, `FechaModificacion`: Campos de auditoría
- Otros campos internos de Nesto

Si necesitas sincronizar alguno de estos campos:
1. Añadirlo a `entity_configs.py` en la sección `producto.field_mappings`
2. Actualizar este trigger para incluirlo en las comparaciones
3. Reiniciar Odoo y actualizar el módulo `nesto_sync`

### ⚠️ Tipos de Datos

Asegúrate de que los tipos de datos en SQL Server coincidan con los esperados:

| Campo | Tipo SQL Server | Notas |
|-------|-----------------|-------|
| `Tamaño` | `DECIMAL` o `NUMERIC` | Si es `VARCHAR`, el trigger necesita `CAST` |
| `UnidadMedida` | `VARCHAR` | Debe ser texto (ml, g, cm, etc.) |
| `Ficticio` | `BIT` | Booleano (0 o 1) |
| `UrlFoto` | `VARCHAR(MAX)` o `NVARCHAR(MAX)` | URLs pueden ser largas |

### ⚠️ Usuario RDS2016$

El trigger ignora cambios realizados por `NUEVAVISION\RDS2016$` para evitar bucles infinitos si Odoo escribe de vuelta a SQL Server.

Si usas otro usuario para sincronización inversa (Odoo → Nesto), ajusta la condición:
```sql
IF (SYSTEM_USER != 'NUEVAVISION\TU_USUARIO$')
```

---

## Resumen de Cambios

| Aspecto | Antes (v2.4.x) | Ahora (v2.5.0) | Diferencia |
|---------|----------------|----------------|------------|
| **Campos sincronizados** | 5 | 12 | +7 campos (+140%) |
| **Campos de texto** | 2 | 7 | +5 campos |
| **Campos numéricos** | 3 | 4 | +1 campo |
| **Campos booleanos** | 0 | 1 | +1 campo |
| **Funcionalidades** | Básico | Dimensiones + Categorización + Imágenes | ⭐ Grandes mejoras |

---

**Fecha**: 2025-11-17
**Versión**: v2.5.0
**Archivo de trigger**: [TRIGGER_PRODUCTOS_ACTUALIZADO.sql](TRIGGER_PRODUCTOS_ACTUALIZADO.sql)
