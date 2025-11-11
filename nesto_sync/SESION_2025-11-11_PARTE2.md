# Sesión 2025-11-11 (Parte 2) - Clarificación de Servidores y Documentación

**Fecha**: 2025-11-11
**Servidor de trabajo**: Odoo18 (DESARROLLO)
**Estado**: ✅ **DOCUMENTACIÓN COMPLETADA - Servidores clarificados**

---

## 🎯 Problema Principal

Durante la sesión hubo confusión entre los dos servidores:
- **DESARROLLO** (Odoo18): Donde se hacen los cambios
- **PRODUCCIÓN** (nuevavisionodoo): Donde el usuario reportó el Error 500

El asistente estaba trabajando en el servidor de desarrollo pensando que era producción.

---

## 📝 Solución Implementada

### 1. Creado archivo [SERVIDORES.md](SERVIDORES.md)

**Propósito**: Documentación completa para evitar confusiones futuras

**Contenido**:
- Descripción detallada de cada servidor (hostname, IP, rutas, servicios)
- Cómo identificar en qué servidor estás
- Flujo de trabajo correcto (desarrollo → producción)
- Errores comunes y cómo evitarlos
- Checklist de verificación antes de trabajar
- Información de credenciales y configuración por servidor
- Diagrama visual de la arquitectura

**Información clave documentada**:

| Aspecto | DESARROLLO (Odoo18) | PRODUCCIÓN (nuevavisionodoo) |
|---------|---------------------|------------------------------|
| **Hostname** | `Odoo18` | `nuevavisionodoo` |
| **URL** | - | `sede.nuevavision.es` |
| **IP** | (no especificada) | `217.61.212.170` |
| **Usuario SSH** | `azureuser` (probablemente) | `root` |
| **Path módulo** | `/opt/odoo16/custom_addons/nesto_sync` | `/opt/odoo/custom_addons/nesto_sync` ⚠️ |
| **Servicio** | `odoo16.service` | `odoo.service` (verificar) |
| **Odoo** | Virtualenv: `/opt/odoo16/odoo-venv` | Sistema: `/usr/bin/odoo` |
| **Base de datos** | `odoo16` | (consultar con usuario) |

**Diferencia crítica**: El path es DIFERENTE:
- Desarrollo: `/opt/odoo16/custom_addons/nesto_sync`
- Producción: `/opt/odoo/custom_addons/nesto_sync`

### 2. Actualizado [ESTADO_DESPLIEGUE.md](ESTADO_DESPLIEGUE.md)

**Cambios realizados**:

1. **Encabezado actualizado** (líneas 3-10):
   - Clarificado que estamos en servidor de DESARROLLO
   - Añadido estado: "PENDIENTE DESPLEGAR A PRODUCCIÓN"
   - Referencia a [SERVIDORES.md](SERVIDORES.md)

2. **Sección "Estado Actual: DOS SERVIDORES"** (líneas 156-175):
   - Añadido hostname, IP y URL de cada servidor
   - Aclarado que producción tiene Error 500 por falta de librería
   - Marcado que producción tiene código desactualizado

3. **Nueva sección al final** (líneas 387-444):
   - "Actualización 2025-11-11 (Segunda Parte): Clarificación de Servidores"
   - Problema detectado durante la sesión
   - Documentación creada
   - Estado actual de producción (pendiente)
   - Checklist para próxima sesión

---

## 🔍 Estado Actual de Cada Servidor

### DESARROLLO (Odoo18) ✅

**Estado**: Completamente funcional

```
Hostname: Odoo18
Path: /opt/odoo16/custom_addons/nesto_sync
Servicio: odoo16.service - Active (running)
```

**Verificado**:
- ✅ Código actualizado (commit `74c4dfa`)
- ✅ Librería `google-cloud-pubsub` instalada en virtualenv
- ✅ Módulo `nesto_sync` cargado sin errores
- ✅ Servicio corriendo sin problemas
- ✅ Logs sin errores

**Logs verificados**:
```
2025-11-11 09:02:05,006 - Module nesto_sync loaded in 1.82s, 0 queries
```

### PRODUCCIÓN (nuevavisionodoo) ❌

**Estado**: Error 500 - Pendiente de despliegue

```
Hostname: nuevavisionodoo
URL: sede.nuevavision.es
IP: 217.61.212.170
Usuario: root
Path: /opt/odoo/custom_addons/nesto_sync
```

**Problemas identificados**:
1. ❌ **Error 500 al acceder por navegador**
   - Causa: Falta librería `google-cloud-pubsub`
   - El código nuevo importa `google.cloud.pubsub_v1` pero la librería no está instalada

2. ❌ **Código desactualizado**
   - El fix de serialización (`74c4dfa`) NO está en producción
   - Necesita: `git pull` desde el directorio correcto

3. ❌ **Credenciales Google Cloud no configuradas**
   - Archivo de credenciales no existe
   - Variable de entorno no configurada en systemd
   - System Parameters no configurados

**NO se pudo acceder al servidor de producción** durante esta sesión porque el asistente estaba en desarrollo.

---

## 🚀 Próximos Pasos para Producción

Ver [PROXIMA_SESION.md](PROXIMA_SESION.md) para guía completa.

### Resumen rápido:

1. **Conectar a producción**:
   ```bash
   ssh root@217.61.212.170
   hostname  # Verificar: nuevavisionodoo
   ```

2. **Resolver Error 500** (instalar librería):
   ```bash
   pip3 install --break-system-packages google-cloud-pubsub
   ```

3. **Actualizar código**:
   ```bash
   cd /opt/odoo/custom_addons/nesto_sync
   git pull origin main
   find . -type f -name "*.pyc" -delete
   ```

