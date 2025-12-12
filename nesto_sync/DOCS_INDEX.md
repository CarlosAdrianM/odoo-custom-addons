# Índice de Documentación - Nesto Sync

> Última actualización: 2025-12-12

## 📋 Documentación Principal

### Guías de Usuario
- [README.md](README.md) - Descripción general del módulo
- [ROADMAP.md](ROADMAP.md) - **Hoja de ruta y pendientes del proyecto**
- [CHANGELOG.md](CHANGELOG.md) - Historial de cambios

### Arquitectura y Diseño
- [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md) - Diseño del sistema extensible
- [IMPLEMENTACION_ARQUITECTURA.md](IMPLEMENTACION_ARQUITECTURA.md) - Detalles de implementación
- [PROMPT_NESTOAPI.md](PROMPT_NESTOAPI.md) - Especificaciones para NestoAPI

### Despliegue y Configuración
- [PRODUCCION_READY.md](PRODUCCION_READY.md) - Checklist de producción
- [DESPLIEGUE.md](DESPLIEGUE.md) - Guía general de despliegue
- [CONFIGURACION_CREDENCIALES.md](CONFIGURACION_CREDENCIALES.md) - Configurar Google Cloud
- [SERVIDORES.md](SERVIDORES.md) - Información de servidores (desarrollo/producción)
- [INSTRUCCIONES_DESPLIEGUE_PRODUCCION.md](INSTRUCCIONES_DESPLIEGUE_PRODUCCION.md) - Pasos para producción

### Testing
- [TESTING.md](TESTING.md) - Guía de testing
- [docs/TESTING.md](docs/TESTING.md) - Tests detallados

### Troubleshooting
- [TROUBLESHOOTING_PRODUCCION.md](TROUBLESHOOTING_PRODUCCION.md) - Solución de problemas

## 🚀 Versiones y Releases

### v2.8.0 - BOM Sync
- [docs/BOM_SYNC.md](docs/BOM_SYNC.md) - Sincronización de BOMs (ProductosKit)
- [docs/SESSION_SUMMARY_2025-11-20.md](docs/SESSION_SUMMARY_2025-11-20.md) - Resumen de sesión

### v2.7.0 - Dead Letter Queue (DLQ)
- [CHANGELOG_v2.7.0.md](CHANGELOG_v2.7.0.md) - Changelog detallado
- [docs/DLQ_SYSTEM.md](docs/DLQ_SYSTEM.md) - Sistema de mensajes fallidos
- [docs/SESSION_SUMMARY_2025-11-19.md](docs/SESSION_SUMMARY_2025-11-19.md) - Resumen de sesión

### v2.6.0 - Mejoras de Productos
- [docs/README_v2.6.0.md](docs/README_v2.6.0.md) - Resumen de la versión
- [docs/DEPLOY_v2.6.0.md](docs/DEPLOY_v2.6.0.md) - Guía de despliegue
- [docs/sesion_2025-11-18_v2.6.0.md](docs/sesion_2025-11-18_v2.6.0.md) - Sesión de desarrollo
- [docs/migration_v2.6.0.sql](docs/migration_v2.6.0.sql) - Script de migración

### v2.5.0 - Sincronización de Productos
- [RESUMEN_SESION_2025-11-17_PARTE2.md](RESUMEN_SESION_2025-11-17_PARTE2.md)
- [SINCRONIZACION_PRODUCTOS.md](SINCRONIZACION_PRODUCTOS.md)

### v2.4.0 - Arquitectura Extensible
- [DESPLIEGUE_V2.4.0.md](DESPLIEGUE_V2.4.0.md)
- [CHANGELOG_SESION_2025-11-11.md](CHANGELOG_SESION_2025-11-11.md)

## 📝 Sesiones de Desarrollo

- [SESION_2025-11-17.md](SESION_2025-11-17.md) - Productos y triggers
- [SESION_2025-11-11_PARTE2.md](SESION_2025-11-11_PARTE2.md) - Refactoring
- [SESION_2025-11-11.md](SESION_2025-11-11.md) - Bidirectional sync
- [SESION_2025-11-10.md](SESION_2025-11-10.md) - Serialización JSON
- [SESION_2025-11-07.md](SESION_2025-11-07.md) - Arquitectura extensible

## 🔧 Archivos Técnicos

