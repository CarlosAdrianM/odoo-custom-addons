# Próxima Sesión - Sincronización Bidireccional

**Fecha última sesión**: 2025-11-10
**Estado actual**: ✅ Código funcional en desarrollo (Odoo18), pendiente de sincronizar a producción (nuevavisionodoo)

## 🎯 Contexto Crítico: Dos Servidores

### IMPORTANTE: Estábamos trabajando en servidores diferentes

Durante la última sesión descubrimos que:

- **Servidor de Desarrollo (Odoo18)**: `/opt/odoo16/custom_addons/nesto_sync`
  - ✅ Aquí hice todos los cambios
  - ✅ Sincronización bidireccional FUNCIONA
  - ✅ Logs muestran 🔔 emoji y todo el flujo
  - ✅ Tests de Python exitosos

- **Servidor de Producción (nuevavisionodoo)**: `/opt/odoo/custom_addons/nesto_sync`
  - ❌ Código antiguo (sin los cambios)
  - ❌ No tiene las credenciales configuradas
  - ❌ Por eso no aparecían logs al actualizar desde UI

**Conclusión**: Todo el trabajo está en Odoo18, hay que sincronizarlo a nuevavisionodoo.

---

## 📋 Resumen de lo Completado en Odoo18

### 1. Archivos Modificados

#### `/opt/odoo16/custom_addons/nesto_sync/core/odoo_publisher.py`
**Cambio**: Arreglado bug de serialización JSON

**Líneas modificadas**:
- Línea 103-104: Añadido llamada a `_serialize_odoo_value()`
- Líneas 221-259: Nuevo método `_serialize_odoo_value()`

**¿Por qué?**: Los objetos Many2one (como `state_id`, `country_id`) no son serializables a JSON directamente. Ahora se convierten a IDs antes de publicar.

```python
# Línea 103-104 (MODIFICADO)
# Serializar objetos Odoo (Many2one, Many2many, etc.)
value = self._serialize_odoo_value(value)

# Líneas 221-259 (NUEVO MÉTODO)
def _serialize_odoo_value(self, value):
    """
    Serializa valores de Odoo para JSON

    Convierte objetos Odoo (Many2one, Many2many, recordset) a valores serializables
    """
    # None, bool, int, float, str → ya son serializables
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    # Many2one (ej: state_id, country_id) → devolver ID
    if hasattr(value, '_name') and hasattr(value, 'id'):
        # Es un recordset de Odoo
        if len(value) == 1:
            # Many2one: devolver solo el ID
            return value.id
        elif len(value) > 1:
            # Many2many o One2many: devolver lista de IDs
            return value.ids
        else:
            # Recordset vacío
            return None

    # Listas/tuplas → serializar cada elemento
    if isinstance(value, (list, tuple)):
        return [self._serialize_odoo_value(v) for v in value]

    # Diccionarios → serializar cada valor
    if isinstance(value, dict):
        return {k: self._serialize_odoo_value(v) for k, v in value.items()}

    # Si llegamos aquí, intentar convertir a string
    return str(value)
```

#### `/opt/odoo16/custom_addons/nesto_sync/models/res_partner.py`
**Cambio**: Añadido logging temporal de debug

**Líneas modificadas**:
- Línea 3: `import logging`
- Línea 5: `_logger = logging.getLogger(__name__)`
- Líneas 15-18: Override temporal de `write()` con emoji ⭐

```python
def write(self, vals):
    """Override para debug - verificar que se llama"""
    _logger.info(f"⭐ ResPartner.write() llamado con vals: {vals}")
    return super(ResPartner, self).write(vals)
```

**NOTA**: Este código es TEMPORAL. Una vez verificado que funciona en producción, hay que eliminarlo (el mixin ya tiene su propio logging con 🔔).

#### `/opt/odoo16/secrets/google-cloud-credentials.json`
**Cambio**: Creado archivo con credenciales

**Contenido**: JSON con service account de Google Cloud
- Project ID: `nestomaps-1547636206945`
- Service Account: `nesto-130@nestomaps-1547636206945.iam.gserviceaccount.com`

