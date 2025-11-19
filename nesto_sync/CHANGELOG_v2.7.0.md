# Changelog v2.7.0 - Sistema DLQ (Dead Letter Queue)

**Fecha:** 2025-11-19
**Versión:** 2.7.0
**Objetivo:** Evitar mensajes infinitos en cola PubSub

---

## 🎯 Problema Resuelto

Cuando nesto_sync no puede procesar un mensaje (por ejemplo, código de barras duplicado), el mensaje se reintenta indefinidamente creando un loop infinito. Esto genera:
- Logs repetitivos saturando el sistema
- Recursos consumidos innecesariamente
- Imposibilidad de identificar y resolver problemas

### Ejemplo del problema:
```
[2025-11-19 07:47:35] ERROR: Código de barras "1" ya asignado
[2025-11-19 07:47:35] ERROR: Código de barras "1" ya asignado
[2025-11-19 07:47:35] ERROR: Código de barras "1" ya asignado
... (infinitamente)
```

---

## ✅ Solución Implementada

Sistema completo de **Dead Letter Queue (DLQ)** con tracking de reintentos automático.

### Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Google PubSub                        │
│                          │                              │
│                          ↓                              │
│                   POST /nesto_sync                      │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Controller (con DLQ Logic)                 │
│                                                          │
│  1. Extraer messageId del envelope                      │
│  2. Intentar procesar mensaje                           │
│  3. Si ERROR → Incrementar contador de reintentos       │
│  4. ¿Reintentos > 3?                                    │
│     ├─ NO  → HTTP 500 (NACK) → PubSub reintenta        │
│     └─ SÍ  → Mover a DLQ + HTTP 200 (ACK) → Fin        │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  Dead Letter Queue                      │
│                                                          │
│  • Almacena mensaje original                            │
│  • Guarda error completo + stack trace                  │
│  • Permite reprocesamiento manual                       │
│  • Vista en Odoo para gestión                           │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Componentes Nuevos

### 1. Modelo: `nesto.sync.failed.message`
**Archivo:** `models/failed_message.py`

Almacena mensajes que fallaron después de múltiples intentos.

**Campos principales:**
- `message_id`: ID único de PubSub
- `raw_data`: Mensaje original completo (JSON)
- `entity_type`: Tipo de entidad (cliente/producto/proveedor)
- `error_message`: Mensaje de error legible
- `error_traceback`: Stack trace completo para debugging
- `retry_count`: Número de reintentos realizados
- `state`: failed / resolved / reprocessing / permanently_failed
- `first_attempt_date`: Primera vez que falló
- `last_attempt_date`: Último intento
- `resolution_notes`: Notas del administrador

**Acciones disponibles:**
- `action_reprocess()`: Reintenta procesar el mensaje
- `action_mark_resolved()`: Marca como resuelto manualmente
- `action_mark_permanently_failed()`: Marca como fallo permanente

---

### 2. Modelo: `nesto.sync.message.retry`
**Archivo:** `models/message_retry.py`

Tracking temporal de reintentos por messageId.

**Constantes configurables:**
```python
MAX_RETRIES = 3       # Límite de reintentos
CLEANUP_DAYS = 7      # Días para mantener registros
```

**Métodos principales:**
- `increment_retry()`: Incrementa contador y determina si mover a DLQ
- `mark_success()`: Marca mensaje como exitoso
- `mark_moved_to_dlq()`: Marca como movido a DLQ
- `cleanup_old_records()`: Limpieza automática (vía cron)
- `get_retry_stats()`: Estadísticas para dashboard

**Estados:**
- `retrying`: Mensaje siendo reintentado
- `moved_to_dlq`: Mensaje movido a DLQ
- `success`: Procesado exitosamente

---

### 3. Controller Mejorado
**Archivo:** `controllers/controllers.py:26-360`

**Cambios principales:**

#### Extracción de messageId:
```python
pubsub_envelope = json.loads(raw_data.decode('utf-8'))
message_id = pubsub_envelope.get('message', {}).get('messageId')
```

#### Manejo de 3 tipos de errores:

**A) RequirePrincipalClientError**
```python
# Cliente principal no existe (común cuando mensajes llegan desordenados)
# DECISIÓN: Reintentar algunas veces antes de mover a DLQ
if message_id:
    retry_info = self._handle_retry(...)
    if retry_info['should_move_to_dlq']:
        return Response(status=200)  # ACK → Detener reintentos
    else:
        return Response(status=500)  # NACK → Reintentar
```

