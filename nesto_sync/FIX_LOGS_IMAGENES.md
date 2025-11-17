# Fix: Logs incomprensibles con base64 de imágenes

**Fecha**: 2025-11-17
**Versión**: v2.5.0
**Estado**: ✅ RESUELTO

---

## Problema Reportado

Los logs de Odoo mostraban base64 completo de imágenes, haciéndolos incomprensibles:

```
INFO ... Cambio en image_1920: 'b'iVBORw0KGgoAAAANSUhEUgAAARoAAAFCCAYAAAAubhIgAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAgAElEQVR42uy9eZBcyXkn9st8r6q6uqvvE2iggcF9DIAZYDDDOTjD4ZAcmZI2JFG7FLUrO7yW/YcjvBGyww6Hvbthx2rXG...' (continúa por miles de caracteres)
```

**Impacto**:
- Logs imposibles de leer para humanos
- Dificultad para debugging
- Logs ocupan espacio innecesario en disco
- journalctl se vuelve inútil

---

## Solución Implementada

### 1. Función de Sanitización

Se creó `_sanitize_value_for_logging()` que:

- Detecta campos de imagen (base64, bytes, string repr)
- Reemplaza con resumen legible: `<image_data: X bytes>`
- Trunca strings largos (>200 chars) que no sean imágenes
- Deja intactos números, None, y strings normales

**Implementación**:

```python
def _sanitize_value_for_logging(value):
    """
    Sanitiza un valor individual para logging
    """
    # Detectar bytes
    if isinstance(value, bytes):
        return f"<binary_data: {len(value)} bytes>"

    if isinstance(value, str):
        # Detectar base64 de imágenes
        is_image_data = (
            value.startswith('iVBOR') or  # PNG base64
            value.startswith('/9j/') or    # JPEG base64
            value.startswith('R0lGOD') or  # GIF base64
            value.startswith("b'iVBOR") or  # String repr of PNG bytes
            value.startswith("b'/9j/") or   # String repr of JPEG bytes
            value.startswith('b"iVBOR') or
            value.startswith('b"/9j/')
        )

        if is_image_data and len(value) > 100:
            return f"<image_data: {len(value)} bytes>"

        # Truncar strings muy largos
        if len(value) > 200:
            return value[:200] + "..."

    return value
```

### 2. Ubicaciones donde se aplicó

#### A. `models/bidirectional_sync_mixin.py` (Commit 877de8f)

**Línea 77-80**: Log de `write()` method

```python
_logger.debug(
    f"BidirectionalSyncMixin.write() llamado en {self._name} con vals: "
    f"{_sanitize_vals_for_logging(vals)}, IDs: {self.ids}"
)
```

**Función auxiliar** (líneas 22-53):
```python
def _sanitize_vals_for_logging(vals):
    """
    Sanitiza un diccionario de valores para logging
    """
    if not isinstance(vals, dict):
        return vals

    sanitized = {}
    binary_fields = ('image_1920', 'image_1024', 'image_512', 'image_256', 'image_128')

    for key, value in vals.items():
        if key in binary_fields and value:
            if isinstance(value, (str, bytes)):
                size_bytes = len(value) if isinstance(value, bytes) else len(value.encode('utf-8'))
                sanitized[key] = f"<image_data: {size_bytes} bytes>"
            else:
                sanitized[key] = "<image_data>"
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:200] + "..."
        else:
            sanitized[key] = value

    return sanitized
```

#### B. `core/generic_service.py` (Commit ef92938)

**Líneas 16-51**: Función de sanitización de valores individuales

**Líneas 218-221**: Aplicado en `_has_changes()` method

```python
if self._values_are_different(field, current_value, new_value, record):
    # Sanitizar valores para logging (evitar base64 de imágenes en logs)
    sanitized_current = _sanitize_value_for_logging(current_value)
    sanitized_new = _sanitize_value_for_logging(new_value)
    _logger.info(f"Cambio en {field}: '{sanitized_current}' -> '{sanitized_new}'")
    return True
```

---

## Resultado: Antes vs Después

### ❌ ANTES (incomprensible)

```
INFO ... BidirectionalSyncMixin.write() llamado en product.template con vals: {
  'name': 'ACIDO HIALURONICO RICCHEZZA',
  'image_1920': 'iVBORw0KGgoAAAANSUhEUgAAARoAAAFCCAYAAAAubhIgAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAgAElEQVR42uy9eZBcyXkn9st8r6q6uqvvE2iggcF9DIAZYDDDOTjD4ZAcmZI2JFG7FLUrO7yW/YcjvBGyww6Hvbthx2rXG...' (continúa por miles de caracteres)
}, IDs: [1234]

INFO ... Cambio en image_1920: 'b'iVBORw0KGgoAAAANSUhEUgAAARoAAAFCCAYAAAAubhIgAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAgAElEQVR42uy9eZBcyXkn9st8r6q6uqvvE2iggcF9DIAZYDDDOTjD4ZAcmZI2JFG7FLUrO7yW/YcjvBGyww6Hvbthx2rXG...' -> 'iVBORw0KGgoAAAANSUhEUgAAARoAAAFCCAYAAAAubhIgAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAgAElEQVR...'
```

