# Troubleshooting - Cliente 15191 no envía mensaje a Pub/Sub

**Fecha**: 2025-11-11
**Servidor**: nuevavisionodoo (PRODUCCIÓN)
**Problema**: Al cambiar el teléfono del cliente 15191 desde la UI, no se envía mensaje a Google Pub/Sub

---

## 🔍 Pasos de Diagnóstico

### 1. Verificar versión del módulo en producción

**Comando** (en producción):
```bash
ssh root@217.61.212.170
cd /opt/odoo/custom_addons/nesto_sync
git log --oneline -5
```

**Esperado**:
```
82737a2 docs: Añadir documentación de servidores
a555e94 docs: Actualizar estado del despliegue con fix de serialización JSON
74c4dfa fix: Corregir doble serialización JSON y estructura de mensaje
```

**Si NO aparece el commit `74c4dfa`**:
→ El código está desactualizado. Hacer `git pull origin main`

---

### 2. Verificar que el módulo está actualizado en Odoo

**Comando** (en producción):
```bash
# Verificar en la UI de Odoo:
# Aplicaciones → Buscar "Nesto Sync" → Click en el módulo
# Debe mostrar: Versión 2.1.0
```

**Si muestra versión 1.0**:
→ El módulo NO se ha actualizado. Ejecutar:
```bash
cd /opt/odoo/custom_addons/nesto_sync
find . -type f -name "*.pyc" -delete
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Verificar nombre del servicio
systemctl list-units | grep odoo

# Actualizar módulo (ajustar nombre de servicio y BD)
python3 /usr/bin/odoo -c /opt/odoo/odoo.conf -d [NOMBRE_BD] -u nesto_sync --stop-after-init

# Reiniciar
sudo systemctl restart odoo  # o el nombre del servicio
```

---

### 3. Verificar que el cliente tiene los campos necesarios

**Requisito para sincronización bidireccional**:
El cliente DEBE tener:
- `cliente_externo` (campo obligatorio para identificar cliente en Nesto)
- `contacto_externo` (campo obligatorio para identificar contacto en Nesto)

**Comando SQL** (verificar en producción):
```sql
# Conectar a PostgreSQL
sudo -u postgres psql [NOMBRE_BD]

# Verificar el cliente 15191
SELECT
    id,
    name,
    vat,
    cliente_externo,
    contacto_externo,
    parent_id,
    mobile,
    phone
FROM res_partner
WHERE id = 15191;
```

**Casos posibles**:

#### Caso A: cliente_externo es NULL
```
id    | name         | cliente_externo | contacto_externo
15191 | Juan Pérez   | NULL            | 12345
```

**Problema**: Si `cliente_externo` es NULL, el registro NO es un cliente (Parent), es un contacto (Child).

**Verificar si es un contacto**:
```sql
SELECT
    c.id as contacto_id,
    c.name as contacto_name,
    c.contacto_externo,
    p.id as parent_id,
    p.name as parent_name,
    p.cliente_externo
FROM res_partner c
LEFT JOIN res_partner p ON c.parent_id = p.id
WHERE c.id = 15191;
```

**Si parent_id NO es NULL**:
→ Es un contacto (PersonasContacto), NO un cliente.
→ La sincronización bidireccional está configurada solo para clientes (Parent).
→ Si cambias el teléfono de un contacto, NO se publicará solo.
→ Se publicará CUANDO cambies algo del cliente padre.

**Solución**: Cambiar el teléfono del CLIENTE PADRE, no del contacto.

---

#### Caso B: cliente_externo y contacto_externo son NULL
```
id    | name         | cliente_externo | contacto_externo
15191 | Juan Pérez   | NULL            | NULL
```

**Problema**: El registro NO tiene identificadores externos. NO se puede sincronizar con Nesto.

**Verificar en config** [config/entity_configs.py](config/entity_configs.py:59-63):
```python
'search_fields': {
    'unique': ['cliente_externo', 'contacto_externo'],
    'update': ['vat']
}
```

**Solución**: Este cliente fue creado manualmente en Odoo, no viene de Nesto.
- Opción 1: Asignarle `cliente_externo` y `contacto_externo` manualmente
- Opción 2: No sincronizarlo (solo se sincronizan clientes que vienen de Nesto)

---

#### Caso C: Es un cliente válido con ambos campos
```
id    | name              | cliente_externo | contacto_externo | parent_id
15191 | EMPRESA S.L.      | 39270           | 15191            | NULL
```

**Esto es correcto**. Si NO se envía mensaje, continuar con los siguientes pasos.

---

### 4. Verificar que BidirectionalSyncMixin está aplicado

**Archivo**: [models/res_partner.py](models/res_partner.py)

