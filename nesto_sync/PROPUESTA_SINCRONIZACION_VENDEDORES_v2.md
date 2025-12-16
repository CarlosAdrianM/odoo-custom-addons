# Propuesta: Sincronización de Vendedores en Clientes (v2)

> **Autor**: Análisis técnico para issue en GitHub
> **Fecha**: 2025-12-12 (Revisión con auto-mapeo por email)
> **Estado**: Propuesta - Pendiente de aprobación

## 📋 Cambios respecto a v1

- ✅ **Auto-mapeo por email** (elimina mapeo manual)
- ✅ **Sincronización automática de vendedores** desde Nesto
- ✅ **Fase 3 clarificada** con tabla `EquiposVenta`
- ⏸️ **Fase 2 (Peluquería)** en stand-by

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
Mail         VARCHAR      -- Email del vendedor ← CLAVE PARA AUTO-MAPEO
```

### Tabla `EquiposVenta` (para Fase 3)
```sql
Id                INT IDENTITY(1,1)
Empresa           CHAR(3)
Vendedor          CHAR(3)      -- FK a Vendedores.Número
Superior          CHAR(3)      -- FK a Vendedores.Número (Jefe de ventas)
FechaDesde        DATE
FechaHasta        DATE
Usuario           NVARCHAR(50)
FechaModificacion DATETIME
```

**Director Comercial**: Hard-coded (sin tabla, valor fijo)

---

## 💡 Propuesta FASE 1: Auto-mapeo por Email

### Ventajas ✅

1. **Cero configuración manual**
   - No necesita tabla `nesto.vendedor`
   - No necesita UI para mapear
   - Todo automático

2. **Auto-actualizable**
   - Nuevo vendedor en Nesto → Se crea automáticamente en Odoo
   - Cambio de email → Se actualiza automáticamente

3. **Más simple**
   - Menos código
   - Menos tablas
   - Menos mantenimiento

### Desventajas ⚠️

1. **Requiere coincidencia exacta de emails**
   - Nesto: `juan@nuevavision.es`
   - Odoo: `juan@nuevavision.es` ✅
   - Nesto: `juan@nv.es`
   - Odoo: `juan@nuevavision.es` ❌

2. **Si email no coincide → vendedor no se asigna**
   - Solución: Logs claros para detectar
   - Fallback: Admin puede asignar manualmente

3. **Dependencia de calidad de datos**
   - Si email en Nesto está mal → falla
   - Si vendedor no tiene usuario en Odoo → falla

### Solución Híbrida: Auto-mapeo + Fallback Manual 🎯

**Mejor de ambos mundos**:
1. **Intentar auto-mapeo por email** primero
2. **Si falla**, buscar en tabla `nesto.vendedor` (opcional)
3. **Si ambos fallan**, log warning y `user_id = False`

---

## 🔧 Implementación Fase 1 (Auto-mapeo)

### 1. Mensaje PubSub desde Nesto

```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Nombre": "Cliente Ejemplo",
  "Vendedor": "001",                       // ⬅️ NUEVO: Código vendedor (CHAR(3))
  "VendedorEmail": "juan@nuevavision.es"   // ⬅️ NUEVO: Email para auto-mapeo
  // ... resto de campos ...
}
```

**Campos requeridos**: `Vendedor` + `VendedorEmail` (solo 2 campos nuevos)

### 2. Transformer con Auto-mapeo

```python
# transformers/field_transformers.py