**Permisos**:
```bash
sudo mkdir -p /opt/odoo16/secrets
sudo chmod 700 /opt/odoo16/secrets
sudo chown odoo:odoo /opt/odoo16/secrets
sudo chmod 600 /opt/odoo16/secrets/google-cloud-credentials.json
```

#### `/etc/systemd/system/odoo16.service`
**Cambio**: Añadida variable de entorno

```ini
[Service]
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/odoo16/secrets/google-cloud-credentials.json"
```

**Aplicado con**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart odoo16
```

#### System Parameters (Base de datos)
Configurados con Python:
```python
env['ir.config_parameter'].sudo().set_param('nesto_sync.google_project_id', 'nestomaps-1547636206945')
env['ir.config_parameter'].sudo().set_param('nesto_sync.pubsub_topic', 'sincronizacion-tablas')
```

### 2. Verificación Exitosa en Odoo18

**Test ejecutado**:
```python
python3 test_bidirectional.py
```

**Resultado**:
```
✅ Cliente encontrado: 2012 SACH SERVICE, S.L. (ID=5428)
Actualizando teléfono a: 666642422
✅ Actualizado
```

**Logs obtenidos** (journalctl):
```
16:06:22,738 INFO: 🔔 BidirectionalSyncMixin.write() llamado en res.partner con vals: {'mobile': '666642422'}
16:06:22,782 INFO: Creando publisher para proveedor: google_pubsub
16:06:22,783 INFO: Configurando Google Pub/Sub Publisher: project_id=nestomaps-1547636206945
16:06:22,785 INFO: Publicando cliente desde Odoo: res.partner ID 5428
```

✅ **Confirmado**: La sincronización bidireccional FUNCIONA en Odoo18

---

## 🚀 Pasos para Sincronizar a Producción (nuevavisionodoo)

### Opción A: Git Pull (Recomendado)

#### 1. Hacer commit y push desde Odoo18
```bash
# En Odoo18
cd /opt/odoo16/custom_addons/nesto_sync

# Verificar cambios
git status

# Añadir archivos modificados (NO las credenciales)
git add core/odoo_publisher.py
git add models/res_partner.py

# Commit
git commit -m "fix: Serialización JSON para Many2one en bidirectional sync"

# Push
git push origin main
```

#### 2. Pull en nuevavisionodoo
```bash
# En nuevavisionodoo
cd /opt/odoo/custom_addons/nesto_sync

# Pull de cambios
git pull origin main

# Verificar que los archivos se actualizaron
git log --oneline -5
```

### Opción B: Copia Directa (Si no funciona git)

```bash
# Desde tu máquina local o desde Odoo18
scp /opt/odoo16/custom_addons/nesto_sync/core/odoo_publisher.py usuario@nuevavisionodoo:/opt/odoo/custom_addons/nesto_sync/core/
scp /opt/odoo16/custom_addons/nesto_sync/models/res_partner.py usuario@nuevavisionodoo:/opt/odoo/custom_addons/nesto_sync/models/
```

---

## 🔑 Configurar Credenciales en nuevavisionodoo

### 1. Crear directorio secrets
```bash
# En nuevavisionodoo
sudo mkdir -p /opt/odoo/secrets
sudo chmod 700 /opt/odoo/secrets
sudo chown odoo:odoo /opt/odoo/secrets
```

### 2. Copiar archivo de credenciales
```bash
# Desde tu máquina local
scp ~/Descargas/credentials_pubsub.json usuario@nuevavisionodoo:/tmp/

# En nuevavisionodoo
sudo mv /tmp/credentials_pubsub.json /opt/odoo/secrets/google-cloud-credentials.json
sudo chmod 600 /opt/odoo/secrets/google-cloud-credentials.json
sudo chown odoo:odoo /opt/odoo/secrets/google-cloud-credentials.json
```

### 3. Añadir variable de entorno a systemd

**Editar servicio** (en nuevavisionodoo):
```bash
sudo systemctl edit --full odoo.service
# o el nombre que tenga el servicio en producción
```

**Añadir en la sección `[Service]`**:
```ini
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/odoo/secrets/google-cloud-credentials.json"
```

**Recargar y reiniciar**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart odoo  # o el nombre del servicio
```