**B) ValueError**
```python
# Errores de validación (datos malformados, campos faltantes)
# Similar lógica de reintentos
```

**C) Exception**
```python
# Errores inesperados (bugs, errores de BD, etc.)
# Similar lógica de reintentos
```

#### Nuevos métodos:
- `_handle_retry()`: Gestiona reintentos y DLQ
- `_move_to_dlq()`: Mueve mensaje a DLQ con toda la info
- `_mark_message_success()`: Marca mensaje como exitoso

#### Logs mejorados:
```python
_logger.info(f"[{message_id}] Sincronizando entidad de tipo: {entity_type}")
_logger.error(f"[{message_id}] Error después de {retry_count} intentos. Moviendo a DLQ.")
```

---

### 4. Vistas Odoo
**Archivo:** `views/failed_message_views.xml`

#### Menú nuevo:
```
Nesto Sync
└── Dead Letter Queue
    ├── Mensajes Fallidos
    └── Tracking de Reintentos
```

#### Vista de mensajes fallidos:
- **Lista (tree)**: Colores según estado (rojo=fallido, verde=resuelto)
- **Formulario**: 4 pestañas
  - Error: Mensaje legible
  - Stack Trace: Traceback completo
  - Datos Crudos: JSON original
  - Notas de Resolución: Documentación del admin

#### Filtros disponibles:
- Por estado (fallidos/resueltos/permanentes)
- Por tipo de entidad (cliente/producto/proveedor)
- Por fecha (últimas 24h, última semana)
- Agrupación por estado/entidad/fecha

#### Botones de acción:
- **Reprocesar**: Reintenta procesar el mensaje
- **Marcar como Resuelto**: Si se arregló manualmente en Odoo
- **Fallo Permanente**: Si no se puede resolver

---

### 5. Seguridad
**Archivo:** `security/ir.model.access.csv`

```csv
# Administradores: Acceso completo
access_nesto_sync_failed_message_admin,...,base.group_system,1,1,1,1

# Usuarios: Solo lectura
access_nesto_sync_failed_message_user,...,base.group_user,1,0,0,0
```

---

### 6. Cron Job
**Archivo:** `data/cron_jobs.xml`

```xml
<record id="ir_cron_cleanup_retry_records" model="ir.cron">
    <field name="name">Nesto Sync: Limpiar registros de reintentos antiguos</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="code">model.cleanup_old_records()</field>
</record>
```

**Ejecución:** Diaria a medianoche
**Acción:** Elimina registros de reintentos exitosos > 7 días

---

## 🔧 Configuración

### Límite de reintentos (modificable):

**Archivo:** `models/message_retry.py:28`
```python
MAX_RETRIES = 3  # Cambiar aquí el límite
```

### Días de retención de logs:

**Archivo:** `models/message_retry.py:29`
```python
CLEANUP_DAYS = 7  # Cambiar aquí los días
```

---

## 📊 Flujo de Trabajo Completo

### Caso 1: Mensaje procesa correctamente
```
1. Mensaje llega → Procesa ✅
2. _mark_message_success(messageId)
3. HTTP 200 → PubSub elimina mensaje
```

### Caso 2: Mensaje falla 1-2 veces
```
1. Mensaje llega → Error ❌
2. increment_retry() → retry_count = 1
3. HTTP 500 (NACK) → PubSub reintenta
4. Mensaje llega (2° intento) → Error ❌
5. increment_retry() → retry_count = 2
6. HTTP 500 (NACK) → PubSub reintenta
7. Mensaje llega (3° intento) → Procesa ✅
8. mark_success() → Fin
```

### Caso 3: Mensaje falla 4+ veces (DLQ)
```
1. Mensaje llega → Error ❌
2. increment_retry() → retry_count = 1
3. HTTP 500 (NACK) → Reintentar
4. ... (reintentos 2 y 3) ...
5. Mensaje llega (4° intento) → Error ❌
6. increment_retry() → retry_count = 4
7. should_move_to_dlq = True
8. _move_to_dlq() → Crea registro en DLQ
9. HTTP 200 (ACK) → PubSub elimina mensaje
10. Administrador revisa en Odoo → Reprocesa/Resuelve
```