4. **Actualizar módulo**:
   ```bash
   # Verificar nombre del servicio primero
   systemctl list-units | grep odoo

   # Actualizar módulo (verificar nombre de BD)
   python3 /usr/bin/odoo -c /opt/odoo/odoo.conf -d [NOMBRE_BD] -u nesto_sync --stop-after-init

   # Reiniciar
   sudo systemctl restart odoo
   ```

5. **Configurar credenciales** (después de que funcione):
   - Copiar archivo de credenciales
   - Configurar variable de entorno en systemd
   - Configurar System Parameters

---

## 📚 Archivos Modificados/Creados

### Archivos Nuevos

1. **[SERVIDORES.md](SERVIDORES.md)** (nuevo)
   - Documentación completa de servidores
   - Flujo de trabajo
   - Errores comunes

2. **[SESION_2025-11-11_PARTE2.md](SESION_2025-11-11_PARTE2.md)** (este archivo)
   - Resumen de la sesión
   - Clarificación de la confusión
   - Próximos pasos

### Archivos Modificados

1. **[ESTADO_DESPLIEGUE.md](ESTADO_DESPLIEGUE.md)**
   - Líneas 3-10: Encabezado actualizado
   - Líneas 156-175: Sección "DOS SERVIDORES" mejorada
   - Líneas 387-444: Nueva sección con estado actual

---

## 🎯 Aprendizajes de la Sesión

### Problema Raíz

**Confusión de contexto**: El asistente estaba en el servidor de desarrollo (Odoo18) pero el usuario reportaba problemas en producción (nuevavisionodoo).

**Causas**:
1. Nombres similares de paths (`/opt/odoo16` vs `/opt/odoo`)
2. Mismo nombre de servicio en ambos (`odoo16.service`)
3. Falta de verificación del hostname al inicio

### Solución

**Documentación clara**: [SERVIDORES.md](SERVIDORES.md) con:
- Tabla comparativa de servidores
- Checklist de verificación ANTES de trabajar
- Comandos para identificar servidor actual

### Prevención Futura

**Antes de ejecutar CUALQUIER comando**:
```bash
# 1. ¿Dónde estoy?
hostname

# 2. ¿En qué directorio?
pwd

# 3. ¿Qué servicio corre?
systemctl list-units | grep odoo
```

Si `hostname` = `Odoo18` → Estás en DESARROLLO
Si `hostname` = `nuevavisionodoo` → Estás en PRODUCCIÓN

---

## 📊 Comparación: Antes vs Después

### ANTES (problemas)

- ❌ No había documentación clara de servidores
- ❌ Confusión entre desarrollo y producción
- ❌ Paths similares causaban confusión (`/opt/odoo16` vs `/opt/odoo`)
- ❌ No se verificaba hostname antes de trabajar

### DESPUÉS (solución)

- ✅ [SERVIDORES.md](SERVIDORES.md) documenta TODO
- ✅ Tabla comparativa clara de diferencias
- ✅ Checklist de verificación obligatorio
- ✅ Errores comunes documentados
- ✅ Diagrama visual de arquitectura
- ✅ [ESTADO_DESPLIEGUE.md](ESTADO_DESPLIEGUE.md) actualizado con estado real

---

## 🔧 Troubleshooting para la Próxima Sesión

### Si aparece "Error 500" en producción

**NO es un problema del código**, es falta de librería.

**Solución**:
```bash
# En producción (nuevavisionodoo)
pip3 install --break-system-packages google-cloud-pubsub
sudo systemctl restart odoo
```

### Si dice "no such file or directory" en producción

Probablemente estás en el directorio incorrecto.

**Verificar**:
```bash
pwd
# Debe mostrar: /opt/odoo/custom_addons/nesto_sync
# SI muestra /opt/odoo16/... → Estás en el servidor equivocado
```

### Si no hay logs de nesto_sync en producción

El módulo no está cargado o el código es antiguo.

**Solución**:
```bash
cd /opt/odoo/custom_addons/nesto_sync
git pull origin main
python3 /usr/bin/odoo -c /opt/odoo/odoo.conf -d [NOMBRE_BD] -u nesto_sync --stop-after-init
sudo systemctl restart odoo
```

---

## ✅ Checklist de la Sesión

- [x] Identificado problema: confusión entre servidores
- [x] Creado [SERVIDORES.md](SERVIDORES.md) con documentación completa
- [x] Actualizado [ESTADO_DESPLIEGUE.md](ESTADO_DESPLIEGUE.md) con estado real
- [x] Verificado estado del servidor de desarrollo (Odoo18) - ✅ OK
- [x] Documentado problema de producción (Error 500 por librería)
- [x] Documentado próximos pasos para producción
- [x] Creado este resumen de sesión
- [ ] **PENDIENTE**: Conectar a producción y resolver Error 500
- [ ] **PENDIENTE**: Actualizar código en producción
- [ ] **PENDIENTE**: Configurar credenciales en producción

---

## 📞 Información de Contacto Rápida

### Para la próxima sesión, conectar a:

**PRODUCCIÓN**:
```bash
ssh root@217.61.212.170
# o
ssh root@nuevavisionodoo
```

**Verificar siempre**:
```bash
hostname  # Debe mostrar: nuevavisionodoo
pwd       # Debe estar en: /opt/odoo/custom_addons/nesto_sync
```

---

**Sesión completada**: 2025-11-11
**Por**: Claude Code
**Archivo clave creado**: [SERVIDORES.md](SERVIDORES.md)
**Estado**: ✅ Documentación lista, pendiente despliegue a producción
**Próxima acción**: Conectar a producción (nuevavisionodoo) y seguir [PROXIMA_SESION.md](PROXIMA_SESION.md)
