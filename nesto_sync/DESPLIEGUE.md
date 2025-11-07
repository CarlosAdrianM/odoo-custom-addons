# Guía de Despliegue - Nesto Sync

**Fecha**: 2025-11-07
**Commit**: fd4f2a3
**Estado**: ✅ Código commiteado, pendiente push

## 🚨 IMPORTANTE: Push Manual Requerido

El código ya está commiteado localmente pero **necesita ser pusheado al repositorio remoto**:

```bash
cd /opt/odoo16/custom_addons/nesto_sync
git push origin main
```

Si solicita credenciales, usar token de GitHub personal.

## 📦 Contenido del Commit

**Commit**: `fd4f2a3 - feat: Implementar arquitectura extensible con tests completos`

### Archivos Nuevos (30 archivos)
- **Documentación** (8): ARQUITECTURA_EXTENSIBLE.md, ESTADO_ACTUAL.md, IMPLEMENTACION_ARQUITECTURA.md, PRODUCCION_READY.md, PROMPT_NESTOAPI.md, ROADMAP.md, SESION_2025-11-07.md, TESTING.md
- **Core** (4): core/entity_registry.py, core/generic_processor.py, core/generic_service.py, core/__init__.py
- **Config** (2): config/entity_configs.py, config/__init__.py
- **Transformers** (4): transformers/field_transformers.py, transformers/validators.py, transformers/post_processors.py, transformers/__init__.py
- **Legacy** (3): legacy/client_processor.py, legacy/client_service.py, legacy/__init__.py
- **Tests** (5): test_transformers.py, test_validators.py, test_post_processors.py, test_generic_service.py, test_integration_end_to_end.py

### Archivos Modificados (4)
- __init__.py: Importar nueva arquitectura
- models/__init__.py: Ajustes de imports
- controllers/controllers.py: Usar EntityRegistry
- tests/__init__.py: Importar nuevos tests

## 🚀 Pasos de Despliegue

### Pre-requisitos
- [x] Código commiteado localmente (commit fd4f2a3)
- [ ] Código pusheado a GitHub
- [ ] Tests ejecutados (105/105 pasando)
- [ ] Backup de base de datos realizado

### 1. Push al Repositorio (PENDIENTE)

```bash
cd /opt/odoo16/custom_addons/nesto_sync
git push origin main
```

Verificar en GitHub que el commit fd4f2a3 está visible.

### 2. Backup de Base de Datos

**CRÍTICO**: Hacer backup antes de cualquier despliegue.

```bash
# Backup completo
pg_dump -U odoo odoo_prod > /backup/odoo_prod_$(date +%Y%m%d_%H%M%S).sql

# O backup solo de nesto_sync tables
pg_dump -U odoo odoo_prod -t res_partner > /backup/res_partner_$(date +%Y%m%d_%H%M%S).sql
```

### 3. Actualizar Código en Servidor de Producción

```bash
# SSH al servidor de producción
ssh user@odoo-prod-server

# Navegar al directorio de addons
cd /opt/odoo16/custom_addons/nesto_sync

# Backup del código actual (por si acaso)
cp -r /opt/odoo16/custom_addons/nesto_sync /opt/odoo16/custom_addons/nesto_sync.backup_$(date +%Y%m%d)

# Pull del código
git pull origin main

# Verificar que estamos en el commit correcto
git log -1 --oneline
# Debe mostrar: fd4f2a3 feat: Implementar arquitectura extensible con tests completos
```

### 4. Verificar Idioma Español (Opcional)

Si el campo `_lang` en producción necesita `es_ES`:

```bash
# Opción A: Instalar español en Odoo (recomendado para producción)
# Desde UI: Ajustes → Traducciones → Cargar una traducción → Español

# Opción B: Descomentar campo _lang en entity_configs.py (ya está comentado)
```

**Nota**: El código actual tiene `_lang` comentado para compatibilidad. Si español está instalado, se puede descomentar.

### 5. Actualizar Módulo en Odoo