@FieldTransformerRegistry.register('vendedor')
class VendedorTransformer(FieldTransformer):
    """
    Transforma vendedor Nesto → user_id en Odoo mediante auto-mapeo por email

    Estrategia:
    1. Buscar usuario en Odoo por email (VendedorEmail)
    2. Si no existe, crear usuario automáticamente (opcional)
    3. Asignar user_id al cliente

    Entrada:
        Vendedor: "001"
        VendedorEmail: "juan@nuevavision.es"

    Salida:
        user_id: 6 (ID de res.users)
    """

    def transform(self, value, record_values, env):
        vendedor_codigo = value  # "001"
        vendedor_email = record_values.get('VendedorEmail', '').strip().lower()

        if not vendedor_codigo:
            return {'user_id': False, 'vendedor_externo': False}

        if not vendedor_email:
            _logger.warning(
                f"Vendedor '{vendedor_codigo}' sin email. No se puede auto-mapear."
            )
            return {'user_id': False, 'vendedor_externo': vendedor_codigo}

        # PASO 1: Buscar usuario existente por email
        user = env['res.users'].sudo().search([
            ('login', '=ilike', vendedor_email),
            ('active', '=', True)
        ], limit=1)

        if user:
            _logger.info(
                f"✅ Vendedor '{vendedor_codigo}' mapeado a usuario '{user.name}' "
                f"({vendedor_email}) → user_id={user.id}"
            )
            return {
                'user_id': user.id,
                'vendedor_externo': vendedor_codigo
            }

        # PASO 2: Usuario no existe → Crear automáticamente (OPCIONAL)
        # ⚠️ DECISIÓN: ¿Crear usuarios automáticamente o no?

        # OPCIÓN A: NO crear, solo registrar warning
        _logger.warning(
            f"⚠️ Vendedor '{vendedor_codigo}' ({vendedor_email}) no existe en Odoo. "
            f"No se asignará user_id. Crear usuario manualmente."
        )
        return {'user_id': False, 'vendedor_externo': vendedor_codigo}

        # OPCIÓN B: Crear usuario automáticamente (comentado por seguridad)
        # user = self._create_user_from_vendedor(
        #     env, vendedor_codigo, vendedor_email, vendedor_nombre
        # )
        # return {'user_id': user.id, 'vendedor_externo': vendedor_codigo}

    def _create_user_from_vendedor(self, env, codigo, email, nombre):
        """
        Crea un usuario en Odoo desde datos de vendedor Nesto

        ⚠️ USAR CON PRECAUCIÓN: Crea usuarios con permisos
        """
        # Buscar si existe partner con ese email
        partner = env['res.partner'].sudo().search([
            ('email', '=ilike', email)
        ], limit=1)

        if not partner:
            # Crear partner
            partner = env['res.partner'].sudo().create({
                'name': nombre or f"Vendedor {codigo}",
                'email': email,
                'company_id': env.user.company_id.id,
            })

        # Crear usuario
        user = env['res.users'].sudo().create({
            'login': email,
            'name': nombre or f"Vendedor {codigo}",
            'partner_id': partner.id,
            'company_id': env.user.company_id.id,
            'groups_id': [(6, 0, [
                env.ref('base.group_user').id,      # Usuario interno
                env.ref('sales_team.group_sale_salesman').id  # Vendedor
            ])],
            'notification_type': 'email',
        })

        _logger.info(
            f"✅ Usuario creado automáticamente: {nombre} ({email}) → ID {user.id}"
        )
        return user
```

### 3. Configuración en entity_configs.py

```python
# config/entity_configs.py

ENTITY_CONFIGS = {
    'cliente': {
        # ... configuración existente ...

        'field_mappings': {
            # ... campos existentes ...

            # ⬅️ NUEVO: Vendedor con auto-mapeo
            # El transformer procesará 2 campos del mensaje:
            #   - Vendedor (código CHAR(3))
            #   - VendedorEmail (para auto-mapeo por email)
            'Vendedor': {
                'transformer': 'vendedor',
                'odoo_fields': ['user_id', 'vendedor_externo']
            },
        },

        # Mapeo inverso para sincronización bidireccional
        'reverse_field_mappings': {
            # ... campos existentes ...

            # Al publicar desde Odoo → Nesto
            'vendedor_externo': {'nesto_field': 'Vendedor'},
        },
    }
}
```

**Nota**: El transformer accede a `VendedorEmail` desde `record_values`, no necesita estar en `field_mappings`.

### 4. Campo en res.partner

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
        string="Código Vendedor (Nesto)",
        help="Código del vendedor en Nesto (ej: 001, 002, etc.)",
        index=True,
        readonly=True  # Solo se actualiza desde Nesto
    )

    # user_id ya existe en res.partner estándar (Many2one a res.users)
```