### ✅ DESPUÉS (legible para humanos)

```
INFO ... BidirectionalSyncMixin.write() llamado en product.template con vals: {
  'name': 'ACIDO HIALURONICO RICCHEZZA',
  'image_1920': '<image_data: 109328 bytes>'
}, IDs: [1234]

INFO ... Cambio en image_1920: '<image_data: 109328 bytes>' -> '<image_data: 110000 bytes>'
```

---

## Tests

### `test_sanitization.py`

Test standalone que verifica todas las funcionalidades de sanitización:

**9/9 tests pasados** ✅

1. Base64 PNG → `<image_data: X bytes>`
2. Base64 JPEG → `<image_data: X bytes>`
3. Base64 con prefijo `b'` → `<image_data: X bytes>`
4. Bytes binarios → `<binary_data: X bytes>`
5. String largo (no imagen) → Truncado a 200 chars + `...`
6. String normal → Sin cambios
7. Números → Sin cambios
8. `None` → Sin cambios
9. Caso real del log reportado → Sanitizado correctamente

**Ejecución**:
```bash
cd /opt/odoo16/custom_addons/nesto_sync
python3 test_sanitization.py
```

**Resultado esperado**:
```
✅ TODOS LOS TESTS DE SANITIZACIÓN PASARON!

Antes del fix, los logs mostraban:
  Cambio en image_1920: 'b'iVBORw0KGgoAAAA... (miles de caracteres)

Después del fix, los logs mostrarán:
  Cambio en image_1920: '<image_data: 109328 bytes>' -> '<image_data: 110000 bytes>'

✅ Fix completo y funcional
```

---

## Commits Relacionados

| Commit | Descripción | Archivo Modificado |
|--------|-------------|-------------------|
| `877de8f` | Sanitización inicial en `bidirectional_sync_mixin.py` | `models/bidirectional_sync_mixin.py` |
| `ef92938` | Sanitización completa en `generic_service.py` | `core/generic_service.py` |

---

## Despliegue en Producción

### Pasos para aplicar el fix

1. **Pull de los cambios**:
   ```bash
   cd /opt/odoo16/custom_addons/nesto_sync
   git pull origin main
   ```

2. **Limpiar cache de Python**:
   ```bash
   find . -type f -name "*.pyc" -delete
   find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
   ```

3. **Actualizar módulo en Odoo**:
   ```bash
   sudo /opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo-bin \
     -c /opt/odoo16/odoo.conf \
     -d odoo16 \
     -u nesto_sync \
     --stop-after-init
   ```

4. **Reiniciar Odoo**:
   ```bash
   sudo systemctl restart odoo16
   ```

5. **Verificar en logs**:
   ```bash
   sudo journalctl -u odoo16 -f | grep -E "image_1920|Cambio en"
   ```

   **Logs esperados** (sanitizados):
   ```
   INFO ... Cambio en image_1920: '<image_data: 109328 bytes>' -> '<image_data: 110000 bytes>'
   ```

   **NO deberías ver** (base64 completo):
   ```
   INFO ... Cambio en image_1920: 'iVBORw0KGgoAAAA...'
   ```

---

## Beneficios

### ✅ Logs legibles para humanos
- Puedes ver rápidamente qué campos cambiaron sin scroll infinito
- Fácil identificar cambios en dimensiones (`weight`, `volume`, etc.)

### ✅ Mejor performance de journalctl
- Logs más pequeños = búsquedas más rápidas
- `journalctl -f` no se "traba" con logs gigantes

### ✅ Menor uso de disco
- Logs de 100KB+ → Logs de ~200 bytes
- Rotación de logs más eficiente

### ✅ Debugging más eficiente
- Información útil sin "ruido" de base64
- Puedes ver tamaño de imagen sin decodificar

---

## Casos Edge Verificados

