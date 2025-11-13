# Nesto Sync - Módulo de Sincronización Bidireccional

Módulo de Odoo 16 Community para sincronización bidireccional entre Nesto y Odoo via Google Cloud Pub/Sub.

## Versión Actual

**v2.3.4** (2025-11-13) - Operativo en producción

## Características

### ✅ Entidades Sincronizadas

1. **Clientes** (`res.partner`)
   - Sincronización bidireccional completa
   - Jerarquía parent/children (PersonasContacto)
   - Campos: Nombre, Dirección, NIF, Teléfonos, Email, Estado, etc.
   - [Documentación detallada](SINCRONIZACION_CLIENTES.md)

2. **Productos** (`product.template`)
   - Sincronización bidireccional operativa
   - Campos básicos: Producto, Nombre, Precio, Tamaño, Código de Barras
   - Transformer para tipo de producto (almacenable/servicio/consumible)
   - [Documentación detallada](SINCRONIZACION_PRODUCTOS.md)

### 🏗️ Arquitectura

- **Genérica y extensible:** Configuración declarativa en `entity_configs.py`
- **Sin código específico por entidad:** Un solo `GenericEntityService` y `GenericEntityProcessor`
- **Transformers reutilizables:** Registro de transformaciones (phone, country_state, etc.)
- **Anti-bucle robusto:** Detección de cambios reales + contexto `skip_sync`
- **Validación genérica:** Usando `id_fields` de configuración

[Arquitectura completa](ARQUITECTURA_EXTENSIBLE.md)

## Instalación

### Dependencias

```bash
pip install google-cloud-pubsub
```

### Módulos de Odoo

- `base` (core)
- `product` (para sincronización de productos)

### Configuración

1. Instalar módulo desde Odoo UI o CLI
2. Configurar credenciales de Google Cloud Pub/Sub en variables de entorno
3. Verificar endpoint: `https://tu-odoo.com/nesto_sync`
4. Verificar logs: `https://tu-odoo.com/nesto_sync/logs`

## Uso

### Sincronización Nesto → Odoo

Los mensajes de Nesto llegan via Pub/Sub al endpoint `/nesto_sync` con estructura:

```json
{
  "Tabla": "Productos",
  "Producto": "15191",
  "Nombre": "Producto ejemplo",
  "PrecioProfesional": 99.99,
  ...
}
```

El sistema detecta automáticamente el tipo de entidad usando el campo `"Tabla"` y aplica los mapeos configurados.

### Sincronización Odoo → Nesto

Cuando se modifica un registro en Odoo UI:

1. `BidirectionalSyncMixin` intercepta el cambio
2. Verifica que sea un cambio real (anti-bucle)
3. Serializa según `reverse_field_mappings`
4. Publica a Pub/Sub con formato Nesto

## Changelog

### v2.3.4 (2025-11-13) - CRÍTICO

- **Fix:** Manejo de estructuras de mensaje con/sin wrapper
- Añadido `_extract_entity_data()` para compatibilidad con ambas estructuras
- Logs de debug para identificar estructura detectada
- **Verificado en producción:** Productos sincronizando correctamente

### v2.3.3 (2025-11-13) - CRÍTICO

- **Fix:** Detección de entidad usando campo "Tabla" como fuente de verdad
- Antes detectaba por presencia de campos (causaba errores de tipo de entidad)
- Mapeo: `Clientes→cliente`, `Productos→producto`, `Proveedores→proveedor`

### v2.3.2 (2025-11-13)

- **Refactor:** Validación genérica usando `id_fields` de entity_configs
- Eliminado código hardcoded específico de entidades
- Logs mejorados con información específica por entidad

### v2.3.1 (2025-11-13)

- Mapeo enriquecido de productos: Producto, PrecioProfesional, CodigoBarras
- Transformer `ficticio_to_detailed_type` (Ficticio + Grupo → tipo producto)
- Lógica: `Ficticio=0→product`, `Ficticio=1+Grupo=CUR→service`, otros→`consu`

### v2.3.0 (2025-11-13)

- **Nueva entidad:** Productos (`product.template`)
- Campo `producto_externo` para sincronización
- Mapeo de campos básicos (fase minimalista)
- Sincronización bidireccional habilitada

### v2.2.x (2025-11-11 y anteriores)

- Sincronización de clientes con jerarquía
- Anti-bucle mediante detección de cambios
- Transformers para teléfonos, provincias, etc.
- Sistema genérico de configuración

## Roadmap

### Fase 2 - Productos (Pendiente)

1. **UnidadMedida** → `uom_id` (transformer)
2. **Grupo/Subgrupo/Familia** → `categ_id` (categorías con jerarquía)
3. **Proveedor** → `product.supplierinfo` (relación con proveedores)
4. **UrlFoto** → `image_1920` (descarga y conversión a base64)

### Fase 3 - Testing

1. Tests unitarios para sincronización Nesto → Odoo
2. Tests para sincronización Odoo → Nesto
3. Tests de anti-bucle infinito
4. Pruebas de rendimiento con volumen alto

### Futuro

- Sincronización de pedidos
- Sincronización de stock
- Dashboard de métricas de sincronización
- Webhook de confirmación a Nesto

## Debugging

### Logs

```bash
# Ver logs en tiempo real
sudo journalctl -u odoo16 -f | grep -i "nesto_sync"

# Ver logs específicos de productos
sudo journalctl -u odoo16 --since "1 hour ago" | grep -i "producto"

# Endpoint HTTP de logs (últimos 100)
curl https://tu-odoo.com/nesto_sync/logs
```

### Base de Datos

```sql
-- Verificar productos sincronizados
SELECT id, name, default_code, producto_externo, list_price, detailed_type
FROM product_template
WHERE producto_externo IS NOT NULL;

-- Verificar clientes sincronizados
SELECT id, name, cliente_externo, contacto_externo, is_company
FROM res_partner
WHERE cliente_externo IS NOT NULL;
```

## Troubleshooting

### Error: "Tabla 'X' no está configurada"

**Causa:** El campo "Tabla" en el mensaje contiene un valor no mapeado.

**Solución:** Añadir mapeo en `controllers.py:tabla_to_entity`:

```python
tabla_to_entity = {
    'Clientes': 'cliente',
    'Productos': 'producto',
    'TuNuevaTabla': 'tu_nueva_entidad',  # Añadir aquí
}
```

### Error: "No se pudo determinar el tipo de entidad"

**Causa:** El mensaje no contiene campo "Tabla" ni campos identificables.

**Solución:** Verificar estructura del mensaje en logs y asegurar que tenga "Tabla" o al menos un campo ID.

### Productos se crean pero no se sincronizan de vuelta

**Causa:** Falta `producto_externo` (campo requerido en `id_fields`).

**Solución:** Verificar mapeo en `entity_configs.py:external_id_mapping`:

```python
'external_id_mapping': {
    'producto_externo': 'Producto',
}
```

## Contribuir

1. Crear branch desde `main`
2. Implementar cambios siguiendo arquitectura genérica
3. Actualizar documentación relevante
4. Commit con mensaje descriptivo
5. Push y crear PR

## Soporte

- Logs del módulo: `https://tu-odoo.com/nesto_sync/logs`
- Documentación: Ver archivos `.md` en el módulo
- Issues: Reportar en repositorio

## Licencia

Propietario - Uso interno

---

**Última actualización:** 2025-11-13 17:30 UTC
**Mantenido por:** Equipo de Integración Nesto-Odoo
