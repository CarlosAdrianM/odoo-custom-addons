# Guía de Despliegue v2.6.0

## 🚀 Despliegue en Producción

### Pre-requisitos
- [x] Backup de la base de datos
- [x] Acceso SSH al servidor de producción
- [x] Permisos sudo
- [x] Git configurado

---

## 📦 Paso 1: Hacer Pull de los Cambios

```bash
# Conectar al servidor de producción
ssh usuario@servidor-produccion

# Navegar al directorio del módulo
cd /ruta/al/modulo/nesto_sync

# Verificar rama actual
git branch

# Hacer pull de los cambios
git pull origin main

# Verificar que se descargaron los 4 commits de v2.6.0
git log --oneline -5
```

**Commits esperados:**
```
25855b4 chore: Ignorar archivos de test locales
fb4d345 chore: Actualizar versión a 2.6.0 con changelog completo
e36c4a8 feat: Implementar transformers inversos completos para productos
100dc51 feat: Campo volume_ml para almacenar volumen sin pérdida de precisión
```

---

## 🗄️ Paso 2: Actualizar el Módulo en Odoo

```bash
# Marcar módulo para actualización
sudo -u postgres psql -d <nombre_base_datos> -c \
  "UPDATE ir_module_module SET state = 'to upgrade' WHERE name = 'nesto_sync';"
```

**Salida esperada:**
```
UPDATE 1
```

---

## 🔄 Paso 3: Reiniciar Odoo

```bash
# Reiniciar servicio
sudo systemctl restart odoo

# Verificar que esté activo
sudo systemctl status odoo

# Ver logs en tiempo real (Ctrl+C para salir)
sudo journalctl -u odoo -f
```

**Logs esperados:**
```
INFO ... Upgrading module nesto_sync
INFO ... Module nesto_sync upgraded successfully
```

---

## ✅ Paso 4: Verificar Actualización

```bash
# Verificar que el campo volume_ml se creó
sudo -u postgres psql -d <nombre_base_datos> -c \
  "SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'product_template'
   AND column_name = 'volume_ml';"
```

**Salida esperada:**
```
 column_name | data_type
-------------+-----------
 volume_ml   | numeric
(1 row)
```

---

## 🔄 Paso 5: Migración de Datos (OPCIONAL)

**SOLO ejecutar si hay productos con volumen ya guardados**

```bash
# Ejecutar script de migración
sudo -u postgres psql -d <nombre_base_datos> \
  -f /ruta/al/modulo/nesto_sync/docs/migration_v2.6.0.sql
```

**El script realizará:**
1. Verificación del campo `volume_ml`
2. Backup de datos existentes
3. Migración: `volume_ml = volume × 1,000,000`
4. Validación de coherencia
5. Resumen de resultados

**Tiempo estimado:** < 1 minuto (para ~10,000 productos)

---

## 🧪 Paso 6: Pruebas de Validación

### 6.1. Verificar productos con volumen

```bash
sudo -u postgres psql -d <nombre_base_datos> << 'EOF'
SELECT
    default_code,
    volume_ml,
    CASE
        WHEN volume_ml < 1000 THEN CONCAT(volume_ml, ' ml')
        ELSE CONCAT((volume_ml / 1000)::numeric(16,2), ' l')
    END as volume_display
FROM product_template
WHERE volume_ml > 0
ORDER BY volume_ml DESC
LIMIT 10;
EOF
```

### 6.2. Probar sincronización Odoo → Nesto

1. Abrir Odoo en el navegador
2. Ir a Inventario → Productos
3. Editar un producto existente (cambiar nombre o precio)
4. Guardar
5. Verificar logs de publicación:

```bash
sudo journalctl -u odoo -f | grep "📨 Publicando producto"
```

**Log esperado:**
```
📨 Publicando producto desde Odoo: product.template ID 123
```

### 6.3. Verificar mensaje PubSub

```bash
# Ver últimos logs con "Tamanno" y "UnidadMedida"
sudo journalctl -u odoo --since "5 minutes ago" | grep -E "Tamanno|UnidadMedida"
```

**Debe mostrar campos correctos:**
```json
{
  "Tamanno": 50,
  "UnidadMedida": "ml",
  "Grupo": "Cosméticos"
}
```

