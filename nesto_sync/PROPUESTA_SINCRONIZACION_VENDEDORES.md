# Propuesta: Sincronización de Vendedores en Clientes

> **Autor**: Análisis técnico para issue en GitHub
> **Fecha**: 2025-12-12
> **Estado**: Propuesta - Pendiente de aprobación

## 📋 Contexto

Actualmente, la sincronización de clientes desde Nesto a Odoo **no incluye información de vendedores**. Este documento plantea cómo implementar esta funcionalidad considerando:

1. La estructura de datos en Nesto (SQL Server)
2. La estructura de datos en Odoo 16
3. El caso especial de clientes con 2 vendedores (estética y peluquería)
4. La jerarquía de vendedores (Director → Jefe → Vendedores)

---

## 🗄️ Estructura de Datos en Nesto

### Tabla `Clientes`
```sql
Clientes.Vendedor CHAR(3)  -- Vendedor de estética (por defecto)
```

### Tabla `Vendedores`
```sql
Empresa      CHAR(3)
Número       CHAR(3)      -- ID del vendedor (PK)
Descripción  VARCHAR      -- Nombre del vendedor
Mail         VARCHAR      -- Email del vendedor
-- [Posiblemente más campos para jerarquía: Director, Jefe, etc.]
```

### Tabla `VendedoresClienteGrupoProducto`
Para clientes con vendedores específicos por grupo de producto (ej: Peluquería):
```sql
Id                INT IDENTITY(1,1)
Empresa           CHAR(3)
Cliente           CHAR(10)
Contacto          CHAR(3)
GrupoProducto     CHAR(3)      -- "PEL" para peluquería
Vendedor          CHAR(3)
Estado            SMALLINT
Usuario           VARCHAR(30)
FechaModificacion DATETIME

-- Ejemplo de uso:
-- Cliente: 12345, Contacto: 0, GrupoProducto: PEL, Vendedor: 001
```

---

## 🔧 Estructura de Datos en Odoo 16

### Modelo `res.partner` (Clientes)
```python
# Campos existentes relacionados con vendedores:
user_id   = Many2one('res.users')      # Vendedor asignado (Salesperson)
team_id   = Many2one('crm.team')       # Equipo de ventas
```

### Modelo `res.users` (Usuarios/Vendedores)
```python
id           INT
login        VARCHAR    # Email de login
partner_id   INT        # Relación con res.partner
sale_team_id INT        # Equipo de ventas del vendedor
```

### Modelo `crm.team` (Equipos de Ventas)
```python
id      INT
name    JSONB
user_id INT     # Líder del equipo
```

---

## 💡 Propuesta de Implementación

### Fase 1: Vendedor Principal (Estética) ✅ Recomendado

**Objetivo**: Sincronizar el vendedor de estética desde `Clientes.Vendedor`

#### 1.1. Mensaje PubSub desde Nesto

Añadir al mensaje de cliente:
```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Nombre": "Cliente Ejemplo",
  "Vendedor": "001",                       // ⬅️ NUEVO: Vendedor de estética (CHAR(3))
  "VendedorEmail": "juan@nuevavision.es"   // ⬅️ NUEVO: Email para auto-mapeo
  // ... resto de campos ...
}
```

**Nota**: `VendedorNombre` NO es necesario. Cada sistema tiene su propia forma de almacenar nombres.

#### 1.2. Tabla de Mapeo en Odoo

Crear modelo `nesto.vendedor` para mapear vendedores de Nesto → Usuarios de Odoo:

```python
# models/nesto_vendedor.py
class NestoVendedor(models.Model):
    _name = 'nesto.vendedor'
    _description = 'Mapeo de Vendedores Nesto → Odoo'

    vendedor_externo = fields.Char(string="Código Vendedor Nesto", required=True, index=True)
    name = fields.Char(string="Nombre Vendedor", required=True)
    email = fields.Char(string="Email")
    user_id = fields.Many2one('res.users', string="Usuario Odoo", required=True)
    team_id = fields.Many2one('crm.team', string="Equipo de Ventas")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('vendedor_externo_unique', 'UNIQUE(vendedor_externo)',
         'El código de vendedor externo debe ser único')
    ]
```