### 4. Configurar System Parameters

**Opción 1: Via Python**
```bash
# En nuevavisionodoo
python3 odoo-bin shell -c /opt/odoo/odoo.conf -d [nombre_base_datos]
```

```python
env['ir.config_parameter'].sudo().set_param('nesto_sync.google_project_id', 'nestomaps-1547636206945')
env['ir.config_parameter'].sudo().set_param('nesto_sync.pubsub_topic', 'sincronizacion-tablas')
env.cr.commit()
exit()
```

**Opción 2: Via UI de Odoo**
1. Settings → Technical → System Parameters
2. Crear parámetro `nesto_sync.google_project_id` = `nestomaps-1547636206945`
3. Crear parámetro `nesto_sync.pubsub_topic` = `sincronizacion-tablas`

---

## 🔄 Actualizar Módulo en nuevavisionodoo

### 1. Limpiar cache de Python
```bash
# En nuevavisionodoo
cd /opt/odoo/custom_addons/nesto_sync
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
```

### 2. Actualizar módulo
```bash
# En nuevavisionodoo
python3 odoo-bin -c /opt/odoo/odoo.conf -d [nombre_base_datos] -u nesto_sync --stop-after-init
```

### 3. Reiniciar servicio
```bash
sudo systemctl restart odoo  # o el nombre del servicio
```

---

## ✅ Verificación en nuevavisionodoo

### 1. Actualizar cliente desde UI

1. Abrir Odoo en navegador
2. Ir a Contactos
3. Buscar un cliente que tenga `cliente_externo` y `contacto_externo`
4. Cambiar el campo **Teléfono Móvil**
5. Guardar

### 2. Verificar logs

**Comando**:
```bash
sudo journalctl -u odoo --since '1 minute ago' | grep -E '🔔|⭐|Publicando|BidirectionalSyncMixin'
```

**Logs esperados** (si funciona):
```
INFO: ⭐ ResPartner.write() llamado con vals: {'mobile': '666XXXXXX'}
INFO: 🔔 BidirectionalSyncMixin.write() llamado en res.partner con vals: {'mobile': '666XXXXXX'}
INFO: Creando publisher para proveedor: google_pubsub
INFO: Configurando Google Pub/Sub Publisher: project_id=nestomaps-1547636206945
INFO: Publicando cliente desde Odoo: res.partner ID XXXX
```

### 3. Si no aparece nada en logs

**Verificar que el módulo se cargó**:
```bash
sudo journalctl -u odoo --since '5 minutes ago' | grep nesto_sync
```

**Debe aparecer**:
```
DEBUG: Loading module nesto_sync
```

**Verificar credenciales**:
```bash
sudo systemctl show odoo | grep GOOGLE_APPLICATION_CREDENTIALS
```

**Debe mostrar**:
```
Environment=GOOGLE_APPLICATION_CREDENTIALS=/opt/odoo/secrets/google-cloud-credentials.json
```

**Verificar archivo existe**:
```bash
sudo ls -la /opt/odoo/secrets/google-cloud-credentials.json
```

**Debe mostrar**:
```
-rw------- 1 odoo odoo 2329 [fecha] google-cloud-credentials.json
```

---

## 🐛 Troubleshooting

### Error: "Object of type res.country.state is not JSON serializable"

**Causa**: No se aplicó el fix de `odoo_publisher.py`

**Solución**: Verificar que el método `_serialize_odoo_value()` está en línea 221 del archivo

### Error: "DefaultCredentialsError: Your default credentials were not found"

**Causa**: Variable de entorno no configurada o archivo no existe