---

## 🛡️ Protecciones Implementadas

### 1. Mensajes sin messageId
```python
if not message_id:
    _logger.warning("Mensaje sin messageId")
    # Procesar normalmente pero sin tracking
    # Si falla: HTTP 200 (ACK) para evitar loop infinito
```

### 2. Idempotencia en DLQ
```python
existing = FailedMessage.search([('message_id', '=', message_id)])
if existing:
    existing.write({...})  # Actualizar
else:
    FailedMessage.create({...})  # Crear
```

### 3. Commit explícito
```python
request.env.cr.commit()  # Persiste inmediatamente
```

### 4. Logs con contexto
```python
_logger.info(f"[{message_id}] Reintento {retry_count}/{MAX_RETRIES}")
```

---

## 📈 Ventajas del Sistema

✅ **No se pierden mensajes**: Todo se guarda en DLQ
✅ **Sin loops infinitos**: Límite de 3 reintentos
✅ **Visibilidad completa**: Interface visual en Odoo
✅ **Reprocesamiento manual**: Cuando se arregle el problema
✅ **Genérico**: Funciona para cualquier tipo de error
✅ **Autocontenido**: Todo dentro del módulo nesto_sync
✅ **Portable**: Instalar en otras instancias sin config adicional
✅ **Logs detallados**: Facilita debugging
✅ **Limpieza automática**: Cron mantiene BD ligera

---

## 🚀 Instalación/Actualización

### En desarrollo (local):
```bash
# Actualizar módulo desde Odoo UI:
Apps > Buscar "Nesto Sync" > Actualizar
```

### En producción:
```bash
# 1. Push de cambios
git push origin main

# 2. En servidor de producción
cd /opt/odoo/custom_addons/nesto_sync
git pull origin main

# 3. Reiniciar Odoo
sudo systemctl restart odoo16

# 4. Actualizar módulo desde Odoo UI
```

---

## 📋 Testing

### Verificar instalación:
1. Ir a Odoo UI
2. Buscar menú "Nesto Sync" en la barra lateral
3. Debería aparecer "Dead Letter Queue" con 2 submenús

### Forzar un mensaje a DLQ (testing):
1. Crear producto con código de barras duplicado en Nesto
2. Enviar mensaje 4 veces (simulando reintentos)
3. Verificar que aparece en "Mensajes Fallidos"

### Probar reprocesamiento:
1. Corregir el problema (eliminar código de barras duplicado)
2. En Odoo: Mensajes Fallidos > Abrir registro > Reprocesar
3. Verificar que cambia a estado "Resuelto"

---

## 📞 Soporte

### Logs del sistema:
```bash
# Ver logs en tiempo real
sudo journalctl -u odoo16 -f | grep -i "nesto_sync"

# Ver logs de DLQ específicamente
sudo journalctl -u odoo16 | grep -i "dlq\|retry"
```

### Estadísticas de reintentos:
```python
# En shell de Odoo:
env['nesto.sync.message.retry'].get_retry_stats()
```

### Limpiar manualmente reintentos antiguos:
```python
# En shell de Odoo:
env['nesto.sync.message.retry'].cleanup_old_records()
```

---

## 🔄 Commits Realizados

### Commit principal:
```
0da497b feat: Sistema DLQ (Dead Letter Queue) v2.7.0

Archivos modificados:
- __manifest__.py (versión 2.7.0 + changelog)
- controllers/controllers.py (lógica DLQ)
- models/__init__.py (imports nuevos modelos)

Archivos nuevos:
- models/failed_message.py (modelo DLQ)
- models/message_retry.py (tracking reintentos)
- views/failed_message_views.xml (vistas Odoo)
- security/ir.model.access.csv (permisos)
- data/cron_jobs.xml (limpieza automática)
```

---

## 📝 Notas Finales

- **Límite recomendado**: 3 reintentos es suficiente para errores transitorios
- **Monitoreo**: Revisar DLQ semanalmente para detectar problemas recurrentes
- **Limpieza**: El cron mantiene la BD limpia automáticamente
- **Escalabilidad**: El sistema está preparado para alto volumen de mensajes

**Versión anterior:** 2.6.0
**Versión actual:** 2.7.0
**Estado:** Listo para producción ✅