### 5. Sincronización Bidireccional (Odoo → Nesto)

```python
# core/odoo_publisher.py - Método _build_message_from_odoo()

# Al publicar cliente desde Odoo → Nesto
if record.user_id:
    # Opción A: Usar vendedor_externo guardado
    if record.vendedor_externo:
        message['Vendedor'] = record.vendedor_externo
    else:
        # Opción B: Buscar vendedor por email en tabla Vendedores (NestoAPI)
        # Esto requeriría una consulta a base de datos Nesto o una tabla de mapeo
        _logger.warning(
            f"Cliente {record.name} tiene user_id pero no vendedor_externo. "
            f"No se puede sincronizar vendedor a Nesto."
        )
```

**⚠️ Limitación**: Si se asigna un vendedor manualmente en Odoo (que no vino de Nesto), **no se puede sincronizar** a Nesto porque no sabemos su código.

**Solución**: Mantener `vendedor_externo` como fuente de verdad. Si admin cambia `user_id` en Odoo, debe actualizar también `vendedor_externo`.

---

## 🔄 Comparación: Auto-mapeo vs Mapeo Manual

| Criterio | Auto-mapeo por Email | Mapeo Manual |
|----------|---------------------|--------------|
| **Configuración inicial** | ✅ Ninguna | ❌ Crear mapeo de cada vendedor |
| **Nuevos vendedores** | ✅ Automático | ❌ Admin debe mapear manualmente |
| **Tolerancia a errores** | ⚠️ Si email no coincide → falla | ✅ Siempre funciona |
| **Calidad de datos** | ⚠️ Depende de emails correctos | ✅ No depende de emails |
| **Mantenimiento** | ✅ Cero | ⚠️ Admin debe actualizar mapeos |
| **Complejidad código** | ✅ Más simple | ⚠️ Más complejo (modelo + UI) |
| **Sincronización Odoo→Nesto** | ⚠️ Limitada | ✅ Completa |

### 🎯 Recomendación: **Enfoque Híbrido**

```python
def transform(self, value, record_values, env):
    vendedor_codigo = value
    vendedor_email = record_values.get('VendedorEmail', '').strip().lower()

    # PASO 1: Intentar auto-mapeo por email
    if vendedor_email:
        user = env['res.users'].sudo().search([
            ('login', '=ilike', vendedor_email)
        ], limit=1)

        if user:
            return {'user_id': user.id, 'vendedor_externo': vendedor_codigo}

    # PASO 2: Si falla, buscar en tabla de mapeo (fallback)
    vendedor = env['nesto.vendedor'].sudo().search([
        ('vendedor_externo', '=', vendedor_codigo)
    ], limit=1)

    if vendedor and vendedor.user_id:
        return {'user_id': vendedor.user_id.id, 'vendedor_externo': vendedor_codigo}

    # PASO 3: Si ambos fallan, registrar y continuar sin vendedor
    _logger.warning(f"Vendedor '{vendedor_codigo}' no se pudo mapear")
    return {'user_id': False, 'vendedor_externo': vendedor_codigo}
```

**Ventajas del híbrido**:
- ✅ 95% de casos usan auto-mapeo (rápido, automático)
- ✅ 5% de excepciones usan mapeo manual (flexible)
- ✅ Mejor de ambos mundos

---

## 📊 Fase 3: Jerarquía de Vendedores

### Estructura en Nesto

```
Director Comercial (hard-coded)
    ↓
Jefe de Ventas (desde EquiposVenta.Superior)
    ↓
Vendedor (EquiposVenta.Vendedor)
```

### Tabla `EquiposVenta`

```sql
Vendedor: "005"  → Superior: "003"
Vendedor: "006"  → Superior: "003"
Vendedor: "003"  → Superior: "001"  (Jefe → Director)
```

**Interpretación**:
- Vendedor "005" tiene como jefe a "003"
- Vendedor "003" es Jefe de Ventas (su superior es "001" = Director)
- Vendedor "001" es Director Comercial (no tiene superior, o su superior es NULL/él mismo)

### Mensaje PubSub (Fase 3)