**Solución**:
1. Verificar que el archivo existe: `sudo ls -la /opt/odoo/secrets/google-cloud-credentials.json`
2. Verificar variable de entorno: `sudo systemctl show odoo | grep GOOGLE`
3. Reiniciar servicio: `sudo systemctl restart odoo`

### No aparecen logs pero el teléfono sí se actualiza

**Causa**: El código antiguo está activo (sin el mixin)

**Solución**:
1. Verificar que el archivo `models/res_partner.py` tiene el logging con ⭐
2. Limpiar cache: `find . -type f -name "*.pyc" -delete`
3. Actualizar módulo: `-u nesto_sync --stop-after-init`
4. Reiniciar servicio

### Logs muestran "Sin cambios en res.partner, omitiendo actualización"

**Causa**: El anti-bucle está funcionando (esto es CORRECTO)

**Explicación**: Si intentas actualizar con el mismo valor, el sistema detecta que no hay cambios y no publica. Prueba con un valor diferente.

---

## 🧹 Limpieza Post-Verificación

Una vez verificado que funciona en producción, **ELIMINAR** el código temporal de debug:

### Archivo: `/opt/odoo/custom_addons/nesto_sync/models/res_partner.py`

**ELIMINAR estas líneas**:
```python
import logging

_logger = logging.getLogger(__name__)

def write(self, vals):
    """Override para debug - verificar que se llama"""
    _logger.info(f"⭐ ResPartner.write() llamado con vals: {vals}")
    return super(ResPartner, self).write(vals)
```

**¿Por qué?**: El `BidirectionalSyncMixin` ya tiene su propio logging con 🔔. El código con ⭐ era solo para debug.

**Después de eliminar**:
```bash
python3 odoo-bin -c /opt/odoo/odoo.conf -d [nombre_base_datos] -u nesto_sync --stop-after-init
sudo systemctl restart odoo
```

---

## 📊 Estado Final Esperado

Después de completar todos los pasos:

### En nuevavisionodoo (Producción)
- ✅ Código sincronizado desde Odoo18
- ✅ Credenciales Google Cloud configuradas
- ✅ System Parameters configurados
- ✅ Módulo actualizado
- ✅ Servicio reiniciado
- ✅ Logs muestran sincronización bidireccional funcionando

### Logs esperados al actualizar un cliente
```
🔔 BidirectionalSyncMixin.write() llamado en res.partner
Publicando cliente desde Odoo: res.partner ID XXXX
```

### Anti-bucle funcionando
Si Nesto envía un mensaje con los mismos valores que ya tiene Odoo:
```
Sin cambios en res.partner, omitiendo actualización
```
(NO se publica de vuelta → bucle evitado ✅)

---

## 📚 Documentación de Referencia

- [CONFIGURACION_CREDENCIALES.md](CONFIGURACION_CREDENCIALES.md) - Guía detallada de credenciales
- [ESTADO_DESPLIEGUE.md](ESTADO_DESPLIEGUE.md) - Estado actual del despliegue
- [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md) - Arquitectura del sistema
- [test_bidirectional.py](test_bidirectional.py) - Script de prueba

---

## 🎯 Checklist de la Próxima Sesión

- [ ] **Paso 1**: Sincronizar código a nuevavisionodoo (git pull o scp)
- [ ] **Paso 2**: Copiar credenciales a `/opt/odoo/secrets/`
- [ ] **Paso 3**: Configurar variable de entorno en systemd
- [ ] **Paso 4**: Configurar System Parameters (google_project_id y pubsub_topic)
- [ ] **Paso 5**: Actualizar módulo (`-u nesto_sync`)
- [ ] **Paso 6**: Reiniciar servicio Odoo
- [ ] **Paso 7**: Probar actualización desde UI
- [ ] **Paso 8**: Verificar logs (debe aparecer 🔔 emoji)
- [ ] **Paso 9**: Confirmar publicación a Pub/Sub
- [ ] **Paso 10**: Eliminar código temporal de debug (⭐)

---

**Sesión anterior finalizada**: 2025-11-10
**Próxima sesión**: Pendiente
**Estado**: Listo para sincronizar a producción