---

## 🔍 Paso 7: Monitoreo Post-Despliegue

### Durante las primeras 24 horas:

```bash
# Ver logs de errores
sudo journalctl -u odoo --since "1 hour ago" -p err

# Ver logs de warnings
sudo journalctl -u odoo --since "1 hour ago" -p warning | grep nesto_sync

# Ver estadísticas de sincronización
sudo journalctl -u odoo --since "1 hour ago" | grep "📨 Publicando" | wc -l
```

---

## 🐛 Troubleshooting

### Problema 1: Campo `volume_ml` no se crea

**Síntoma:**
```
ERROR: column "volume_ml" does not exist
```

**Solución:**
```bash
# Verificar que el módulo está marcado para upgrade
sudo -u postgres psql -d <nombre_base_datos> -c \
  "SELECT name, state FROM ir_module_module WHERE name = 'nesto_sync';"

# Si state != 'to upgrade', marcarlo:
sudo -u postgres psql -d <nombre_base_datos> -c \
  "UPDATE ir_module_module SET state = 'to upgrade' WHERE name = 'nesto_sync';"

# Reiniciar Odoo
sudo systemctl restart odoo
```

### Problema 2: Errores en migración de datos

**Síntoma:**
```
ERROR: división por cero
ERROR: valor fuera de rango
```

**Solución:**
```bash
# Revisar tabla de backup
sudo -u postgres psql -d <nombre_base_datos> -c \
  "SELECT * FROM product_template_volume_backup_v260 LIMIT 10;"

# Restaurar datos si es necesario
sudo -u postgres psql -d <nombre_base_datos> -c \
  "UPDATE product_template pt
   SET volume_ml = NULL
   FROM product_template_volume_backup_v260 backup
   WHERE pt.id = backup.id;"
```

### Problema 3: Transformers inversos no funcionan

**Síntoma:**
```
WARNING ... Reverse transformer 'grupo' no implementado
```

**Solución:**
```bash
# Verificar versión del módulo
sudo -u postgres psql -d <nombre_base_datos> -c \
  "SELECT latest_version FROM ir_module_module WHERE name = 'nesto_sync';"

# Debe mostrar: 2.6.0

# Si no, forzar actualización:
sudo systemctl restart odoo --no-block
```

---

## ✅ Checklist de Despliegue

- [ ] Backup de base de datos realizado
- [ ] Pull de cambios desde Git
- [ ] Módulo marcado como 'to upgrade'
- [ ] Odoo reiniciado
- [ ] Campo `volume_ml` creado
- [ ] Migración de datos ejecutada (si aplicable)
- [ ] Pruebas de validación pasadas
- [ ] Logs monitoreados (sin errores)
- [ ] Sincronización Odoo → Nesto verificada
- [ ] Equipo notificado del despliegue

---

## 📞 Contacto de Emergencia

**Desarrollador:** Carlos Adrián Martínez

**En caso de problemas críticos:**
1. Detener servicio Odoo: `sudo systemctl stop odoo`
2. Restaurar backup de BD
3. Revertir cambios en Git: `git reset --hard HEAD~4`
4. Contactar al desarrollador

---

## 📊 Métricas de Éxito

**Indicadores a monitorear:**

| Métrica | Valor Esperado | Comando |
|---------|----------------|---------|
| Campo `volume_ml` existe | 1 row | Ver Paso 4 |
| Productos migrados | > 0 | Ver migration_v2.6.0.sql |
| Errores en logs (24h) | 0 | `journalctl -u odoo -p err` |
| Mensajes PubSub enviados | > 0 | `journalctl \| grep "📨"` |

---

## 🔄 Rollback (si es necesario)

**SOLO en caso de problemas graves**

```bash
# 1. Detener Odoo
sudo systemctl stop odoo

# 2. Restaurar backup de BD
sudo -u postgres psql -d <nombre_base_datos> < backup_pre_v2.6.0.sql

# 3. Revertir código
cd /ruta/al/modulo/nesto_sync
git reset --hard HEAD~4  # Revertir 4 commits

# 4. Reiniciar Odoo
sudo systemctl start odoo

# 5. Notificar al equipo
```

---

**Última actualización:** 2025-11-18
**Versión:** 2.6.0