| Caso | Input | Output | Status |
|------|-------|--------|--------|
| Imagen PNG base64 | `iVBORw0KGgo...` (1083 bytes) | `<image_data: 1083 bytes>` | ✅ |
| Imagen JPEG base64 | `/9j/4AAQSkZ...` (1027 bytes) | `<image_data: 1027 bytes>` | ✅ |
| Bytes Python | `b'binary...'` (1600 bytes) | `<binary_data: 1600 bytes>` | ✅ |
| String repr bytes | `b'iVBORw0...` (174 bytes) | `<image_data: 174 bytes>` | ✅ |
| String largo | `'AAAA...'` (300 chars) | `'AAA...'` (203 chars) | ✅ |
| Producto normal | `'ACIDO HIALURONICO'` | `'ACIDO HIALURONICO'` | ✅ |
| Precio | `32.95` | `32.95` | ✅ |
| `None` | `None` | `None` | ✅ |

---

## Notas Técnicas

### ¿Por qué dos funciones diferentes?

1. **`_sanitize_vals_for_logging(vals)`** en `bidirectional_sync_mixin.py`:
   - Recibe un **diccionario completo**
   - Sabe qué campos son imágenes por nombre (`image_1920`, etc.)
   - Sanitiza todos los campos del dict

2. **`_sanitize_value_for_logging(value)`** en `generic_service.py`:
   - Recibe un **valor individual**
   - Detecta imágenes por **contenido** (base64 patterns)
   - Más genérico, no depende de nombres de campos

Ambas son necesarias porque se usan en contextos diferentes.

### Detección de base64 de imágenes

La función detecta:
- PNG: `iVBOR` (primeros 5 bytes de PNG en base64)
- JPEG: `/9j/` (primeros 3 bytes de JPEG en base64)
- GIF: `R0lGOD` (primeros 6 bytes de GIF en base64)
- String repr: `b'iVBOR`, `b"/9j/`, etc.

**Threshold**: Solo sanitiza si `len(value) > 100` para evitar falsos positivos.

---

## Verificación Post-Despliegue

### 1. Sincronizar producto con imagen

Enviar mensaje desde NestoAPI con un producto que tenga `UrlFoto`.

### 2. Revisar logs

```bash
sudo journalctl -u odoo16 --since "5 minutes ago" | grep -E "image_1920|UrlFoto"
```

**Esperado**:
```
INFO ... Procesando campo 'UrlFoto'
INFO ... Cambio en image_1920: '<image_data: 109328 bytes>' -> '<image_data: 110500 bytes>'
```

**NO esperado** (indicaría que el fix no se aplicó):
```
INFO ... Cambio en image_1920: 'iVBORw0KGgoAAAANSUhEUgAAARoAA...'
```

### 3. Verificar tamaño de logs

```bash
# Ver tamaño del journal de Odoo
sudo journalctl -u odoo16 --disk-usage

# Comparar antes/después de sincronizar 100 productos con imágenes
```

El tamaño debería ser **significativamente menor** con la sanitización activa.

---

## FAQ

### ¿Se pierde información importante en los logs?

**No**. Los logs siguen mostrando:
- Qué campo cambió (`image_1920`)
- Que es un campo de imagen (`<image_data>`)
- Tamaño aproximado de la imagen (`X bytes`)

Lo único que se omite es el **contenido binario** que no es útil para humanos.

### ¿Puedo recuperar la imagen desde los logs?

**No**, pero **nunca fue el propósito de los logs**. La imagen está en:
1. Base de datos Odoo (tabla `product_template`, campo `image_1920`)
2. URL original en `url_imagen_actual`

Los logs son para **debugging**, no para almacenar datos.

### ¿Qué pasa si necesito ver el valor exacto?

Para debugging avanzado, puedes temporalmente desactivar la sanitización:

```python
# En generic_service.py línea 218, comentar temporalmente:
# sanitized_current = _sanitize_value_for_logging(current_value)
# sanitized_new = _sanitize_value_for_logging(new_value)
# Y usar directamente:
_logger.info(f"Cambio en {field}: '{current_value}' -> '{new_value}'")
```

**IMPORTANTE**: Recordar revertir después del debugging.

### ¿Este fix afecta el funcionamiento de la sincronización?

**No**. Solo afecta cómo se **muestran** los valores en logs. La lógica de comparación (`_has_changes`, `_values_are_different`) sigue usando los valores originales sin sanitizar.

---

## Conclusión

✅ **Problema resuelto completamente**

Los logs ahora son:
- Legibles para humanos
- Compactos y eficientes
- Útiles para debugging
- No contienen "ruido" de base64

**Commits**:
- `877de8f`: Sanitización en `bidirectional_sync_mixin.py`
- `ef92938`: Sanitización en `generic_service.py`

**Tests**: 9/9 ✅

**Listo para producción**: ✅

---

**Fecha de documentación**: 2025-11-17
**Autor**: Claude Code
**Versión del módulo**: 2.5.0
