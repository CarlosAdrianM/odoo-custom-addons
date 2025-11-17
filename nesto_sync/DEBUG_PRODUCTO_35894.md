# Debug: Producto 35894 - 100ml no se convierte a volume

## Resumen del Problema

**Producto**: 35894 - ACIDO HIALURONICO RICCHEZZA
**Input**: `Tamanno=100`, `UnidadMedida="ml"`
**Output esperado**: `volume = 0.0001 m³` (100ml × 0.000001)
**Output real**: `volume = 0.00 m³`

## Datos del Mensaje JSON

```json
{
  "$id": "1",
  "Producto": "35894",
  "Nombre": "ACIDO HIALURONICO RICCHEZZA",
  "Tamanno": 100,
  "UnidadMedida": "ml",
  "Familia": "Eva Visnú",
  "PrecioProfesional": 32.95,
  "Estado": 0,
  "Grupo": "COS",
  "Subgrupo": "Aceites, fluidos y geles profesionales",
  "UrlFoto": "https://www.productosdeesteticaypeluqueriaprofesional.com/102148-home_default/acido-hialuronico-ricchezza-100ml.jpg",
  "CodigoBarras": "8437005358942"
}
```

## Verificación de Configuración

### ✅ Transformer existe y está bien configurado

**Archivo**: `transformers/unidad_medida_transformer.py`

La clase `UnidadMedidaConfig` tiene `ml` configurado correctamente:

```python
VOLUMEN_UNITS = {
    'l': {'factor': 0.001, 'uom_search': ['l', 'liter', 'litro']},
    'ml': {'factor': 0.000001, 'uom_search': ['ml', 'milliliter', 'mililitro']},  # ← Correcto
    'cl': {'factor': 0.00001, 'uom_search': ['cl', 'centiliter', 'centilitro']},
    ...
}
```

La función `transform_unidad_medida_y_tamanno` procesa correctamente:

```python
def transform_unidad_medida_y_tamanno(env, nesto_data):
    tamanno = nesto_data.get('Tamanno')  # → 100
    unidad_medida_str = nesto_data.get('UnidadMedida')  # → "ml"

    unit_type, conversion_factor = UnidadMedidaConfig.get_unit_type(unidad_medida_str)
    # unit_type = 'volume', conversion_factor = 0.000001

    valor_convertido = float(tamanno) * conversion_factor
    # valor_convertido = 100 × 0.000001 = 0.0001

    if unit_type == 'volume':
        result['volume'] = valor_convertido  # → 0.0001
        _logger.info(f"Tamanno {tamanno} {unidad_medida_str} → volume = {valor_convertido} m³")

    return result
```

### ✅ Entity configs correcto

**Archivo**: `config/entity_configs.py`

```python
'producto': {
    'field_mappings': {
        'Tamanno': {
            'transformer': 'unidad_medida_y_tamanno',  # ← Correcto
            'odoo_fields': ['weight', 'volume', 'product_length', 'uom_id', 'uom_po_id']
        },
        ...
    }
}
```

### ✅ Transformer registrado

**Archivo**: `transformers/field_transformers.py`

```python
@FieldTransformerRegistry.register('unidad_medida_y_tamanno')
class UnidadMedidaYTamannoTransformer:
    def transform(self, value, context):
        from ..transformers.unidad_medida_transformer import transform_unidad_medida_y_tamanno

        env = context.get('env')
        nesto_data = context.get('nesto_data', {})  # ← Recibe nesto_data completo

        return transform_unidad_medida_y_tamanno(env, nesto_data)
```

## Posibles Causas del Bug

### 1. ❓ El transformer no se está ejecutando

**Cómo verificar**:
```bash
# Sincronizar producto 35894 y revisar logs
sudo journalctl -u odoo16 -f | grep -E "Tamanno|UnidadMedida|volume"
```

**Logs esperados**:
```
INFO ... Tamanno 100 ml → volume = 0.0001 m³
INFO ... UnidadMedida 'ml' → uom_id = X
```