**Vista en Odoo UI**:
- Menú: Configuración → Sincronización Nesto → Vendedores
- Permite mapear manualmente `001` → `Juan Pérez (res.users.id=6)`

#### 1.3. Field Transformer para Vendedor

```python
# transformers/field_transformers.py

@FieldTransformerRegistry.register('vendedor')
class VendedorTransformer(FieldTransformer):
    """
    Transforma código de vendedor Nesto → user_id en Odoo

    Entrada: "001" (código vendedor Nesto)
    Salida: 6 (ID de res.users en Odoo)
    """

    def transform(self, value, record_values, env):
        if not value:
            return {'user_id': False}

        # Buscar mapeo en tabla nesto.vendedor
        vendedor = env['nesto.vendedor'].sudo().search([
            ('vendedor_externo', '=', str(value).strip()),
            ('active', '=', True)
        ], limit=1)

        if not vendedor:
            _logger.warning(
                f"Vendedor externo '{value}' no encontrado en mapeo. "
                f"No se asignará vendedor al cliente."
            )
            return {'user_id': False}

        if not vendedor.user_id:
            _logger.warning(
                f"Vendedor externo '{value}' existe pero no tiene user_id asignado"
            )
            return {'user_id': False}

        return {
            'user_id': vendedor.user_id.id,
            'team_id': vendedor.team_id.id if vendedor.team_id else False
        }
```

#### 1.4. Configuración en entity_configs.py

```python
# config/entity_configs.py

ENTITY_CONFIGS = {
    'cliente': {
        # ... configuración existente ...

        'field_mappings': {
            # ... campos existentes ...

            # ⬅️ NUEVO: Vendedor
            'Vendedor': {
                'transformer': 'vendedor',
                'odoo_fields': ['user_id', 'team_id']
            },
        },

        # Mapeo inverso para sincronización bidireccional
        'reverse_field_mappings': {
            # ... campos existentes ...

            # ⬅️ NUEVO: Al publicar desde Odoo → Nesto
            'vendedor_externo': {'nesto_field': 'Vendedor'},
        },
    }
}
```

#### 1.5. Añadir campo en res.partner

```python
# models/res_partner.py

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['bidirectional.sync.mixin', 'res.partner']

    cliente_externo = fields.Char(...)
    contacto_externo = fields.Char(...)
    persona_contacto_externa = fields.Char(...)

    # ⬅️ NUEVO
    vendedor_externo = fields.Char(
        string="Vendedor Externo (Nesto)",
        help="Código del vendedor en Nesto (estética)",
        index=True
    )
```

#### 1.6. Script de Migración

Crear data/vendedores_mapping.xml con mapeo inicial:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <!-- Mapeo de vendedores Nesto → Odoo -->
        <record id="vendedor_001" model="nesto.vendedor">
            <field name="vendedor_externo">001</field>
            <field name="name">Juan Pérez</field>
            <field name="email">juan@nuevavision.es</field>
            <field name="user_id" ref="base.user_example_1"/>
        </record>

        <record id="vendedor_002" model="nesto.vendedor">
            <field name="vendedor_externo">002</field>
            <field name="name">María García</field>
            <field name="email">maria@nuevavision.es</field>
            <field name="user_id" ref="base.user_example_2"/>
        </record>

        <!-- Añadir más vendedores según sea necesario -->
    </data>
</odoo>
```

---

### Fase 2: Vendedor de Peluquería (Opcional) 🔄

**Objetivo**: Soportar clientes con 2 vendedores (estética + peluquería)

#### 2.1. Campo adicional en res.partner

```python
# models/res_partner.py

class ResPartner(models.Model):
    # ... campos existentes ...

    vendedor_externo = fields.Char(...)  # Vendedor estética

    # ⬅️ NUEVO para peluquería
    vendedor_peluqueria_externo = fields.Char(
        string="Vendedor Peluquería (Nesto)",
        help="Código del vendedor de peluquería en Nesto (grupo PEL)",
        index=True
    )
    user_id_peluqueria = fields.Many2one(
        'res.users',
        string="Vendedor Peluquería",
        help="Vendedor asignado para productos de peluquería"
    )
