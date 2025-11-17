# Documentación de Servidores - Nesto Sync

**Última actualización**: 2025-11-11
**IMPORTANTE**: Leer esta documentación SIEMPRE antes de trabajar con el módulo

---

## 🖥️ Arquitectura de Servidores

### Servidor 1: **DESARROLLO** (Odoo18)

**Hostname**: `Odoo18`
**IP**: (La IP del servidor de desarrollo)
**Usuario SSH**: `azureuser` (probablemente)
**Path del módulo**: `/opt/odoo16/custom_addons/nesto_sync`
**Servicio Odoo**: `odoo16.service`
**Base de datos**: `odoo16`
**Virtualenv**: `/opt/odoo16/odoo-venv`

**Propósito**:
- Desarrollo y testing de nuevas funcionalidades
- Aquí se hacen TODOS los cambios primero
- Aquí se ejecutan los tests
- Desde aquí se hace `git push` a GitHub

**Cómo identificarlo**:
```bash
hostname
# Output: Odoo18

pwd
# Si estás en: /opt/odoo16/custom_addons/nesto_sync
# → Estás en DESARROLLO
```

---

### Servidor 2: **PRODUCCIÓN** (nuevavisionodoo)

**Hostname**: `nuevavisionodoo`
**URL Web**: `sede.nuevavision.es`
**IP**: `217.61.212.170`
**Usuario SSH**: `root`
**Comando de conexión**: `ssh root@217.61.212.170` o `ssh root@nuevavisionodoo`
**Path del módulo**: `/opt/odoo/custom_addons/nesto_sync` (⚠️ **DIFERENTE AL DESARROLLO**)
**Archivo de configuración**: `/etc/odoo/odoo.conf`
**Servicio Odoo**: `odoo.service`
**Base de datos**: `odoo_nv`
**Instalación Odoo**: Sistema (no virtualenv), ubicado en `/usr/bin/odoo`
**Logs**: `/var/log/odoo/odoo-server.log`

**Propósito**:
- Servidor de producción donde corren los clientes reales
- Aquí NUNCA se modifican archivos directamente
- Se actualiza desde GitHub con `git pull`
- Es el servidor que da Error 500 cuando faltan librerías

**Cómo identificarlo**:
```bash
hostname
# Output: nuevavisionodoo

pwd
# Si estás en: /opt/odoo/custom_addons/nesto_sync
# → Estás en PRODUCCIÓN

# O también:
curl -I http://localhost
# Si el servidor responde con sede.nuevavision.es → PRODUCCIÓN
```

---

## 🔄 Flujo de Trabajo Correcto

### 1. Desarrollo (Odoo18)

```bash
# 1. Conectar a DESARROLLO
ssh azureuser@odoo18  # o la IP correspondiente

# 2. Verificar que estás en el servidor correcto
hostname  # Debe mostrar: Odoo18
cd /opt/odoo16/custom_addons/nesto_sync

# 3. Hacer cambios en el código

# 4. Ejecutar tests
python3 test_publisher_structure.py

# 5. Actualizar módulo en Odoo
python3 /opt/odoo16/odoo-bin -c /opt/odoo16/odoo.conf -d odoo16 -u nesto_sync --stop-after-init

# 6. Reiniciar servicio
sudo systemctl restart odoo16

# 7. Verificar logs
sudo journalctl -u odoo16 -n 50 --no-pager

# 8. Si todo funciona, hacer commit y push
git add .
git commit -m "descripción del cambio"
git push origin main
```

### 2. Despliegue a Producción (nuevavisionodoo)

```bash
# 1. Conectar a PRODUCCIÓN
ssh root@217.61.212.170
# o
ssh root@nuevavisionodoo

# 2. ⚠️ VERIFICAR QUE ESTÁS EN EL SERVIDOR CORRECTO
hostname  # Debe mostrar: nuevavisionodoo
pwd       # Si estás en /opt/odoo16 → ¡ESTÁS EN EL SERVIDOR EQUIVOCADO!

# 3. Ir al directorio correcto
cd /opt/odoo/custom_addons/nesto_sync  # ⚠️ /opt/odoo, NO /opt/odoo16

# 4. Hacer pull de los cambios desde GitHub
git pull origin main

# 5. Limpiar cache de Python
find . -type f -name "*.pyc" -delete
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# 6. Verificar que las librerías necesarias están instaladas
python3 -c "import google.cloud.pubsub_v1; print('OK')"
# Si da error → pip3 install --break-system-packages google-cloud-pubsub

# 7. Actualizar módulo (base de datos: odoo_nv)
/usr/bin/odoo -c /etc/odoo/odoo.conf -d odoo_nv -u nesto_sync --stop-after-init

# 8. Verificar servicio Odoo
systemctl list-units | grep odoo  # Ver el nombre exacto del servicio

# 9. Reiniciar servicio
sudo systemctl restart odoo  # o el nombre que corresponda

# 10. Verificar logs
sudo journalctl -u odoo -n 50 --no-pager
```

---

## ⚠️ Errores Comunes y Cómo Evitarlos

### Error 1: "Estoy en /opt/odoo16 pero el hostname dice nuevavisionodoo"

**Causa**: Estás en el servidor de producción pero en el directorio incorrecto.

**Solución**:
```bash
cd /opt/odoo/custom_addons/nesto_sync  # El path correcto en producción
```

### Error 2: "ModuleNotFoundError: No module named 'google'"

**Causa**: Estás en producción y falta la librería `google-cloud-pubsub`.

**Solución**:
```bash
# En producción (nuevavisionodoo)
pip3 install --break-system-packages google-cloud-pubsub
sudo systemctl restart odoo
```