**Verificar que la clase hereda del mixin**:
```python
from ..models.bidirectional_sync_mixin import BidirectionalSyncMixin

class ResPartner(BidirectionalSyncMixin, models.Model):
    _inherit = 'res.partner'
    _name = 'res.partner'
```

**Si NO hereda de BidirectionalSyncMixin**:
→ El código está desactualizado. Hacer `git pull` y actualizar módulo.

---

### 5. Verificar logs en tiempo real

**Comando** (ejecutar en producción ANTES de cambiar el teléfono):
```bash
# Terminal 1: Seguir logs en tiempo real
sudo journalctl -u odoo -f | grep -E 'nesto_sync|BidirectionalSyncMixin|Publicando|⭐|🔔'
```

**Luego**:
1. Ir a la UI de Odoo
2. Buscar cliente 15191
3. Cambiar teléfono móvil
4. Guardar
5. Observar los logs en la terminal

---

### 6. Logs esperados y qué significan

#### Logs exitosos (TODO correcto):
```
INFO: ⭐ ResPartner.write() llamado con vals: {'mobile': '666999888'}
INFO: 🔔 BidirectionalSyncMixin.write() llamado en res.partner con vals: {'mobile': '666999888'}
INFO: Creando publisher para proveedor: google_pubsub
INFO: Configurando Google Pub/Sub Publisher: project_id=nestomaps-1547636206945
INFO: Publicando cliente desde Odoo: res.partner ID 15191
INFO: Mensaje publicado a sincronizacion-tablas: message_id=XXXXX, size=XXX bytes
```

#### No aparece NADA:
**Posibles causas**:
1. El módulo no está cargado
2. El código es antiguo (versión 1.0)
3. El registro no cumple los criterios para sincronización

**Verificar**:
```bash
# ¿Está el módulo cargado?
sudo journalctl -u odoo --since '10 minutes ago' | grep "Loading module nesto_sync"

# Debe aparecer:
DEBUG: Loading module nesto_sync (X/YY)
DEBUG: Module nesto_sync loaded in X.XXs
```

**Si NO aparece**:
→ El módulo no está en la lista de módulos instalados.
→ Verificar en UI: Aplicaciones → Buscar "nesto_sync" → ¿Está instalado?

#### Aparece solo ⭐ pero NO 🔔:
```
INFO: ⭐ ResPartner.write() llamado con vals: {'mobile': '666999888'}
```

**Causa**: El `BidirectionalSyncMixin` NO está interceptando el write().

**Verificar orden de herencia** en [models/res_partner.py](models/res_partner.py):
```python
class ResPartner(BidirectionalSyncMixin, models.Model):  # ✅ Correcto: Mixin primero
    # NOT: class ResPartner(models.Model, BidirectionalSyncMixin)  # ❌ Incorrecto
```

**Solución**:
```bash
# Limpiar cache
cd /opt/odoo/custom_addons/nesto_sync
find . -type f -name "*.pyc" -delete
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Reiniciar Odoo
sudo systemctl restart odoo
```

#### Aparece 🔔 pero NO "Publicando":
```
INFO: 🔔 BidirectionalSyncMixin.write() llamado en res.partner con vals: {'mobile': '666999888'}
INFO: Sin cambios en res.partner, omitiendo actualización
```

**Causa**: El **anti-bucle** detectó que no hay cambios reales.

**Explicación**:
- Si el valor de `mobile` ya era '666999888', NO se publica (esto es CORRECTO).
- El anti-bucle evita sincronizaciones innecesarias.

**Solución**: Cambiar el teléfono a un valor DIFERENTE del actual.

#### Aparece error de credenciales:
```
ERROR: DefaultCredentialsError: Your default credentials were not found
```

**Causa**: Variable de entorno `GOOGLE_APPLICATION_CREDENTIALS` no configurada.

**Verificar**:
```bash
sudo systemctl show odoo | grep GOOGLE_APPLICATION_CREDENTIALS
```

**Debe mostrar**:
```
Environment=GOOGLE_APPLICATION_CREDENTIALS=/opt/odoo/secrets/google-cloud-credentials.json
```

**Si NO aparece**:
→ Ver [PROXIMA_SESION.md](PROXIMA_SESION.md) sección "Configurar Credenciales"

#### Aparece error de serialización:
```
ERROR: Object of type res.country.state is not JSON serializable
```

**Causa**: El código con el fix de serialización NO está aplicado.

**Solución**: Verificar que `git log` muestra commit `74c4dfa`. Si no, hacer `git pull`.

---

### 7. Verificar configuración de entity_configs

**Archivo**: [config/entity_configs.py](config/entity_configs.py)