```bash
# Activar virtualenv
source /opt/odoo16/odoo-venv/bin/activate

# Método 1: Odoo CLI (recomendado, más seguro)
cd /opt/odoo16
python3 odoo-bin -c /etc/odoo/odoo.conf -d odoo_prod -u nesto_sync --stop-after-init

# Método 2: Desde UI (más lento pero visible)
# Aplicaciones → Actualizar lista de aplicaciones
# Buscar "Nesto Sync" → Actualizar
```

**Importante**: Usar `--stop-after-init` evita que el servidor se quede corriendo en modo CLI.

### 6. Reiniciar Odoo (si es necesario)

```bash
# Solo si usaste actualización por UI o si hay problemas
sudo systemctl restart odoo
```

### 7. Verificar Funcionamiento

#### 7.1. Verificar Logs
```bash
# Monitorear logs en tiempo real
tail -f /var/log/odoo/odoo-server.log | grep nesto_sync

# Buscar errores
grep -i "error.*nesto_sync" /var/log/odoo/odoo-server.log | tail -20
```

#### 7.2. Probar con Mensaje de Nesto

Desde NestoAPI, enviar un mensaje de prueba a `/nesto_sync`.

**Logs esperados**:
```
INFO ... odoo.addons.nesto_sync.core.generic_processor: Procesando mensaje de tipo cliente
INFO ... odoo.addons.nesto_sync.core.generic_service: Creando nuevo res.partner
INFO ... odoo.addons.nesto_sync.core.generic_service: res.partner creado con ID: XXX
```

#### 7.3. Verificar Anti-Bucle

Enviar el **mismo mensaje otra vez**.

**Logs esperados**:
```
INFO ... odoo.addons.nesto_sync.core.generic_service: Sin cambios en res.partner, omitiendo actualización
```

#### 7.4. Verificar en UI de Odoo

1. Ir a **Contactos** en Odoo
2. Buscar el cliente por nombre o cliente_externo
3. Verificar que todos los campos estén correctos:
   - Nombre
   - Dirección
   - Teléfonos (mobile, phone)
   - Email (del primer PersonaContacto)
   - NIF
   - Ciudad, código postal
   - Activo/Inactivo según Estado

4. Verificar que tiene children (PersonasContacto):
   - Ir a la pestaña "Contactos e Direcciones"
   - Deben aparecer las PersonasContacto como contactos tipo "Contacto"

### 8. Ejecutar Tests en Servidor (Opcional pero Recomendado)

```bash
# Activar virtualenv
source /opt/odoo16/odoo-venv/bin/activate

# Ejecutar tests en base de test
cd /opt/odoo16
python3 odoo-bin -c /etc/odoo/odoo.conf -d odoo_test -u nesto_sync --test-enable --stop-after-init

# Verificar resultado
# Debe mostrar: "0 failed, 0 error(s) of 105 tests"
```

## 🔍 Verificación de Despliegue

### Checklist Post-Despliegue

- [ ] Push a GitHub completado (commit fd4f2a3 visible)
- [ ] Backup de BD realizado
- [ ] Código actualizado en servidor (git pull)
- [ ] Módulo actualizado en Odoo (-u nesto_sync)
- [ ] Logs sin errores
- [ ] Mensaje de prueba procesado correctamente
- [ ] Anti-bucle funciona (segundo mensaje = "Sin cambios")
- [ ] Cliente visible en UI de Odoo con todos los campos
- [ ] PersonasContacto visibles como children
- [ ] Tests ejecutados en servidor (opcional)

## 🆘 Troubleshooting

### Error: "Module nesto_sync could not be loaded"

**Causa**: Archivos Python con errores de sintaxis o imports faltantes.

**Solución**:
```bash
# Verificar logs
grep -A 20 "could not be loaded" /var/log/odoo/odoo-server.log

# Verificar sintaxis Python
python3 -m py_compile /opt/odoo16/custom_addons/nesto_sync/core/*.py
```

### Error: "Wrong value for res.partner.lang: 'es_ES'"

**Causa**: Idioma español no instalado en Odoo.

**Solución**:
- Opción A: Instalar español desde UI (Ajustes → Traducciones)
- Opción B: El código ya tiene `_lang` comentado, no debería ocurrir