**¿Por qué `--break-system-packages`?**:
- Producción usa Python 3.12 con "externally-managed-environment" (PEP 668)
- Odoo está instalado a nivel de sistema (no virtualenv)
- Es seguro usar esta flag en este contexto

### Error 3: "Error 500 al acceder a Odoo desde el navegador"

**Causa más común**: Falta alguna librería Python necesaria para el módulo.

**Cómo verificar**:
```bash
# En producción
sudo journalctl -u odoo -n 100 --no-pager | grep -i "error\|traceback"
```

**Solución**:
1. Identificar la librería faltante en los logs
2. Instalarla con `pip3 install --break-system-packages [nombre-libreria]`
3. Reiniciar servicio

### Error 4: "He hecho cambios en el servidor de desarrollo pero no se reflejan en producción"

**Causa**: No has hecho `git push` desde desarrollo y `git pull` desde producción.

**Solución correcta**:
```bash
# En DESARROLLO (Odoo18)
cd /opt/odoo16/custom_addons/nesto_sync
git add .
git commit -m "descripción"
git push origin main

# En PRODUCCIÓN (nuevavisionodoo)
cd /opt/odoo/custom_addons/nesto_sync
git pull origin main
sudo systemctl restart odoo
```

---

## 📋 Checklist de Verificación Antes de Trabajar

Antes de ejecutar CUALQUIER comando, verificar:

- [ ] ¿En qué servidor estoy?
  ```bash
  hostname
  # Odoo18 → DESARROLLO
  # nuevavisionodoo → PRODUCCIÓN
  ```

- [ ] ¿En qué directorio estoy?
  ```bash
  pwd
  # /opt/odoo16/custom_addons/nesto_sync → DESARROLLO
  # /opt/odoo/custom_addons/nesto_sync → PRODUCCIÓN
  ```

- [ ] ¿Qué servicio de Odoo corre aquí?
  ```bash
  systemctl list-units | grep odoo
  # odoo16.service → DESARROLLO
  # odoo.service → PRODUCCIÓN (probablemente)
  ```

- [ ] Si voy a hacer cambios, ¿estoy en DESARROLLO?
  - ✅ Sí → Puedo modificar código
  - ❌ No, estoy en PRODUCCIÓN → SOLO git pull, NUNCA modificar archivos

---

## 🔑 Credenciales y Configuración

### Desarrollo (Odoo18)

**Credenciales Google Cloud**:
```bash
/opt/odoo16/secrets/google-cloud-credentials.json
```

**Variable de entorno** (en `/etc/systemd/system/odoo16.service`):
```ini
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/odoo16/secrets/google-cloud-credentials.json"
```

**System Parameters** (en base de datos `odoo16`):
- `nesto_sync.google_project_id` = `nestomaps-1547636206945`
- `nesto_sync.pubsub_topic` = `sincronizacion-tablas`

### Producción (nuevavisionodoo)

**⚠️ PENDIENTE DE CONFIGURAR** (según [PROXIMA_SESION.md](PROXIMA_SESION.md)):

1. Copiar credenciales:
   ```bash
   sudo mkdir -p /opt/odoo/secrets
   sudo cp [origen] /opt/odoo/secrets/google-cloud-credentials.json
   sudo chmod 600 /opt/odoo/secrets/google-cloud-credentials.json
   ```

2. Configurar variable de entorno en systemd

3. Configurar System Parameters en la base de datos de producción

---

## 📞 Información de Contacto por Servidor

### DESARROLLO (Odoo18)
- **SSH**: `ssh azureuser@[IP-desarrollo]`
- **Path**: `/opt/odoo16/custom_addons/nesto_sync`
- **Servicio**: `sudo systemctl status odoo16`
- **Logs**: `sudo journalctl -u odoo16 -f`
- **Base de datos**: `odoo16`

### PRODUCCIÓN (nuevavisionodoo)
- **SSH**: `ssh root@217.61.212.170` o `ssh root@nuevavisionodoo`
- **URL**: `https://sede.nuevavision.es`
- **Path**: `/opt/odoo/custom_addons/nesto_sync`
- **Config**: `/etc/odoo/odoo.conf`
- **Servicio**: `sudo systemctl status odoo`
- **Logs**: `/var/log/odoo/odoo-server.log` o `sudo journalctl -u odoo -f`
- **Base de datos**: `odoo_nv`

---

## 🎯 Resumen Visual

```
┌─────────────────────────────────────────────────────────────┐
│                     DESARROLLO (Odoo18)                     │
├─────────────────────────────────────────────────────────────┤
│ Hostname: Odoo18                                            │
│ Path: /opt/odoo16/custom_addons/nesto_sync                  │
│ Servicio: odoo16.service                                    │
│ Virtualenv: /opt/odoo16/odoo-venv                           │
│                                                             │
│ Aquí se hacen TODOS los cambios                            │
│ Luego: git push origin main                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
                      git push/pull
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                PRODUCCIÓN (nuevavisionodoo)                 │
├─────────────────────────────────────────────────────────────┤
│ Hostname: nuevavisionodoo                                   │
│ URL: sede.nuevavision.es                                    │
│ IP: 217.61.212.170                                          │
│ Usuario: root                                               │
│ Path: /opt/odoo/custom_addons/nesto_sync  ⚠️ DIFERENTE     │
│ Servicio: odoo.service (verificar)                          │
│ Instalación: Sistema (/usr/bin/odoo)                        │
│                                                             │
│ Aquí SOLO git pull                                          │
│ NUNCA modificar archivos directamente                       │
└─────────────────────────────────────────────────────────────┘
```

---

**Fecha de creación**: 2025-11-11
**Autor**: Claude Code
**Motivo**: Evitar confusión entre servidores que causó problemas en sesiones anteriores