**Si no aparecen estos logs**: El transformer no se está ejecutando.

**Posibles razones**:
- Cache de Python antiguo (necesita limpiar `__pycache__`)
- Módulo no actualizado en Odoo (necesita `-u nesto_sync`)

### 2. ❓ El transformer recibe valores incorrectos

**Cómo verificar**:
Añadir log temporal en `transformers/unidad_medida_transformer.py` línea 119:

```python
def transform_unidad_medida_y_tamanno(env, nesto_data):
    result = {}

    # Obtener valores del mensaje
    tamanno = nesto_data.get('Tamanno')
    unidad_medida_str = nesto_data.get('UnidadMedida')

    # ⭐ LOG TEMPORAL PARA DEBUG
    _logger.info(f"🔍 DEBUG transform_unidad_medida_y_tamanno: Tamanno={tamanno}, UnidadMedida={unidad_medida_str}, nesto_data keys={list(nesto_data.keys())}")
    # ⭐ FIN LOG TEMPORAL

    if not tamanno or tamanno == 0:
        _logger.debug("No hay Tamanno o es 0, no se mapean dimensiones")
        return result
```

**Logs esperados**:
```
INFO ... 🔍 DEBUG transform_unidad_medida_y_tamanno: Tamanno=100, UnidadMedida=ml, nesto_data keys=['Producto', 'Nombre', 'Tamanno', 'UnidadMedida', ...]
```

**Si Tamanno o UnidadMedida son None**: El problema está en cómo se pasa `nesto_data` al transformer.

### 3. ❓ El transformer calcula correctamente pero el valor no se guarda

**Cómo verificar**:
Añadir log en `core/generic_service.py` método `_create_record` y `_update_record`:

```python
def _create_record(self, values):
    try:
        # ⭐ LOG TEMPORAL
        _logger.info(f"🔍 DEBUG _create_record para {self.config['odoo_model']}: values={values}")
        # ⭐ FIN LOG

        record = self.model.sudo().with_context(skip_sync=True).create(values)
```

**Logs esperados**:
```
INFO ... 🔍 DEBUG _create_record para product.template: values={'name': 'ACIDO...', 'volume': 0.0001, ...}
```

**Si `volume` no aparece en values**: El transformer no está retornando el valor correctamente.

**Si `volume` aparece con valor 0.0001 pero en BD es 0.00**: Problema en el `write` de Odoo (permisos, validaciones, etc.).

### 4. ❓ Problema de precisión en el campo float

**Cómo verificar**:
```sql
-- Conectar a BD
sudo -u postgres psql odoo16

-- Ver definición del campo volume
\d product_template

-- Ver valor exacto
SELECT producto_externo, volume FROM product_template WHERE producto_externo = '35894';
```

**Si el campo `volume` no existe o tiene tipo incorrecto**: El módulo `product_dimension` no está instalado o tiene conflictos.

## Pasos para Debugging

### Paso 1: Verificar que el transformer se ejecuta

```bash
# 1. Limpiar cache
cd /opt/odoo16/custom_addons/nesto_sync
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 2. Actualizar módulo
python3 /opt/odoo16/odoo-bin -c /opt/odoo16/odoo.conf -d odoo16 -u nesto_sync --stop-after-init

# 3. Reiniciar Odoo
sudo systemctl restart odoo16

# 4. Monitorear logs
sudo journalctl -u odoo16 -f
```

### Paso 2: Sincronizar producto de prueba

Desde NestoAPI o via curl, enviar el mensaje JSON del producto 35894.

### Paso 3: Revisar logs

**Buscar mensajes clave**:
```bash
sudo journalctl -u odoo16 --since "5 minutes ago" | grep -E "35894|Tamanno|UnidadMedida|volume"
```