```json
{
  "Cliente": "12345",
  "Vendedor": "005",
  "VendedorEmail": "vendedor@nv.es",
  "VendedorJefe": "003",              // ⬅️ NUEVO (Fase 3)
  "VendedorJefeEmail": "jefe@nv.es",  // ⬅️ NUEVO (Fase 3)
  "VendedorDirector": "001",          // ⬅️ NUEVO (Fase 3) - hard-coded en Nesto
  // ... resto de campos ...
}
```

**Fuente de datos en NestoAPI**:
```csharp
// NestoAPI - Al publicar cliente
var vendedor = dbContext.Vendedores.Find(cliente.Vendedor);
var equipo = dbContext.EquiposVenta
    .Where(e => e.Vendedor == cliente.Vendedor &&
                e.FechaHasta == null || e.FechaHasta > DateTime.Now)
    .FirstOrDefault();

message.Vendedor = vendedor.Numero;
message.VendedorEmail = vendedor.Mail;
message.VendedorJefe = equipo?.Superior;
message.VendedorDirector = "001";  // Hard-coded
```

### Implementación en Odoo (Fase 3)

**Opción A: Campos en res.partner** (más simple)
```python
class ResPartner(models.Model):
    # ... campos existentes ...

    user_id = fields.Many2one('res.users', string="Vendedor")
    user_jefe_id = fields.Many2one('res.users', string="Jefe de Ventas")
    user_director_id = fields.Many2one('res.users', string="Director Comercial")
```

**Opción B: Usar crm.team** (más Odoo-way)
```python
# Crear equipo de ventas por cada jefe
team = env['crm.team'].search([
    ('user_id.login', '=', 'jefe@nv.es')
], limit=1)

if not team:
    team = env['crm.team'].create({
        'name': f"Equipo de {jefe_nombre}",
        'user_id': jefe_user_id,  # Líder del equipo
    })

# Asignar cliente al equipo
partner.team_id = team.id
partner.user_id = vendedor_user_id  # Vendedor individual
```

**⚠️ Decisión pendiente**: ¿Cómo se usa la jerarquía en el negocio?
- ¿Solo informativa? → Opción A (campos simples)
- ¿Afecta reportes/comisiones/permisos? → Opción B (crm.team)

---

## 🚀 Plan de Implementación

### Fase 1: Vendedor Principal (MVP) - 1 sesión

**Backend (NestoAPI)**:
- [ ] Añadir campos al mensaje: `Vendedor`, `VendedorEmail`
- [ ] Publicar datos desde `Clientes.Vendedor` + JOIN con `Vendedores`
- [ ] Procesar campo `Vendedor` en mensajes entrantes (suscripción)

**Backend (Odoo)**:
- [ ] Crear `VendedorTransformer` con auto-mapeo por email
- [ ] Añadir campo `vendedor_externo` en `res.partner`
- [ ] Actualizar `entity_configs.py`
- [ ] Implementar sincronización bidireccional (Odoo → Nesto)

**Testing**:
- [ ] Test: Email coincide → asigna user_id correctamente
- [ ] Test: Email no coincide → warning, user_id=False
- [ ] Test: Email vacío → warning, user_id=False
- [ ] Test: Cambio user_id en Odoo → publica a Nesto

**Documentación**:
- [ ] Actualizar README con gestión de vendedores
- [ ] Guía para admin: Qué hacer si vendedor no se asigna

### Fase 2: Vendedor Peluquería - STAND-BY ⏸️

No implementar por ahora. Pendiente de decisión de negocio.

### Fase 3: Jerarquía - 1 sesión (después de Fase 1)

**Backend (NestoAPI)**:
- [ ] Añadir campos: `VendedorJefe`, `VendedorJefeEmail`, `VendedorDirector`
- [ ] JOIN con `EquiposVenta` para obtener `Superior`

**Backend (Odoo)**:
- [ ] **DECISIÓN**: ¿Usar campos custom o `crm.team`?
- [ ] Implementar según decisión
- [ ] Extender `VendedorTransformer` para procesar jerarquía