**Verificar que 'cliente' tiene bidirectional habilitado**:
```python
'cliente': {
    'odoo_model': 'res.partner',
    'nesto_table': 'Clientes',
    'bidirectional': True,  # ✅ Debe ser True
    # ...
}
```

**Si es False**:
→ La sincronización bidireccional está deshabilitada para clientes.
→ Cambiar a `True` y reiniciar Odoo.

---

### 8. Verificar System Parameters

**Comando** (en producción):
```bash
sudo -u postgres psql [NOMBRE_BD]

SELECT key, value
FROM ir_config_parameter
WHERE key LIKE 'nesto_sync.%';
```

**Esperado**:
```
                key                 |            value
------------------------------------+-----------------------------
nesto_sync.google_project_id        | nestomaps-1547636206945
nesto_sync.pubsub_topic             | sincronizacion-tablas
```

**Si NO aparecen**:
→ Ver [PROXIMA_SESION.md](PROXIMA_SESION.md) sección "Configurar System Parameters"

---

## 📋 Checklist de Diagnóstico Rápido

Ejecutar estos comandos en **PRODUCCIÓN** (nuevavisionodoo):

```bash
# 1. Verificar servidor
hostname  # Debe mostrar: nuevavisionodoo

# 2. Verificar código actualizado
cd /opt/odoo/custom_addons/nesto_sync
git log --oneline -3
# Debe aparecer: 74c4dfa fix: Corregir doble serialización JSON

# 3. Verificar versión del módulo en UI
# Aplicaciones → Nesto Sync → Debe mostrar: Versión 2.1.0

# 4. Verificar que el cliente tiene cliente_externo
sudo -u postgres psql [NOMBRE_BD] -c \
"SELECT id, name, cliente_externo, contacto_externo, parent_id FROM res_partner WHERE id = 15191;"

# 5. Seguir logs en tiempo real
sudo journalctl -u odoo -f | grep -E 'nesto_sync|BidirectionalSyncMixin|Publicando|⭐|🔔'

# 6. En otra terminal/navegador: cambiar teléfono del cliente 15191 y guardar

# 7. Observar qué aparece en los logs
```

---

## 🎯 Casos Más Comunes

### Caso 1: "No aparece NADA en los logs"
→ **Módulo no actualizado**. Ejecutar:
```bash
cd /opt/odoo/custom_addons/nesto_sync
git pull origin main
find . -type f -name "*.pyc" -delete
python3 /usr/bin/odoo -c /opt/odoo/odoo.conf -d [NOMBRE_BD] -u nesto_sync --stop-after-init
sudo systemctl restart odoo
```

### Caso 2: "Aparece ⭐ pero no 🔔"
→ **Orden de herencia incorrecto**. Verificar [models/res_partner.py](models/res_partner.py) y limpiar cache.

### Caso 3: "Aparece 🔔 pero dice 'Sin cambios'"
→ **Anti-bucle funcionando (correcto)**. Cambiar a un valor DIFERENTE.

### Caso 4: "Es un contacto (PersonasContacto), no un cliente"
→ **Contactos no sincronizan solos**. Cambiar algo del CLIENTE PADRE.

### Caso 5: "El cliente no tiene cliente_externo"
→ **Cliente creado manualmente en Odoo**. No se sincroniza con Nesto.

---

## 📞 Información para Debugging

### Nombre de la base de datos en producción

**Comando**:
```bash
cat /opt/odoo/odoo.conf | grep "^db_name"
```

### Nombre del servicio Odoo

**Comando**:
```bash
systemctl list-units | grep odoo
```

### Usuario de PostgreSQL

**Comando**:
```bash
cat /opt/odoo/odoo.conf | grep "^db_user"
```

---

## 🆘 Si Nada Funciona

1. **Verificar que el módulo está instalado**:
   - UI → Aplicaciones → Buscar "nesto_sync"
   - ¿Estado? Instalado / No instalado

2. **Verificar logs de inicio de Odoo**:
   ```bash
   sudo journalctl -u odoo --since "5 minutes ago" | grep -E "nesto_sync|error|traceback"
   ```

3. **Verificar que el archivo res_partner.py existe**:
   ```bash
   ls -la /opt/odoo/custom_addons/nesto_sync/models/res_partner.py
   ```

4. **Ver contenido del archivo**:
   ```bash
   cat /opt/odoo/custom_addons/nesto_sync/models/res_partner.py
   ```

   Debe tener:
   ```python
   from ..models.bidirectional_sync_mixin import BidirectionalSyncMixin

   class ResPartner(BidirectionalSyncMixin, models.Model):
       _inherit = 'res.partner'
       _name = 'res.partner'
   ```

---

**Última actualización**: 2025-11-11
**Autor**: Claude Code
**Propósito**: Diagnosticar por qué el cliente 15191 no envía mensajes a Pub/Sub