**Logs esperados (si funciona correctamente)**:
```
INFO ... Procesando mensaje de tipo producto
INFO ... Tamanno 100 ml → volume = 0.0001 m³
INFO ... UnidadMedida 'ml' → uom_id = X
INFO ... product.template creado con ID: XXX
```

### Paso 4: Verificar en base de datos

```sql
sudo -u postgres psql odoo16 -c "SELECT producto_externo, name, volume, weight, product_length FROM product_template WHERE producto_externo = '35894';"
```

**Output esperado**:
```
 producto_externo |           name            | volume  | weight | product_length
------------------+---------------------------+---------+--------+----------------
 35894            | ACIDO HIALURONICO...      | 0.0001  |        |
```

### Paso 5: Si sigue fallando, añadir logs temporales

**Archivo**: `transformers/unidad_medida_transformer.py`

Añadir logs en la función `transform_unidad_medida_y_tamanno`:

```python
def transform_unidad_medida_y_tamanno(env, nesto_data):
    _logger.info(f"⭐ INICIO transform_unidad_medida_y_tamanno")
    _logger.info(f"⭐ nesto_data keys: {list(nesto_data.keys())}")

    result = {}
    tamanno = nesto_data.get('Tamanno')
    unidad_medida_str = nesto_data.get('UnidadMedida')

    _logger.info(f"⭐ Tamanno obtenido: {tamanno} (tipo: {type(tamanno)})")
    _logger.info(f"⭐ UnidadMedida obtenido: {unidad_medida_str} (tipo: {type(unidad_medida_str)})")

    if not tamanno or tamanno == 0:
        _logger.warning(f"⭐ SALIDA TEMPRANA: Tamanno es {tamanno}")
        return result

    if not unidad_medida_str:
        _logger.warning(f"⭐ SALIDA TEMPRANA: UnidadMedida es {unidad_medida_str}")
        return result

    unit_type, conversion_factor = UnidadMedidaConfig.get_unit_type(unidad_medida_str)
    _logger.info(f"⭐ Tipo detectado: {unit_type}, factor: {conversion_factor}")

    if not unit_type:
        _logger.warning(f"⭐ SALIDA TEMPRANA: Tipo no reconocido para '{unidad_medida_str}'")
        return result

    tamanno_float = float(tamanno) if tamanno else 0.0
    valor_convertido = tamanno_float * conversion_factor
    _logger.info(f"⭐ Conversión: {tamanno_float} × {conversion_factor} = {valor_convertido}")

    if unit_type == 'volume':
        result['volume'] = valor_convertido
        _logger.info(f"⭐ Asignando result['volume'] = {valor_convertido}")

    _logger.info(f"⭐ FIN transform_unidad_medida_y_tamanno, retornando: {result}")
    return result
```

Luego repetir pasos 1-4.

## Verificación Final

Una vez que funcione, deberías ver:

1. **En logs**:
```
INFO ... Tamanno 100 ml → volume = 0.0001 m³
```

2. **En Odoo UI**:
- Producto 35894
- Volumen: 0.0001 m³ (o 0.10 l en vista de usuario)

3. **En base de datos**:
```sql
SELECT volume FROM product_template WHERE producto_externo = '35894';
-- volume | 0.0001
```

## Notas Adicionales

### Diferencia entre volume en m³ y visualización

Odoo almacena `volume` en m³ (metros cúbicos) pero puede mostrar en otras unidades en la UI.

- 100ml = 0.0001 m³
- 1l = 0.001 m³
- 1000l = 1 m³

### Campo precision

El campo `volume` en Odoo tiene precisión decimal. Verificar que no esté redondeando a 0:

```python
# En product.py
volume = fields.Float('Volume', digits=(12, 6))  # 6 decimales
```

Si tiene menos de 4 decimales, valores como 0.0001 podrían redondearse a 0.00.

---

**Fecha**: 2025-11-17
**Estado**: Pendiente debugging en entorno Odoo real
**Próximo paso**: Sincronizar producto 35894 y revisar logs con flags de debug