**Testing**:
- [ ] Test: Jerarquía completa se mapea correctamente
- [ ] Test: Vendedor sin jefe (FechaHasta expirada)

---

## ⚠️ Decisiones Pendientes

### 1. ¿Crear usuarios automáticamente?

**Escenario**: Nesto envía vendedor con email que no existe en Odoo.

**Opción A**: NO crear, solo log warning
- ✅ Más seguro (no crea usuarios sin control)
- ❌ Requiere creación manual de usuarios

**Opción B**: Crear usuario automáticamente
- ✅ Totalmente automático
- ⚠️ Riesgo de crear usuarios con permisos incorrectos
- ⚠️ Requiere definir qué permisos darles

**Recomendación**: **Opción A** (no crear automáticamente). Motivos:
- Seguridad: Usuarios = acceso a sistema
- Control: Admin debe aprobar nuevos vendedores
- Calidad: Evita usuarios duplicados o mal configurados

### 2. ¿Qué hacer si se cambia user_id en Odoo manualmente?

**Escenario**: Admin asigna en Odoo un vendedor que no vino de Nesto.

**Problema**: No sabemos el código Nesto del vendedor → No podemos sincronizar.

**Solución propuesta**:
- Guardar `vendedor_externo` como fuente de verdad
- Si `user_id` cambia en Odoo y no hay `vendedor_externo`:
  - **NO sincronizar** a Nesto
  - Registrar warning en logs
  - (Opcional) Mostrar mensaje en UI: "Este vendedor no está mapeado en Nesto"

### 3. ¿Usar enfoque híbrido o solo auto-mapeo?

**Enfoque híbrido**: Auto-mapeo primero, fallback a tabla manual

**Pros**:
- ✅ Mejor de ambos mundos
- ✅ Tolera excepciones

**Contras**:
- ⚠️ Más complejo
- ⚠️ Requiere mantener tabla de mapeo

**Recomendación**: Empezar solo con **auto-mapeo**. Si surgen problemas recurrentes (emails que no coinciden), añadir tabla de mapeo después.

---

## 📈 Métricas de Éxito

### KPIs para Fase 1:

1. **% de clientes con vendedor asignado**
   - Target: >95%
   - Medir: `SELECT COUNT(*) WHERE user_id IS NOT NULL / COUNT(*)`

2. **% de auto-mapeo exitoso**
   - Target: >90%
   - Medir: Logs de transformer (éxitos vs warnings)

3. **Tiempo de sincronización**
   - Target: <100ms por cliente
   - Medir: Performance del transformer

4. **Errores de mapeo**
   - Target: <5% de clientes
   - Medir: Logs con warning "no se pudo mapear"

### Monitoreo:

```python
# Añadir al transformer
_logger.info(
    f"📊 Estadísticas de vendedores: "
    f"Total={total}, Éxitos={exitos}, Fallos={fallos}, "
    f"Tasa éxito={exitos/total*100:.1f}%"
)
```

---

## 🔗 Referencias

- [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md)
- [Field Transformers](transformers/field_transformers.py)
- Odoo res.partner fields: `user_id`, `team_id`
- NestoAPI: Tablas `Vendedores`, `EquiposVenta`

---

## 📋 Resumen Ejecutivo

### Lo que cambia respecto a v1:

1. ✅ **Elimina tabla `nesto.vendedor`** → Usa auto-mapeo por email
2. ✅ **Elimina UI de configuración** → Todo automático
3. ✅ **Soluciona problema de nuevos vendedores** → Auto-detecta por email
4. ✅ **Clarifica Fase 3** → Usa tabla `EquiposVenta` para jerarquía
5. ⏸️ **Pospone Fase 2** → Vendedor peluquería en stand-by

### Recomendación final:

**Implementar Fase 1 con auto-mapeo puro** (sin tabla de fallback)

**Ventajas**:
- Código más simple
- Cero configuración
- Automático al 100%

**Mitigación de riesgos**:
- Logs claros cuando falla
- Dashboard para ver clientes sin vendedor
- Documentación para casos excepcionales

---

**Próximo paso**: Crear issue en GitHub con esta propuesta.