```

**Problema**: Odoo estándar solo tiene **un** campo `user_id` por cliente.

**Soluciones posibles**:

**Opción A**: Usar solo `user_id` para estética (ignorar peluquería)
- ✅ Simple
- ❌ No captura la realidad del negocio

**Opción B**: Crear campos custom `user_id_peluqueria`
- ✅ Captura ambos vendedores
- ❌ Requiere customización de vistas y reportes de ventas
- ❌ Módulos estándar de Odoo solo usarán `user_id`

**Opción C**: Usar `team_id` para diferenciar
- Crear 2 equipos: "Estética" y "Peluquería"
- Asignar `user_id` según el equipo principal del cliente
- ❌ Pierde información del segundo vendedor

**⚠️ Recomendación**: En **Fase 1** solo sincronizar vendedor de estética. Evaluar Fase 2 según necesidades de negocio.

#### 2.2. Mensaje PubSub (si se implementa Fase 2)

```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Vendedor": "001",              // Estética
  "VendedorPeluqueria": "002",    // ⬅️ Desde VendedoresClienteGrupoProducto
  // ... resto de campos ...
}
```

---

### Fase 3: Jerarquía de Vendedores (Futuro) 📊

**Objetivo**: Sincronizar la estructura organizativa (Director → Jefe → Vendedor)

#### 3.1. Campos adicionales en nesto.vendedor

```python
class NestoVendedor(models.Model):
    # ... campos existentes ...

    jefe_id = fields.Many2one('nesto.vendedor', string="Jefe de Ventas")
    director_id = fields.Many2one('nesto.vendedor', string="Director Comercial")
```

#### 3.2. Uso de crm.team

Mapear jerarquía a equipos de ventas en Odoo:
- Director Comercial → `crm.team` con `user_id` = Director
- Jefe de Ventas → Miembro del equipo
- Vendedores → Miembros del equipo

**⚠️ Nota**: Esta fase requiere definir primero cómo está estructurada la jerarquía en Nesto.

---

## 🔄 Sincronización Bidireccional

### Odoo → Nesto

Cuando se cambia el `user_id` en Odoo:

1. El `BidirectionalSyncMixin` detecta el cambio
2. Busca el `vendedor_externo` correspondiente en `nesto.vendedor`
3. Publica mensaje a PubSub:

```json
{
  "Tabla": "Clientes",
  "Operacion": "UPDATE",
  "Datos": {
    "Cliente": "12345",
    "Contacto": "0",
    "Vendedor": "001"    // ⬅️ Código Nesto del vendedor
  }
}
```

4. NestoAPI actualiza `Clientes.Vendedor = '001'`

### Transformer Inverso

```python
# core/odoo_publisher.py - Método _build_message_from_odoo()

# Al publicar cliente desde Odoo → Nesto
if record.user_id:
    # Buscar código de vendedor Nesto
    vendedor = env['nesto.vendedor'].sudo().search([
        ('user_id', '=', record.user_id.id)
    ], limit=1)

    if vendedor:
        message['Vendedor'] = vendedor.vendedor_externo
    else:
        _logger.warning(
            f"Usuario {record.user_id.name} no tiene mapeo en nesto.vendedor"
        )
