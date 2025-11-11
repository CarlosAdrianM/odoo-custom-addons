# Changelog - Sesión 2025-11-11

## Versión 2.1.0 - Corrección estructura de mensajes bidireccionales

### Cambios Principales

#### 1. **Estructura de mensajes Odoo → Nesto corregida**
- **Problema**: Los mensajes se enviaban con estructura `{Accion, Tabla, Datos: {Parent, Children}}`
- **Solución**: Cambiado a estructura **plana** compatible con subscriber: `{campos..., PersonasContacto: [...], Tabla, Source}`
- **Archivo**: `core/odoo_publisher.py` - método `_wrap_in_sync_message()`

#### 2. **Implementación de Reverse Transformers**
Implementados transformers bidireccionales para conversión Odoo → Nesto:

- **phone**: Combina `mobile` y `phone` → `"mobile/phone"` o solo mobile
- **country_state**: Convierte `state_id` (Many2one) → nombre de provincia (string)
- **estado_to_active**: Convierte `active` (bool) → `Estado` (9 o -1)
- **cliente_principal**: Convierte `type` ('invoice'/'delivery') → `ClientePrincipal` (bool)
- **cargos**: Convierte `function` (string) → código numérico usando mapeo inverso

**Archivo**: `core/odoo_publisher.py` - método `_apply_reverse_transformer()`

#### 3. **Inferencia automática de field mappings**
- Los campos se infieren automáticamente desde `field_mappings` y `child_field_mappings`
- Solo es necesario declarar explícitamente los **identificadores críticos**:
  - `cliente_externo` → `Cliente`
  - `contacto_externo` → `Contacto`
  - `persona_contacto_externa` → `Id`
- Todos los demás campos se mapean automáticamente manteniendo nombres en español

**Archivos**:
- `core/odoo_publisher.py` - métodos `_infer_reverse_mappings()` y `_infer_reverse_child_mappings()`
- `config/entity_configs.py` - secciones `reverse_field_mappings` y `reverse_child_field_mappings`

#### 4. **Filtrado de campos internos**
- Los campos que empiezan con `_` (como `_country`, `_company`, `_type`) se omiten en mensajes salientes
- Estos campos solo se usan para sincronización Nesto → Odoo

**Archivo**: `core/odoo_publisher.py` - métodos `_infer_reverse_mappings()` y `_infer_reverse_child_mappings()`

#### 5. **Filtrado de campos vacíos**
- Campos con valores `None`, `False`, `''` o `0` se omiten del mensaje
- Excepción: `ClientePrincipal` se incluye siempre (es un booleano real)

**Archivo**: `core/odoo_publisher.py` - método `_build_message_from_odoo()`

#### 6. **Corrección nombre de campo para children**
- **Cambio**: `Telefono` (singular) → `Telefonos` (plural) para PersonasContacto
- **Motivo**: Compatibilidad con formato esperado por Nesto
- Parent sigue usando `Telefono` (singular)

**Archivo**: `config/entity_configs.py` - sección `child_field_mappings`

#### 7. **Fix serialización de objetos Markup**
- Los objetos `Markup` de Odoo (HTML) se convierten correctamente a string
- Evita problemas de serialización JSON

**Archivo**: `core/odoo_publisher.py` - método `_serialize_odoo_value()`

### Archivos Modificados

```
config/entity_configs.py
├── Añadido reverse_field_mappings con identificadores
├── Añadido reverse_child_field_mappings con identificadores
└── Cambiado Telefono → Telefonos en child_field_mappings

core/odoo_publisher.py
├── _wrap_in_sync_message(): Estructura plana en lugar de Parent/Children
├── _build_message_from_odoo(): Inferencia automática + filtrado de campos vacíos
├── _infer_reverse_mappings(): Nuevo método para inferir mappings automáticamente
├── _infer_reverse_child_mappings(): Nuevo método para inferir child mappings
├── _apply_reverse_transformer(): Implementados todos los transformers
├── _add_children_to_message(): Usa inferencia automática + filtrado
└── _serialize_odoo_value(): Fix para objetos Markup
```

### Formato de Mensaje Resultante

```json
{
  "Nif": "B85432771",
  "Cliente": "15191",
  "Contacto": "2",
  "ClientePrincipal": true,
  "Nombre": "CENTRO DE ESTÉTICA EL EDÉN, S.L.U.",
  "Direccion": "AV. DE LA SIERRA, 6",
  "CodigoPostal": "28701",
  "Poblacion": "SAN SEBASTIÁN DE LOS REYES",
  "Provincia": "Madrid",
  "Telefono": "671839434/915027884",
  "Comentarios": "...",
  "Estado": 9,
  "PersonasContacto": [
    {
      "Id": "1",
      "Nombre": "Ángela",
      "CorreoElectronico": "info@esteticaeleden.com",
      "Telefonos": "915027884",
      "Cargo": 22
    }
  ],
  "Tabla": "Clientes",
  "Source": "Odoo"
}
```

### Compatibilidad

✅ **100% compatible** con el subscriber existente (Nesto → Odoo)
✅ **Anti-bucle**: Sistema de detección de cambios evita bucles infinitos
✅ **Estructura idéntica** a mensajes de NestoAPI

### Testing

- ✅ Probado con cliente 15191 (CENTRO DE ESTÉTICA EL EDÉN, S.L.U.)
- ✅ Verificados todos los transformers
- ✅ Verificada estructura de mensaje
- ✅ Verificados identificadores (Cliente, Contacto, Id)
- ✅ Verificado campo Telefonos (plural) en children

### Notas de Despliegue

1. No requiere migración de datos
2. No hay cambios en la base de datos
3. Solo actualizar código del módulo
4. Reiniciar servicio Odoo después de actualizar

### Próximos Pasos

- Desplegar a producción (nuevavisionodoo)
- Monitorizar logs para verificar formato de mensajes
- Verificar que no hay bucles infinitos