### Error: "No module named 'transformers'"

**Causa**: Import incorrecto o archivos `__init__.py` faltantes.

**Solución**:
```bash
# Verificar que existen todos los __init__.py
ls -la /opt/odoo16/custom_addons/nesto_sync/*/___init__.py

# Si faltan, crear:
touch /opt/odoo16/custom_addons/nesto_sync/transformers/__init__.py
```

### Error: "Cliente principal no existe"

**Causa**: Intentando crear cliente de entrega antes que cliente principal.

**Solución**: Orden correcto:
1. Enviar cliente principal primero (ClientePrincipal=True)
2. Luego enviar clientes de entrega (ClientePrincipal=False)

### Logs muestran "Sin cambios" pero debería actualizar

**Causa**: Detección de cambios demasiado estricta o campo HTML.

**Solución**:
```bash
# Ver logs detallados de comparación
grep "Comparando campo" /var/log/odoo/odoo-server.log | tail -50

# Si es campo HTML, verificar que generic_service.py tiene la lógica HTML
grep -A 10 "field_type == 'html'" /opt/odoo16/custom_addons/nesto_sync/core/generic_service.py
```

## 🔄 Rollback (Si es necesario)

Si hay problemas graves, hacer rollback:

```bash
# 1. Detener Odoo
sudo systemctl stop odoo

# 2. Restaurar código anterior
cd /opt/odoo16/custom_addons
rm -rf nesto_sync
mv nesto_sync.backup_YYYYMMDD nesto_sync

# 3. Restaurar base de datos (solo si es necesario)
psql -U odoo odoo_prod < /backup/odoo_prod_YYYYMMDD_HHMMSS.sql

# 4. Reiniciar Odoo
sudo systemctl start odoo
```

## 📊 Métricas a Monitorizar

### Logs a Revisar Regularmente

```bash
# Mensajes procesados hoy
grep "Procesando mensaje de tipo cliente" /var/log/odoo/odoo-server.log | grep "$(date +%Y-%m-%d)" | wc -l

# Creaciones hoy
grep "res.partner creado con ID" /var/log/odoo/odoo-server.log | grep "$(date +%Y-%m-%d)" | wc -l

# Actualizaciones hoy
grep "res.partner actualizado: ID" /var/log/odoo/odoo-server.log | grep "$(date +%Y-%m-%d)" | wc -l

# Sin cambios (anti-bucle funcionando)
grep "Sin cambios en res.partner" /var/log/odoo/odoo-server.log | grep "$(date +%Y-%m-%d)" | wc -l

# Errores hoy
grep -i "error.*nesto_sync" /var/log/odoo/odoo-server.log | grep "$(date +%Y-%m-%d)" | wc -l
```

### Performance

```bash
# Tiempo promedio de procesamiento (requiere logs con timestamps)
# Buscar patrón: "Procesando mensaje" hasta "res.partner creado"
```

## 📞 Contacto

Si hay problemas durante el despliegue:

1. Revisar logs: `/var/log/odoo/odoo-server.log`
2. Ejecutar tests: `python3 odoo-bin ... --test-enable`
3. Comparar con código legacy: `/opt/odoo16/custom_addons/nesto_sync/legacy/`
4. Consultar documentación: `PRODUCCION_READY.md`, `TESTING.md`

## 📝 Notas Adicionales

### Compatibilidad con NestoAPI

**No es necesario tocar NestoAPI para este despliegue**. La nueva arquitectura mantiene:
- Mismo endpoint: `/nesto_sync`
- Mismo formato de mensaje (PubSub base64)
- Mismos campos esperados
- Misma respuesta HTTP

### Próximos Pasos (Futuras Sesiones)

Una vez validado en producción:
1. Sincronización bidireccional (Odoo → Nesto)
2. Nuevas entidades (Proveedores, Productos, Pedidos)
3. Optimizaciones de performance

---

**Documento creado**: 2025-11-07
**Última actualización**: 2025-11-07
**Commit desplegado**: fd4f2a3 (pendiente push)
**Estado**: ✅ Listo para desplegar (requiere push primero)
