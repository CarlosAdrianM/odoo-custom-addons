# Instrucciones de Despliegue a Producción

## Servidor de Producción: nuevavisionodoo

**IP**: 217.61.212.170
**Usuario**: root
**Ruta del módulo**: `/opt/odoo/custom_addons/nesto_sync`

---

## Pasos para Desplegar

### 1. Push desde Servidor de Desarrollo (Odoo18)

Desde `/opt/odoo16/custom_addons/nesto_sync`:

```bash
# Verificar que todo está commiteado
git status

# Push al repositorio
git push origin main
```

### 2. Pull en Servidor de Producción

```bash
# Conectar al servidor de producción
ssh root@217.61.212.170

# Ir al directorio del módulo
cd /opt/odoo/custom_addons/nesto_sync

# Verificar rama actual
git branch

# Pull de los cambios
git pull origin main

# Verificar que se descargaron los cambios
git log --oneline -3
```

Deberías ver el commit:
```
15d4f18 feat: Corregir formato de mensajes bidireccionales Odoo → Nesto
```

### 3. Limpiar Cache de Python

```bash
# Limpiar archivos .pyc
find /opt/odoo/custom_addons/nesto_sync -type f -name "*.pyc" -delete

# Limpiar directorios __pycache__
find /opt/odoo/custom_addons/nesto_sync -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

echo "✅ Cache limpiado"
```

### 4. Actualizar Módulo en Odoo

```bash
# Actualizar módulo (esto recarga el código)
/opt/odoo/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /opt/odoo/odoo.conf \
  -d odoo \
  -u nesto_sync \
  --stop-after-init
```

Deberías ver:
```
INFO odoo.modules.loading: Module nesto_sync loaded in X.XXs
INFO odoo.modules.loading: Modules loaded.
```

### 5. Reiniciar Servicio Odoo

```bash
# Reiniciar servicio
sudo systemctl restart odoo

# Esperar unos segundos
sleep 5

# Verificar que está corriendo
sudo systemctl status odoo
```

Deberías ver:
```
Active: active (running) since ...
```

### 6. Verificar Logs

```bash
# Ver logs en tiempo real
sudo journalctl -u odoo -f
```

Busca líneas como:
- `⭐ ResPartner.write() llamado con vals: ...`
- `🔔 BidirectionalSyncMixin.write() llamado en res.partner ...`
- `📨 Mensaje a publicar: ...`
- `Publicando cliente desde Odoo: res.partner ID ...`

### 7. Prueba de Funcionamiento

Desde la UI de Odoo en producción:

1. Buscar un cliente (ej: cliente 15191)
2. Modificar un campo (ej: teléfono móvil)
3. Guardar
4. Verificar en los logs que se publicó el mensaje
5. Verificar en Nesto que se recibió la actualización

---

## Verificación de Formato de Mensaje

El mensaje publicado debe tener esta estructura:

```json
{
  "Cliente": "15191",
  "Contacto": "2",
  "ClientePrincipal": true,
  "Nombre": "...",
  "Direccion": "...",
  "Telefono": "666111222/912345678",
  "Provincia": "Madrid",
  "Estado": 9,
  "PersonasContacto": [
    {
      "Id": "1",
      "Nombre": "...",
      "Telefonos": "...",
      "Cargo": 22
    }
  ],
  "Tabla": "Clientes",
  "Source": "Odoo"
}
```

**Verificar**:
- ✅ Estructura plana (no Parent/Children)
- ✅ Campos en español
- ✅ Cliente, Contacto, Id presentes
- ✅ Telefono (singular) para parent
- ✅ Telefonos (plural) para children
- ✅ Cargo como número
- ✅ Provincia como string (no ID)
- ✅ Estado como número (9 o -1)
- ✅ ClientePrincipal como booleano

---

## Rollback (si es necesario)

Si algo falla:

```bash
# Volver al commit anterior
cd /opt/odoo/custom_addons/nesto_sync
git log --oneline -5
git reset --hard <commit-anterior>

# Actualizar módulo
/opt/odoo/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /opt/odoo/odoo.conf \
  -d odoo \
  -u nesto_sync \
  --stop-after-init

# Reiniciar servicio
sudo systemctl restart odoo
```

---

## Problemas Comunes

### Módulo no se actualiza
```bash
# Limpiar cache más agresivamente
rm -rf /opt/odoo/custom_addons/nesto_sync/__pycache__
rm -rf /opt/odoo/custom_addons/nesto_sync/*/__pycache__
find /opt/odoo/custom_addons/nesto_sync -name "*.pyc" -delete

# Reintentar actualización
/opt/odoo/venv/bin/python3 /opt/odoo/odoo-bin \
  -c /opt/odoo/odoo.conf \
  -d odoo \
  -u nesto_sync \
  --stop-after-init \
  --log-level=debug
```

### Servicio no arranca
```bash
# Ver logs de error
sudo journalctl -u odoo --since "5 minutes ago" | tail -100

# Verificar que no hay errores de sintaxis Python
python3 -m py_compile /opt/odoo/custom_addons/nesto_sync/core/odoo_publisher.py
python3 -m py_compile /opt/odoo/custom_addons/nesto_sync/config/entity_configs.py
```

### Mensajes no se publican
```bash
# Verificar que el mixin está activo
sudo journalctl -u odoo -f | grep -E '⭐|🔔|📨'

# Si no aparece nada, reiniciar servicio
sudo systemctl restart odoo
```

---

## Contacto

Si hay problemas durante el despliegue:
- Revisar `/opt/odoo/custom_addons/nesto_sync/CHANGELOG_SESION_2025-11-11.md`
- Revisar logs: `sudo journalctl -u odoo --since "10 minutes ago"`