```

---

## 📦 Entregables

### Fase 1: Vendedor Principal

1. **Modelo nuevo**: `nesto.vendedor` (mapeo vendedores)
2. **Campo nuevo**: `res.partner.vendedor_externo`
3. **Transformer**: `VendedorTransformer`
4. **Configuración**: Actualizar `entity_configs.py`
5. **Vista UI**: Menú para gestionar mapeo de vendedores
6. **Data inicial**: XML con vendedores existentes
7. **Tests**: Test del transformer y sincronización bidireccional
8. **Documentación**: Guía de uso y configuración
9. **Migration script**: Actualizar módulo en producción

### Fase 2 (Opcional): Vendedor Peluquería

1. **Campos nuevos**: `vendedor_peluqueria_externo`, `user_id_peluqueria`
2. **Transformer extendido**: Soportar 2 vendedores
3. **Vistas customizadas**: Mostrar ambos vendedores en formulario
4. **Cambios en NestoAPI**: Publicar `VendedorPeluqueria` desde tabla `VendedoresClienteGrupoProducto`

### Fase 3 (Futuro): Jerarquía

1. **Campos adicionales**: `jefe_id`, `director_id` en `nesto.vendedor`
2. **Mapeo a crm.team**: Crear equipos según jerarquía
3. **Análisis previo**: Definir estructura en Nesto

---

## ⚠️ Consideraciones Técnicas

### 1. Mapeo Manual vs Automático

**Opción A: Mapeo Manual** ✅ Recomendado
- Admin configura manualmente en UI de Odoo
- Más control y flexibilidad
- Vendedor "001" → Usuario "Juan Pérez"

**Opción B: Mapeo Automático por Email**
- Si `Vendedores.Mail` coincide con `res.users.login`
- Menos mantenimiento
- ⚠️ Riesgo si emails no coinciden exactamente

**Propuesta**: Empezar con **mapeo manual** (Fase 1), considerar auto-mapeo en futuro.

### 2. ¿Qué pasa si no existe el vendedor?

**Caso**: Nesto envía `"Vendedor": "999"` pero no existe en `nesto.vendedor`

**Solución**:
- Registrar WARNING en logs
- **NO FALLAR** la sincronización del cliente
- Dejar `user_id = False` (sin vendedor asignado)
- Admin puede asignarlo manualmente después

### 3. Permisos y Seguridad

El transformer debe usar `.sudo()` porque:
- El endpoint `/pubsub/inbound` es público (sin autenticación)
- Necesita buscar en `nesto.vendedor` y `res.users`

### 4. Performance

Con miles de clientes sincronizándose:
- ✅ Índice en `nesto.vendedor.vendedor_externo`
- ✅ Caché de mapeos (opcional: decorador `@tools.ormcache`)
- ✅ Búsqueda con `.search(..., limit=1)`

### 5. Testing

Tests necesarios:
```python
# tests/test_vendedor_transformer.py

def test_vendedor_transform_success(self):
    """Vendedor existe → asigna user_id correctamente"""

def test_vendedor_not_found(self):
    """Vendedor no existe → user_id = False, sin error"""

def test_vendedor_without_user(self):
    """Vendedor existe pero sin user_id → user_id = False"""

def test_bidirectional_sync_vendedor(self):
    """Cambiar user_id en Odoo → publica código vendedor a Nesto"""
```

---

## 🎯 Recomendación Final

### Para empezar (MVP):

**Implementar solo Fase 1: Vendedor Principal (Estética)**

✅ **Ventajas**:
- Simple de implementar y mantener
- Cubre el 90% de los casos de uso
- Fácil de probar y desplegar
- Compatible con Odoo estándar

📋 **Tareas**:
1. Crear modelo `nesto.vendedor`
2. Crear transformer `vendedor`
3. Actualizar `entity_configs.py`
4. Añadir campo `vendedor_externo` en `res.partner`
5. NestoAPI: Incluir `Vendedor` en mensaje PubSub
6. Configurar mapeo inicial de vendedores
7. Tests + Documentación

⏱️ **Estimación**: 1-2 sesiones de desarrollo

### Para el futuro:

- **Fase 2** solo si el negocio realmente necesita diferenciar vendedores por grupo de producto
- **Fase 3** cuando se clarifique la estructura jerárquica en Nesto

---

## 🔗 Referencias

- Modelo Odoo `res.partner`: [Odoo Documentation](https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html)
- Módulo CRM Odoo 16: Equipos de ventas y vendedores
- Arquitectura extensible nesto_sync: [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md)
- Field transformers: [transformers/field_transformers.py](transformers/field_transformers.py)

---

**Próximo paso**: Crear issue en GitHub con esta propuesta para discusión y aprobación.
