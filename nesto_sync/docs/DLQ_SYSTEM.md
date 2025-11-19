# Sistema Dead Letter Queue (DLQ)

**Versión:** 2.7.0
**Fecha:** 2025-11-19

## Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Problema que Resuelve](#problema-que-resuelve)
3. [Arquitectura](#arquitectura)
4. [Componentes](#componentes)
5. [Flujo de Funcionamiento](#flujo-de-funcionamiento)
6. [Configuración](#configuración)
7. [Uso desde Odoo UI](#uso-desde-odoo-ui)
8. [Casos de Uso](#casos-de-uso)
9. [Troubleshooting](#troubleshooting)

---

## Resumen Ejecutivo

El sistema **Dead Letter Queue (DLQ)** evita bucles infinitos de reintentos cuando Google Pub/Sub envía mensajes que el módulo `nesto_sync` no puede procesar.

**Funcionamiento básico:**
1. Un mensaje falla al procesarse
2. Se reintenta automáticamente hasta 3 veces
3. Después de 3 reintentos, se mueve a la "cola de mensajes fallidos" (DLQ)
4. El mensaje se almacena con toda la información del error
5. Se devuelve HTTP 200 (ACK) a Pub/Sub para que deje de reintentarlo
6. Un administrador puede revisar y reprocesar manualmente desde Odoo

---

## Problema que Resuelve

### Antes del DLQ (v2.6.0 y anteriores)

Cuando un mensaje de Nesto no se podía procesar (por ejemplo, código de barras duplicado), ocurría:

```
2025-11-19 10:00:01 ERROR: ValidationError: El código de barras '8412345678901' ya existe
2025-11-19 10:00:05 ERROR: ValidationError: El código de barras '8412345678901' ya existe
2025-11-19 10:00:10 ERROR: ValidationError: El código de barras '8412345678901' ya existe
... (infinitamente)
```

**Problemas:**
- Logs ilegibles con miles de líneas repetidas
- Consumo innecesario de recursos (CPU, red, base de datos)
- Difícil identificar problemas reales entre tanto ruido
- Mensajes importantes quedan "atascados" detrás del problema

### Después del DLQ (v2.7.0)

```
2025-11-19 10:00:01 ERROR [msg-001]: ValidationError: El código de barras '8412345678901' ya existe
2025-11-19 10:00:05 INFO  [msg-001]: Reintento 1 de 3
2025-11-19 10:00:10 INFO  [msg-001]: Reintento 2 de 3
2025-11-19 10:00:15 INFO  [msg-001]: Reintento 3 de 3
2025-11-19 10:00:20 ERROR [msg-001]: Error persistente después de 4 intentos. Moviendo a DLQ.
```

**Ventajas:**
- El mensaje se mueve a DLQ y se hace ACK (Pub/Sub deja de enviarlo)
- Logs limpios y legibles
- Toda la información del error se guarda en Odoo para análisis
- Administrador puede revisar y resolver manualmente

---

## Arquitectura

```
┌─────────────────────┐
│   Google Pub/Sub    │
│   (Nesto envía)     │
└──────────┬──────────┘
           │ POST /nesto_sync
           │ messageId: abc123
           ▼
┌─────────────────────────────────────────┐
│          Controller                      │
│  (/nesto_sync endpoint)                 │
│                                         │
│  1. Extrae messageId                    │
│  2. Procesa mensaje                     │
│  3. Si error → _handle_retry()          │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│   nesto.sync.message.retry              │
│   (Tracking temporal de reintentos)     │
│                                         │
│  - increment_retry()                    │
│  - Retorna: {retry_count, should_dlq}   │
└──────────┬──────────────────────────────┘
           │
           │ retry_count <= 3?
           ├─ YES → HTTP 500 (NACK - reintentar)
           │
           └─ NO → _move_to_dlq()
                   │
                   ▼
           ┌─────────────────────────────────┐
           │  nesto.sync.failed.message      │
           │  (DLQ - Almacenamiento          │
           │   persistente)                  │
           │                                 │
           │  - message_id                   │
           │  - raw_data                     │
           │  - error_message                │
           │  - error_traceback              │
           │  - retry_count                  │
           │  - state: failed/resolved       │
           └─────────────────────────────────┘
                   │
                   └─→ HTTP 200 (ACK - no reintentar)
```

---

## Componentes

### 1. Modelo: `nesto.sync.message.retry`

**Propósito:** Tracking temporal de reintentos por messageId
**Archivo:** `models/message_retry.py`

**Campos principales:**
- `message_id`: ID único del mensaje de Pub/Sub
- `retry_count`: Número de reintentos realizados
- `last_error`: Último mensaje de error
- `entity_type`: Tipo de entidad (cliente, producto, etc.)
- `moved_to_dlq`: Si ya fue movido a DLQ

**Métodos clave:**
```python
increment_retry(message_id, error_message, entity_type)
# Retorna: {'retry_count': N, 'should_move_to_dlq': True/False}

mark_success(message_id)
# Elimina el registro cuando el mensaje se procesa exitosamente

mark_moved_to_dlq(message_id)
# Marca el mensaje como movido a DLQ

cleanup_old_records()
# Elimina registros > 7 días (ejecutado por cron)
```

**Configuración:**
```python
MAX_RETRIES = 3       # Límite de reintentos antes de DLQ
CLEANUP_DAYS = 7      # Días para mantener registros antiguos
```

---

### 2. Modelo: `nesto.sync.failed.message`

**Propósito:** Almacenamiento persistente de mensajes que fallaron
**Archivo:** `models/failed_message.py`

**Campos principales:**
- `message_id`: ID único del mensaje
- `raw_data`: Datos crudos del mensaje (JSON completo de Pub/Sub)
- `entity_type`: Tipo de entidad
- `error_message`: Mensaje de error
- `error_traceback`: Stack trace completo
- `retry_count`: Número de reintentos realizados
- `state`: failed / resolved / reprocessing / permanently_failed
- `first_attempt_date`: Fecha del primer intento
- `last_attempt_date`: Fecha del último intento
- `resolution_notes`: Notas sobre la resolución (si aplica)
- `resolved_by`: Usuario que resolvió (si aplica)
- `resolved_date`: Fecha de resolución (si aplica)

**Métodos:**
```python
action_reprocess()
# Botón para reprocesar mensaje (TODO: implementar lógica automática)

action_mark_managed()
# Abre wizard para marcar como resuelto o fallo permanente
```

**Estados:**
- `failed`: Mensaje fallido pendiente de revisión
- `reprocessing`: En proceso de reprocesamiento
- `resolved`: Resuelto exitosamente
- `permanently_failed`: Error irresoluble (ej: datos inválidos de Nesto)

---

### 3. Wizard: `nesto.sync.failed.message.wizard`

**Propósito:** Interfaz para marcar mensajes como resueltos/fallidos
**Archivo:** `wizards/failed_message_wizard.py`

**Acciones:**
- **Marcar como Resuelto:** Problema solucionado (ej: se corrigió el dato en Nesto)
- **Marcar como Fallo Permanente:** Error irresoluble (ej: dato malformado)

**Requiere:**
- `resolution_notes`: Campo obligatorio para documentar la decisión

---

### 4. Controller: Lógica de Reintentos

**Archivo:** `controllers/controllers.py`

**Método principal:** `_handle_retry()`

```python
def _handle_retry(self, message_id, raw_data, error_message, error_traceback, entity_type):
    """
    Maneja el sistema de reintentos y DLQ

    Returns:
        dict con keys:
            - retry_count: Número de reintentos
            - should_move_to_dlq: Si se debe mover a DLQ
    """
    MessageRetry = request.env['nesto.sync.message.retry'].sudo()

    # Incrementar contador
    retry_info = MessageRetry.increment_retry(
        message_id=message_id,
        error_message=error_message,
        entity_type=entity_type
    )

    # Si debe moverse a DLQ
    if retry_info['should_move_to_dlq']:
        self._move_to_dlq(...)
        MessageRetry.mark_moved_to_dlq(message_id)

    return retry_info
```

**Tipos de excepciones manejadas:**

1. **`RequirePrincipalClientError`**: Cliente principal no existe
   - Comportamiento: Reintentar (el principal puede llegar después)

2. **`ValueError`**: Errores de validación
   - Comportamiento: Reintentar (puede ser temporal)

3. **`Exception`**: Errores inesperados
   - Comportamiento: Reintentar

---

### 5. Cron Job: Limpieza Automática

**Archivo:** `data/cron_jobs.xml`

**Función:** Limpia registros de `nesto.sync.message.retry` > 7 días

```xml
<record id="ir_cron_cleanup_retry_records" model="ir.cron">
    <field name="name">Nesto Sync: Limpiar registros de reintentos antiguos</field>
    <field name="model_id" ref="model_nesto_sync_message_retry"/>
    <field name="code">model.cleanup_old_records()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
</record>
```

**Ejecución:** Diaria (1 vez por día)

---

## Flujo de Funcionamiento

### Caso 1: Mensaje Procesado Exitosamente

```
1. Pub/Sub envía mensaje (messageId: abc123)
2. Controller procesa → ÉXITO
3. _mark_message_success(abc123)
4. Elimina registro de retry (si existía)
5. HTTP 200 → ACK
```

### Caso 2: Mensaje Falla pero se Recupera

```
1. Pub/Sub envía mensaje (messageId: xyz789)
2. Controller procesa → ERROR (cliente principal no existe)
3. increment_retry(xyz789) → retry_count=1, should_dlq=False
4. HTTP 500 → NACK (Pub/Sub lo reintentará)
5. ... (algunos segundos después) ...
6. Pub/Sub reenvía mensaje
7. Controller procesa → ÉXITO (cliente principal ya existe)
8. _mark_message_success(xyz789)
9. HTTP 200 → ACK
```

### Caso 3: Mensaje Falla Persistentemente

```
1. Pub/Sub envía mensaje (messageId: err001)
2. Controller procesa → ERROR (código de barras duplicado)
3. increment_retry(err001) → retry_count=1, should_dlq=False
4. HTTP 500 → NACK

5. Pub/Sub reenvía → ERROR
6. increment_retry(err001) → retry_count=2, should_dlq=False
7. HTTP 500 → NACK

8. Pub/Sub reenvía → ERROR
9. increment_retry(err001) → retry_count=3, should_dlq=False
10. HTTP 500 → NACK

11. Pub/Sub reenvía → ERROR
12. increment_retry(err001) → retry_count=4, should_dlq=TRUE
13. _move_to_dlq(err001) → Crea registro en nesto.sync.failed.message
14. HTTP 200 → ACK (Pub/Sub deja de reintentar)

15. Administrador revisa en Odoo → menú "Dead Letter Queue"
16. Ve el error, corrige el problema en Nesto
17. Marca como "Resuelto" con notas
```

---

## Configuración

### Cambiar el Límite de Reintentos

Editar `models/message_retry.py`:

```python
class NestoSyncMessageRetry(models.Model):
    _name = 'nesto.sync.message.retry'

    MAX_RETRIES = 5  # Cambiar de 3 a 5 reintentos
```

**Nota:** Reiniciar Odoo después del cambio.

### Cambiar el Período de Limpieza

Editar `models/message_retry.py`:

```python
CLEANUP_DAYS = 14  # Cambiar de 7 a 14 días
```

### Desactivar la Limpieza Automática

Desde Odoo UI:
1. Ir a **Configuración → Técnico → Automatización → Acciones Programadas**
2. Buscar "Nesto Sync: Limpiar registros de reintentos antiguos"
3. Desmarcar "Activo"

---

## Uso desde Odoo UI

### Acceder al DLQ

**Menú:** `Nesto Sync → Dead Letter Queue → Mensajes Fallidos`

### Vista de Lista

Muestra todos los mensajes fallidos con:
- **Message ID**: ID único del mensaje de Pub/Sub
- **Tipo de Entidad**: cliente, producto, etc.
- **Error**: Resumen del error
- **Reintentos**: Número de intentos realizados
- **Estado**: failed, resolved, permanently_failed
- **Fecha**: Cuándo ocurrió el primer error

**Colores:**
- 🔴 Rojo: Estado "failed" (pendiente de revisión)
- 🟢 Verde: Estado "resolved" (solucionado)

### Vista de Formulario

Al abrir un mensaje fallido, se ven 4 pestañas:

#### 1. Pestaña "Error"
- Mensaje de error
- Tipo de entidad
- Número de reintentos
- Fechas (primer intento, último intento)

#### 2. Pestaña "Stack Trace"
- Traceback completo del error
- Útil para debugging

#### 3. Pestaña "Datos Crudos"
- JSON completo del mensaje de Pub/Sub
- Útil para reprocesamiento manual

#### 4. Pestaña "Resolución"
- Notas de resolución
- Usuario que resolvió
- Fecha de resolución

### Acciones Disponibles

#### Botón "Reprocesar"
Reintenta procesar el mensaje automáticamente.

**Estado actual:** Muestra mensaje informativo (implementación automática pendiente)

**Workaround manual:**
1. Copiar el JSON de "Datos Crudos"
2. Corregir el problema en Nesto (o en Odoo si aplica)
3. Enviar el mensaje corregido a `/nesto_sync` manualmente

#### Botón "Fallo Permanente"
Abre wizard para marcar el mensaje como fallo permanente o resuelto.

**Casos de uso:**
- **Fallo Permanente:** Datos inválidos de Nesto que no se pueden corregir
- **Resuelto:** Se corrigió el problema y se procesó manualmente

**Requiere:** Notas obligatorias explicando la decisión

---

## Casos de Uso

### Caso 1: Código de Barras Duplicado

**Escenario:**
Nesto envía un producto con código de barras que ya existe en Odoo.

**Error en DLQ:**
```
ValidationError: El código de barras '8412345678901' ya existe en el sistema
```

**Solución:**
1. Revisar en Odoo qué producto tiene ese código de barras
2. Opciones:
   - **A)** Cambiar el código de barras del producto duplicado en Nesto
   - **B)** Si es el mismo producto, ignorar (marcar como resuelto)
   - **C)** Si Odoo tiene el código equivocado, corregirlo y reprocesar

3. Marcar mensaje como:
   - **Resuelto** si se corrigió y procesó
   - **Fallo Permanente** si es un error de datos en Nesto

### Caso 2: Cliente Principal No Existe

**Escenario:**
Llega un cliente secundario (persona de contacto) antes que el principal.

**Error en DLQ:**
```
RequirePrincipalClientError: No se encontró cliente principal con cliente_externo='CLI-001'
```

**Comportamiento esperado:**
- El sistema **debería** reintentar automáticamente
- Normalmente el cliente principal llega en los siguientes segundos
- Solo llega a DLQ si después de 3 reintentos sigue sin existir

**Solución:**
1. Verificar si el cliente principal existe ahora en Odoo
2. Si existe: Reprocesar el mensaje (se creará la persona de contacto)
3. Si NO existe: Revisar en Nesto por qué no se envió el cliente principal

### Caso 3: Datos Malformados

**Escenario:**
Nesto envía un mensaje con campos requeridos faltantes.

**Error en DLQ:**
```
ValueError: Campo 'Nombre' requerido pero no presente en el mensaje
```

**Solución:**
1. Revisar los "Datos Crudos" del mensaje
2. Confirmar que efectivamente falta el campo
3. Reportar a Nesto (es un bug de su lado)
4. Marcar como **Fallo Permanente** con notas explicando el problema

### Caso 4: Error de Producto con UoM Faltante

**Escenario:**
Producto con UnidadMedida='ml' pero la UoM no existe en Odoo.

**Error en logs (warning, no llega a DLQ):**
```
WARNING: No se encontró UoM en Odoo para 'ml'. Se deja uom_id sin mapear.
```

**Solución:**
1. Crear la UoM faltante en Odoo (como hicimos hoy)
2. Reprocesar los productos afectados (si es necesario)

**Nota:** Este error NO mueve a DLQ porque es solo un warning, el producto se crea igual.

---

## Troubleshooting

### Problema: Mensajes no se mueven a DLQ

**Síntoma:** Los errores se repiten infinitamente en los logs

**Causas posibles:**

1. **El módulo no está actualizado a v2.7.0**
   ```bash
   # Verificar versión
   grep "version" /opt/odoo16/custom_addons/nesto_sync/__manifest__.py

   # Debe mostrar: 'version': '2.7.0'
   ```

2. **El controller no está re-lanzando excepciones**
   - Verificar que `generic_service.py` tenga `raise` en los `except`
   - Ver commit `c7865fb` para el fix correcto

3. **Mensajes sin messageId**
   - Pub/Sub debe incluir `messageId` en el envelope
   - Sin messageId, no se puede trackear (se hace ACK automático)

**Solución:**
- Actualizar módulo: `sudo systemctl restart odoo16`
- Revisar logs: `sudo journalctl -u odoo16 -n 100`

### Problema: DLQ tiene mensajes duplicados

**Síntoma:** Mismo messageId aparece múltiples veces en DLQ

**Causa:** El controller crea nuevo registro en lugar de actualizar

**Solución:**
El controller ya tiene lógica para evitar duplicados:

```python
existing = FailedMessage.search([('message_id', '=', message_id)], limit=1)
if existing:
    existing.write(...)  # Actualizar
else:
    FailedMessage.create(...)  # Crear nuevo
```

Si persiste, revisar logs para identificar el problema.

### Problema: Cron no limpia registros antiguos

**Síntoma:** Tabla `nesto_sync_message_retry` crece sin límite

**Verificar cron:**
```bash
# Desde Odoo UI
Configuración → Técnico → Automatización → Acciones Programadas
Buscar: "Nesto Sync: Limpiar registros de reintentos antiguos"
Verificar: Estado = Activo, Última ejecución
```

**Ejecutar manualmente:**
```python
# Desde Odoo shell o consola Python
env['nesto.sync.message.retry'].cleanup_old_records()
```

### Problema: Logs siguen siendo ilegibles

**Síntoma:** Stack traces largos en cada error

**Causa:** Versión antigua que usaba `exc_info=True`

**Solución:**
Verificar que los `_logger.error()` NO tengan `exc_info=True`:

```python
# ✓ CORRECTO (conciso)
_logger.error(f"[{message_id}] Error en sincronización: {error_msg}")

# ✗ INCORRECTO (traceback largo)
_logger.error(f"Error: {error_msg}", exc_info=True)
```

El traceback completo se guarda en DLQ, no es necesario en logs.

---

## Monitoreo y Métricas

### Consultas Útiles

**1. Mensajes fallidos por tipo de entidad:**
```sql
SELECT entity_type, COUNT(*) as total
FROM nesto_sync_failed_message
WHERE state = 'failed'
GROUP BY entity_type
ORDER BY total DESC;
```

**2. Errores más comunes:**
```sql
SELECT error_message, COUNT(*) as occurrences
FROM nesto_sync_failed_message
GROUP BY error_message
ORDER BY occurrences DESC
LIMIT 10;
```

**3. Mensajes con más reintentos:**
```sql
SELECT message_id, entity_type, retry_count, error_message
FROM nesto_sync_failed_message
ORDER BY retry_count DESC
LIMIT 10;
```

**4. Tasa de resolución:**
```sql
SELECT
    COUNT(*) FILTER (WHERE state = 'resolved') as resolved,
    COUNT(*) FILTER (WHERE state = 'failed') as pending,
    COUNT(*) FILTER (WHERE state = 'permanently_failed') as permanent,
    COUNT(*) as total
FROM nesto_sync_failed_message;
```

### Alertas Recomendadas

1. **Alerta si DLQ > 10 mensajes**
   - Indica problema sistémico o bug en Nesto/Odoo

2. **Alerta si mismo error se repite > 5 veces**
   - Puede indicar validación que debe ajustarse

3. **Alerta si mensajes sin revisar > 24 horas**
   - Recordatorio para revisar DLQ periódicamente

---

## Mejoras Futuras

### TODO: Reprocesamiento Automático

Actualmente `action_reprocess()` solo muestra un mensaje. Implementar:

```python
def action_reprocess(self):
    """Reprocesa el mensaje automáticamente"""
    self.ensure_one()

    # Cambiar estado a 'reprocessing'
    self.write({'state': 'reprocessing'})

    # Simular nueva request a /nesto_sync
    # con los datos de raw_data
    try:
        # ... lógica de reprocesamiento ...
        self.write({'state': 'resolved'})
    except Exception as e:
        self.write({'state': 'failed', 'error_message': str(e)})
```

### TODO: Dashboard de Métricas

Panel visual en Odoo con:
- Gráfico de mensajes fallidos por día
- Top 5 errores más comunes
- Tasa de resolución
- Tiempo promedio de resolución

### TODO: Notificaciones

Enviar email/notificación a admin cuando:
- Un mensaje llega a DLQ
- DLQ supera umbral (ej: 10 mensajes)
- Mensaje lleva > 24h sin resolver

---

## Changelog

### v2.7.0 (2025-11-19)

**Nuevas Funcionalidades:**
- ✅ Sistema DLQ completo con tracking de reintentos
- ✅ Modelos: `nesto.sync.failed.message` y `nesto.sync.message.retry`
- ✅ Límite configurable de reintentos (3 por defecto)
- ✅ Vistas Odoo para gestión visual
- ✅ Wizard para marcar como resuelto/fallido
- ✅ Cron job de limpieza automática
- ✅ Logs enriquecidos con messageId
- ✅ Información completa del error en DLQ
- ✅ Fix: Evitar validación de unicidad en id_fields sin cambios

**Bugs Corregidos:**
- ✅ Exception re-raising en `generic_service.py`
- ✅ Logs concisos (sin `exc_info=True`)
- ✅ Wizard faltante para gestión de mensajes

---

## Soporte

**Documentación adicional:**
- [README.md](../README.md) - Guía general del módulo
- [CHANGELOG.md](../CHANGELOG.md) - Historial de versiones

**Logs:**
```bash
# Ver logs en tiempo real
sudo journalctl -u odoo16 -f | grep nesto_sync

# Ver últimos 100 mensajes
sudo journalctl -u odoo16 -n 100 | grep nesto_sync

# Buscar mensajes en DLQ
sudo journalctl -u odoo16 | grep "Moviendo a DLQ"
```

**Tests:**
```bash
# Ejecutar tests del DLQ
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo-bin -c /opt/odoo16/odoo.conf \
    -d odoo16 --test-enable --stop-after-init \
    -i nesto_sync --test-tags=test_dlq_system
```

---

**Autor:** Carlos Adrián Martínez
**Licencia:** LGPL-3
