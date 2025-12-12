# ROADMAP - Nesto Sync

## Visión General
Sistema de sincronización bidireccional entre Odoo 16 y Nesto mediante Google PubSub.

## Objetivos Principales

### 1. Sincronización Bidireccional (PRÓXIMO)
- **Estado**: Pendiente
- **Prioridad**: Alta
- **Descripción**: Implementar sincronización Odoo → Nesto
- **Retos**:
  - Evitar bucle infinito de actualizaciones
  - Solución propuesta: Comparar valores antes de actualizar. Solo actualizar si hay cambios reales.
  - Sistema de detección de cambios inteligente

### 2. Arquitectura Extensible
- **Estado**: Pendiente
- **Prioridad**: Crítica
- **Descripción**: Diseño que permita añadir nuevas entidades sin refactorización masiva
- **Objetivos**:
  - Código reutilizable para sincronizar diferentes entidades (Proveedores, Productos, Seguimientos, etc.)
  - Configuración declarativa de campos a sincronizar
  - Sistema de mapeo flexible entre Nesto y Odoo
  - Reducir al mínimo los cambios necesarios al añadir nuevas tablas

### 3. Coordinación con NestoAPI
- **Estado**: Pendiente
- **Prioridad**: Alta
- **Descripción**: Sincronizar desarrollo con proyecto NestoAPI (C# WebApi 2)
- **Repositorio**: https://github.com/CarlosAdrianM/NestoAPI
- **Necesidades**:
  - Prompts preparados para transferir contexto entre proyectos
  - Definición clara de contratos de mensajes
  - Documentación de API compartida

## Fases de Desarrollo

### Fase 1: Análisis y Diseño ✅ COMPLETADA
- [x] Documentar estado actual del código
- [x] Diseñar arquitectura extensible
- [x] Definir estrategia anti-bucle infinito
- [x] Diseñar sistema de mapeo de campos

### Fase 2: Implementación Arquitectura Extensible ✅ COMPLETADA
- [x] Extraer lógica común de sincronización
- [x] Crear sistema de configuración de entidades
- [x] Implementar mapeo declarativo de campos
- [x] Crear factory/registry de procesadores
- [x] Implementar transformers, validators y post_processors
- [x] Implementar detección de cambios (anti-bucle)
- [x] Refactorizar Controller para usar sistema genérico

### Fase 3: Testing y Validación (ACTUAL)
- [ ] Tests unitarios de transformers
- [ ] Tests de GenericProcessor con config de cliente
- [ ] Tests de GenericService (CRUD + detección cambios)
- [ ] Tests de integración completos
- [ ] Validar con mensajes reales de Nesto
- [ ] Comparar comportamiento con código legacy

### Fase 4: Sincronización Bidireccional
- [ ] Implementar publicador a PubSub
- [ ] Implementar hooks en Odoo (write/create)
- [ ] Detectar origen del cambio (Odoo vs Nesto)
- [ ] Verificar que no hay bucles infinitos
- [ ] Coordinar con NestoAPI

### Fase 5: Sincronización de Vendedores (PRÓXIMO)
- [ ] **Fase 1**: Vendedor principal (estética) - Auto-mapeo híbrido
  - [ ] Crear modelo `nesto.vendedor` (tabla de mapeo fallback)
  - [ ] Implementar `VendedorTransformer` con auto-mapeo por email
  - [ ] Añadir campo `vendedor_externo` en `res.partner`
  - [ ] Coordinar con NestoAPI: Publicar `Vendedor`, `VendedorEmail`, `VendedorNombre`
  - [ ] Sincronización bidireccional (Odoo ↔ Nesto)
  - [ ] Tests y documentación
- [ ] **Fase 2**: Vendedor peluquería - STAND-BY
- [ ] **Fase 3**: Jerarquía de vendedores (Director → Jefe → Vendedor)
  - [ ] Sincronizar desde tabla `EquiposVenta`
  - [ ] Integración con `crm.team` de Odoo

Ver: [ISSUE_SINCRONIZACION_VENDEDORES.md](ISSUE_SINCRONIZACION_VENDEDORES.md)

### Fase 6: Expansión a Nuevas Entidades
- [ ] Proveedores (res.partner con supplier_rank)
- [ ] Seguimientos de clientes
- [ ] [Añadir más según necesidades]

## Decisiones de Arquitectura Tomadas

1. **Sistema de detección de cambios**: ✅ Comparación campo a campo con tipo de dato
2. **Configuración de mapeos**: ✅ Python dict (más flexible que JSON/YAML)
3. **Manejo de conflictos**: ✅ Last-write-wins (detección de cambios evita bucles)
4. **Transformers**: ✅ Clases en lugar de funciones (más OO)

## Notas Técnicas

### Convenciones
- Mantener separación de responsabilidades (Processor, Service, Adapter)
- Tests unitarios para toda lógica crítica
- Logging exhaustivo para debugging
- Commits descriptivos en español

### Riesgos Identificados
- Bucle infinito de sincronización
- Pérdida de datos en conflictos
- Performance con grandes volúmenes
- Complejidad al escalar a múltiples entidades

---

## 📌 Issues Abiertas

### Issue #1: Sincronización de Vendedores en Clientes
- **Estado**: 📝 Documentada, pendiente de implementación
- **Prioridad**: Alta
- **Versión objetivo**: v2.9.0
- **Archivo**: [ISSUE_SINCRONIZACION_VENDEDORES.md](ISSUE_SINCRONIZACION_VENDEDORES.md)
- **Descripción**: Implementar auto-mapeo híbrido de vendedores (email + fallback manual)
- **Estimación**: 1-2 sesiones
- **Bloqueantes**: Requiere cambios en NestoAPI

---
**Última actualización**: 2025-12-12