### Scripts SQL
- [TRIGGER_PRODUCTOS_ACTUALIZADO.sql](TRIGGER_PRODUCTOS_ACTUALIZADO.sql) - Trigger de productos
- [docs/migration_v2.6.0.sql](docs/migration_v2.6.0.sql) - Migración v2.6.0

### Debugging
- [DEBUG_PRODUCTO_35894.md](DEBUG_PRODUCTO_35894.md) - Debug de producto específico
- [FIX_LOGS_IMAGENES.md](FIX_LOGS_IMAGENES.md) - Fix de logs con imágenes
- [COMPARACION_TRIGGER_PRODUCTOS.md](COMPARACION_TRIGGER_PRODUCTOS.md) - Comparación de triggers

## 🎯 Próximos Pasos

- [PROXIMA_SESION.md](PROXIMA_SESION.md) - **Tareas pendientes para la próxima sesión**
- [ROADMAP.md](ROADMAP.md) - **Issues pendientes y hoja de ruta**

## ⚠️ Estado Actual

### ✅ Completado
- Arquitectura extensible
- Sincronización Nesto → Odoo (clientes, productos, BOMs)
- Sincronización Odoo → Nesto (bidireccional)
- Sistema DLQ para mensajes fallidos
- Tests automatizados (105 tests)

### 🚧 Pendiente

#### 1. **Sincronización a Producción** (Alta Prioridad)
Código funcional en desarrollo (Odoo18), pendiente de desplegar a producción (nuevavisionodoo)
- Ver: [PROXIMA_SESION.md](PROXIMA_SESION.md)

#### 2. **Reprocesamiento Automático DLQ**
Sistema de reintentos automáticos para mensajes fallidos
- Ver: [models/failed_message.py:129](models/failed_message.py#L129)
- Ver: [docs/DLQ_SYSTEM.md](docs/DLQ_SYSTEM.md#TODO)

#### 3. **Dashboard de Métricas**
Panel para visualizar estadísticas de sincronización
- Ver: [docs/DLQ_SYSTEM.md](docs/DLQ_SYSTEM.md#TODO)

#### 4. **Expansión a Nuevas Entidades**
- Proveedores (res.partner con supplier_rank)
- Seguimientos de clientes
- Ver: [ROADMAP.md](ROADMAP.md#fase-5)

## 📚 Documentación por Tema

### Sincronización Bidireccional
1. [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md)
2. [SESION_2025-11-10.md](SESION_2025-11-10.md)
3. [SESION_2025-11-11.md](SESION_2025-11-11.md)
4. [PROXIMA_SESION.md](PROXIMA_SESION.md)

### Sistema de Productos
1. [SINCRONIZACION_PRODUCTOS.md](SINCRONIZACION_PRODUCTOS.md)
2. [docs/BOM_SYNC.md](docs/BOM_SYNC.md)
3. [TRIGGER_PRODUCTOS_ACTUALIZADO.sql](TRIGGER_PRODUCTOS_ACTUALIZADO.sql)
4. [COMPARACION_TRIGGER_PRODUCTOS.md](COMPARACION_TRIGGER_PRODUCTOS.md)

### Dead Letter Queue
1. [docs/DLQ_SYSTEM.md](docs/DLQ_SYSTEM.md)
2. [CHANGELOG_v2.7.0.md](CHANGELOG_v2.7.0.md)
3. [docs/SESSION_SUMMARY_2025-11-19.md](docs/SESSION_SUMMARY_2025-11-19.md)

### Configuración y Despliegue
1. [CONFIGURACION_CREDENCIALES.md](CONFIGURACION_CREDENCIALES.md)
2. [SERVIDORES.md](SERVIDORES.md)
3. [PRODUCCION_READY.md](PRODUCCION_READY.md)
4. [DESPLIEGUE.md](DESPLIEGUE.md)
5. [INSTRUCCIONES_DESPLIEGUE_PRODUCCION.md](INSTRUCCIONES_DESPLIEGUE_PRODUCCION.md)

---

## 🔗 Enlaces Útiles

- **Repositorio**: https://github.com/CarlosAdrianM/odoo-custom-addons
- **NestoAPI**: https://github.com/CarlosAdrianM/NestoAPI
- **Google Cloud Project**: nestomaps-1547636206945
- **Pub/Sub Topic**: sincronizacion-tablas

---

**Última sincronización con GitHub**: 2025-12-12
**Branch actual**: main
**Commits totales**: Ver `git log`
