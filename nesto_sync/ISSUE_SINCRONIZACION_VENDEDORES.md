# Issue: Sincronización de Vendedores en Clientes

> **Tipo**: Feature / Enhancement
> **Prioridad**: Alta
> **Versión objetivo**: v2.9.0
> **Estado**: EN PROGRESO - Odoo implementado, pendiente NestoAPI
> **Última actualización**: 2025-12-16

---

## 🚦 Estado Actual (2025-12-16)

### Implementado en Odoo:
- [x] `VendedorTransformer` con auto-mapeo solo por email (sin `vendedor_externo`)
- [x] Distingue entre `VendedorEmail` AUSENTE vs VACÍO
- [x] Tests para todos los casos edge (vendedor NV, email vacío, etc.)
- [x] Sincronización bidireccional: Odoo publica `VendedorEmail` a PubSub
- [x] Reverse transformer genera `{VendedorEmail: email}` desde `user_id`

### Pendiente en NestoAPI:
- [ ] Añadir campos `Vendedor` y `VendedorEmail` al mensaje de cliente
- [ ] Hacer JOIN con tabla `Vendedores` para obtener email
- [ ] Procesar `VendedorEmail` en mensajes entrantes (resolver código por email)

### Problema reportado:
La sincronización de vendedores desde Odoo a Nesto **no funciona** todavía.
Posibles causas a investigar:
1. NestoAPI no procesa el campo `VendedorEmail`
2. NestoAPI no envía `VendedorEmail` en mensajes salientes
3. Verificar logs en ambos sistemas

Ver documentación de requerimientos: [REQUERIMIENTOS_NESTOAPI_VENDEDORES.md](REQUERIMIENTOS_NESTOAPI_VENDEDORES.md)

---

## 📋 Descripción

Implementar sincronización del vendedor asignado a cada cliente entre Nesto y Odoo, usando **solo el email como fuente de verdad**.

**Principio clave**: `VendedorEmail` es el identificador universal. Cada sistema resuelve el código de vendedor desde el email de forma independiente.

---

## 🎯 Objetivos

### Fase 1: Vendedor Principal (MVP)

- [x] VendedorTransformer con auto-mapeo por email
- [x] Tests completos incluyendo casos edge
- [x] Sincronización bidireccional Odoo → Nesto (publica VendedorEmail)
- [ ] **PENDIENTE**: NestoAPI debe enviar VendedorEmail en mensajes
- [ ] **PENDIENTE**: NestoAPI debe procesar VendedorEmail entrante

### Fase 2: Vendedor Peluquería

STAND-BY - Pendiente de decisión de negocio

### Fase 3: Jerarquía de Vendedores

- [ ] Sincronizar jefe de ventas (desde `EquiposVenta`)
- [ ] Sincronizar director comercial (hard-coded)
- [ ] Integración con `crm.team` de Odoo

---

## 🗄️ Datos en Nesto (SQL Server)

### Tabla `Vendedores`
```sql
Empresa      CHAR(3)
Número       CHAR(3)      -- ID del vendedor (PK) - Ej: "001", "002"
Descripción  VARCHAR      -- Nombre del vendedor - Ej: "Juan Pérez"
Mail         VARCHAR      -- Email del vendedor - Ej: "juan@nuevavision.es"
```

### Tabla `Clientes`
```sql
Clientes.Vendedor CHAR(3)  -- FK a Vendedores.Número
```

### Tabla `EquiposVenta` (Fase 3)
```sql
Id                INT IDENTITY(1,1)
Empresa           CHAR(3)
Vendedor          CHAR(3)      -- FK a Vendedores.Número
Superior          CHAR(3)      -- FK a Vendedores.Número (Jefe de ventas)
FechaDesde        DATE
FechaHasta        DATE         -- NULL = Vigente
```

---

## 🔧 Datos en Odoo 16

### Modelo `res.partner` (Clientes)

**Campos existentes**:
```python
user_id = Many2one('res.users', string="Salesperson")  # Vendedor asignado
team_id = Many2one('crm.team', string="Sales Team")    # Equipo de ventas
```

**Campos nuevos** (a crear):
```python
vendedor_externo = Char(string="Código Vendedor (Nesto)", index=True, readonly=True)
```

### Modelo `res.users` (Vendedores)
```python
id           INT
login        VARCHAR    # Email de login (para auto-mapeo)
partner_id   INT
sale_team_id INT
```

---

## 💡 Solución Propuesta: Auto-mapeo Híbrido

### Estrategia

1. **Auto-mapeo por email** (90-95% de casos) ✅ Automático
   - Buscar usuario en Odoo por email (`res.users.login`)
   - Si coincide → Asignar `user_id`

2. **Fallback a tabla manual** (5-10% excepciones) 🔧 Manual
   - Crear modelo `nesto.vendedor` para mapeo manual
   - Admin configura excepciones (emails que no coinciden)

3. **Logs claros** 📊 Monitoreo
   - Log de éxito: "✅ Vendedor 001 mapeado a Juan Pérez"
   - Log de warning: "⚠️ Vendedor 001 no encontrado"

### Diagrama de Flujo

```
Mensaje PubSub: {"Vendedor": "001", "VendedorEmail": "juan@nv.es"}
                               ↓
                    ┌──────────────────────┐
                    │ VendedorTransformer  │
                    └──────────────────────┘
                               ↓
         ┌────────────────────────────────────────┐
         │ PASO 1: Auto-mapeo por email          │
         │ Buscar: res.users.login = "juan@nv.es"│
         └────────────────────────────────────────┘
                               ↓
                    ¿Usuario encontrado?
                               ↓
                    ┌──────────┴──────────┐
                   SÍ                     NO
                    ↓                      ↓
          user_id = 6 ✅        ┌──────────────────────┐
          return                │ PASO 2: Fallback     │
                                │ Buscar en tabla      │
                                │ nesto.vendedor       │
                                └──────────────────────┘
                                           ↓
                                ¿Mapeo encontrado?
                                           ↓
                                ┌──────────┴──────────┐
                               SÍ                     NO
                                ↓                      ↓
                      user_id = 6 ✅        user_id = False ⚠️
                      return                Log warning
                                           return
```

---

## 📦 Cambios Necesarios en NestoAPI

### 🏗️ Arquitectura: Patrón PubSub Puro

**IMPORTANTE**: Todos los sistemas (Odoo, Nesto, Prestashop futuro, etc.) son **peers** que:
- **Publican** mensajes al topic PubSub
- **Se suscriben** al topic para recibir mensajes

**NO hay endpoints directos entre sistemas**. Todo pasa por PubSub.

### 🔴 REQUERIMIENTOS PARA NestoAPI

#### 1. Añadir campos al mensaje de Cliente (Publicación)

**Campos a añadir** (2 nuevos):
```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Nombre": "Cliente Ejemplo",

  // ⬇️ NUEVOS CAMPOS
  "Vendedor": "001",                      // Clientes.Vendedor (CHAR(3))
  "VendedorEmail": "juan@nuevavision.es", // Vendedores.Mail (JOIN)

  // ... resto de campos existentes ...
}
```

**Nota**: `VendedorNombre` NO es necesario. Cada sistema usa el identificador que necesita.

#### 2. Query SQL con JOIN

```csharp
public ClienteDTO BuildClienteMessage(string empresa, string cliente, string contacto)
{
    var clienteData = dbContext.Clientes
        .Where(c => c.Empresa == empresa &&
                    c.NºCliente == cliente &&
                    c.Contacto == contacto)
        .FirstOrDefault();

    if (clienteData == null) return null;

    // JOIN con tabla Vendedores para obtener email
    var vendedor = dbContext.Vendedores
        .Where(v => v.Empresa == clienteData.Empresa &&
                    v.Número == clienteData.Vendedor)
        .FirstOrDefault();

    return new ClienteDTO
    {
        Cliente = clienteData.NºCliente,
        Contacto = clienteData.Contacto,
        Nombre = clienteData.Nombre,
        // ... otros campos ...

        // ⬇️ NUEVOS
        Vendedor = clienteData.Vendedor,
        VendedorEmail = vendedor?.Mail
    };
}
```

#### 3. Validaciones (recomendadas)

```csharp
if (string.IsNullOrWhiteSpace(dto.Vendedor))
{
    _logger.Warning($"Cliente {dto.Cliente} sin vendedor asignado");
    dto.Vendedor = null;
    dto.VendedorEmail = null;
}
else if (string.IsNullOrWhiteSpace(dto.VendedorEmail))
{
    _logger.Warning($"Vendedor {dto.Vendedor} sin email. Auto-mapeo fallará.");
    // Publicar de todas formas con solo el código
}
```

#### 4. Procesar Mensajes Entrantes (Suscripción)

NestoAPI ya está suscrito al topic. Cuando reciba mensaje de actualización de cliente (desde Odoo u otro sistema), debe procesar el campo `Vendedor`:

```csharp
// Al recibir mensaje de PubSub
public async Task ProcessClienteUpdate(ClienteUpdateMessage message)
{
    var cliente = await dbContext.Clientes
        .Where(c => c.Empresa == message.Empresa &&
                    c.NºCliente == message.Cliente &&
                    c.Contacto == message.Contacto)
        .FirstOrDefaultAsync();

    if (cliente == null) return;

    // Procesar cambio de vendedor si viene en el mensaje
    if (!string.IsNullOrWhiteSpace(message.Vendedor))
    {
        var vendedorExiste = await dbContext.Vendedores
            .AnyAsync(v => v.Empresa == message.Empresa &&
                          v.Número == message.Vendedor);

        if (vendedorExiste)
        {
            cliente.Vendedor = message.Vendedor;
        }
        else
        {
            _logger.LogWarning($"Vendedor {message.Vendedor} no existe, ignorando");
        }
    }

    cliente.FechaModificacion = DateTime.Now;
    cliente.Usuario = "PubSub";

    await dbContext.SaveChangesAsync();
}
```

Ver documentación completa en: [REQUERIMIENTOS_NESTOAPI_VENDEDORES.md](REQUERIMIENTOS_NESTOAPI_VENDEDORES.md)

---

## 🔨 Implementación en Odoo

### 1. Nuevo Modelo: `nesto.vendedor` (Tabla de Mapeo)

**Archivo**: `models/nesto_vendedor.py`

```python
from odoo import models, fields

class NestoVendedor(models.Model):
    _name = 'nesto.vendedor'
    _description = 'Mapeo de Vendedores Nesto → Odoo (Fallback manual)'

    vendedor_externo = fields.Char(
        string="Código Vendedor Nesto",
        required=True,
        index=True,
        help="Código del vendedor en Nesto (ej: 001, 002)"
    )
    name = fields.Char(
        string="Nombre Vendedor",
        required=True
    )
    email = fields.Char(
        string="Email",
        help="Email del vendedor (informativo)"
    )
    user_id = fields.Many2one(
        'res.users',
        string="Usuario Odoo",
        required=True,
        help="Usuario de Odoo al que se mapea este vendedor"
    )
    team_id = fields.Many2one(
        'crm.team',
        string="Equipo de Ventas",
        help="Equipo de ventas del vendedor (opcional)"
    )
    active = fields.Boolean(default=True)

    notas = fields.Text(
        string="Notas",
        help="Notas sobre este mapeo (ej: por qué el email no coincide)"
    )

    _sql_constraints = [
        ('vendedor_externo_unique', 'UNIQUE(vendedor_externo)',
         'El código de vendedor externo debe ser único')
    ]
```

### 2. Vista UI para Mapeo Manual

**Archivo**: `views/nesto_vendedor_views.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Tree View -->
    <record id="view_nesto_vendedor_tree" model="ir.ui.view">
        <field name="name">nesto.vendedor.tree</field>
        <field name="model">nesto.vendedor</field>
        <field name="arch" type="xml">
            <tree string="Vendedores Nesto">
                <field name="vendedor_externo"/>
                <field name="name"/>
                <field name="email"/>
                <field name="user_id"/>
                <field name="team_id"/>
                <field name="active"/>
            </tree>
        </field>
    </record>

    <!-- Form View -->
    <record id="view_nesto_vendedor_form" model="ir.ui.view">
        <field name="name">nesto.vendedor.form</field>
        <field name="model">nesto.vendedor</field>
        <field name="arch" type="xml">
            <form string="Mapeo de Vendedor">
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <widget name="web_ribbon" title="Archived" bg_color="bg-danger"
                                attrs="{'invisible': [('active', '=', True)]}"/>
                    </div>
                    <group>
                        <group>
                            <field name="vendedor_externo"/>
                            <field name="name"/>
                            <field name="email"/>
                        </group>
                        <group>
                            <field name="user_id"/>
                            <field name="team_id"/>
                            <field name="active"/>
                        </group>
                    </group>
                    <group>
                        <field name="notas" placeholder="Ej: Email en Nesto es diferente al login en Odoo"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <!-- Action -->
    <record id="action_nesto_vendedor" model="ir.actions.act_window">
        <field name="name">Vendedores Nesto</field>
        <field name="res_model">nesto.vendedor</field>
        <field name="view_mode">tree,form</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                Crear mapeo manual de vendedor
            </p>
            <p>
                Esta tabla se usa como <b>fallback</b> cuando el auto-mapeo por email falla.<br/>
                Solo es necesario crear registros para vendedores cuyo email en Nesto no coincide con el login en Odoo.
            </p>
        </field>
    </record>

    <!-- Menu -->
    <menuitem
        id="menu_nesto_vendedor"
        name="Vendedores Nesto"
        parent="menu_nesto_sync_config"
        action="action_nesto_vendedor"
        sequence="20"/>
</odoo>
```

### 3. Transformer: `VendedorTransformer`

**Archivo**: `transformers/field_transformers.py`

```python
@FieldTransformerRegistry.register('vendedor')
class VendedorTransformer(FieldTransformer):
    """
    Transforma vendedor Nesto → user_id en Odoo mediante auto-mapeo híbrido

    Estrategia:
    1. Auto-mapeo por email (automático, 90-95% de casos)
    2. Fallback a tabla nesto.vendedor (manual, 5-10% excepciones)
    3. Si ambos fallan, registrar warning y continuar sin vendedor

    Entrada (del mensaje PubSub):
        Vendedor: "001"                    (código vendedor Nesto)
        VendedorEmail: "juan@nv.es"        (email para auto-mapeo)

    Salida:
        user_id: 6                         (ID de res.users en Odoo)
        vendedor_externo: "001"            (para sincronización bidireccional)
    """

    def transform(self, value, record_values, env):
        """
        Args:
            value: Código del vendedor (ej: "001")
            record_values: Dict con todos los campos del mensaje
            env: Odoo environment

        Returns:
            Dict con user_id y vendedor_externo
        """
        vendedor_codigo = str(value).strip() if value else ''
        vendedor_email = record_values.get('VendedorEmail', '').strip().lower()

        # Si no hay código de vendedor, no asignar
        if not vendedor_codigo:
            return {
                'user_id': False,
                'vendedor_externo': False
            }

        # ========================================
        # PASO 1: Auto-mapeo por email (PRIMARIO)
        # ========================================
        if vendedor_email:
            user = env['res.users'].sudo().search([
                ('login', '=ilike', vendedor_email),
                ('active', '=', True)
            ], limit=1)

            if user:
                _logger.info(
                    f"✅ Vendedor '{vendedor_codigo}' auto-mapeado por email: "
                    f"{vendedor_email} → user_id={user.id} ({user.name})"
                )
                return {
                    'user_id': user.id,
                    'vendedor_externo': vendedor_codigo
                }

            # Email proporcionado pero usuario no encontrado
            _logger.debug(
                f"Auto-mapeo por email falló: vendedor '{vendedor_codigo}' "
                f"({vendedor_email}) no encontrado en res.users. "
                f"Intentando fallback manual..."
            )

        else:
            # No hay email, ir directo a fallback
            _logger.debug(
                f"Vendedor '{vendedor_codigo}' sin email. "
                f"Usando fallback manual..."
            )

        # ========================================
        # PASO 2: Fallback a tabla manual
        # ========================================
        vendedor_mapeo = env['nesto.vendedor'].sudo().search([
            ('vendedor_externo', '=', vendedor_codigo),
            ('active', '=', True)
        ], limit=1)

        if vendedor_mapeo:
            if not vendedor_mapeo.user_id:
                _logger.warning(
                    f"⚠️ Vendedor '{vendedor_codigo}' existe en tabla nesto.vendedor "
                    f"pero no tiene user_id asignado. No se asignará vendedor."
                )
                return {
                    'user_id': False,
                    'vendedor_externo': vendedor_codigo
                }

            _logger.info(
                f"✅ Vendedor '{vendedor_codigo}' mapeado manualmente: "
                f"user_id={vendedor_mapeo.user_id.id} ({vendedor_mapeo.user_id.name})"
            )
            return {
                'user_id': vendedor_mapeo.user_id.id,
                'vendedor_externo': vendedor_codigo
            }

        # ========================================
        # PASO 3: Ningún mapeo funcionó
        # ========================================
        _logger.warning(
            f"⚠️ Vendedor '{vendedor_codigo}' no se pudo mapear. "
            f"Email: {vendedor_email or 'N/A'}. "
            f"El cliente se creará sin vendedor asignado. "
            f"Solución: Crear mapeo manual en Configuración → Sincronización Nesto → Vendedores Nesto"
        )

        # No asignar vendedor, pero guardar código para referencia
        return {
            'user_id': False,
            'vendedor_externo': vendedor_codigo
        }
```

### 4. Actualizar `entity_configs.py`

**Archivo**: `config/entity_configs.py`

```python
ENTITY_CONFIGS = {
    'cliente': {
        # ... configuración existente ...

        'field_mappings': {
            # ... campos existentes ...

            # ⬇️ NUEVO: Vendedor
            'Vendedor': {
                'transformer': 'vendedor',
                'odoo_fields': ['user_id', 'vendedor_externo']
            },
        },

        # Mapeo inverso para sincronización bidireccional
        'reverse_field_mappings': {
            # ... campos existentes ...

            # ⬇️ NUEVO: Al publicar desde Odoo → Nesto
            'vendedor_externo': {'nesto_field': 'Vendedor'},
        },
    }
}
```

### 5. Actualizar modelo `res.partner`

**Archivo**: `models/res_partner.py`

```python
class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['bidirectional.sync.mixin', 'res.partner']

    cliente_externo = fields.Char(...)
    contacto_externo = fields.Char(...)
    persona_contacto_externa = fields.Char(...)

    # ⬇️ NUEVO
    vendedor_externo = fields.Char(
        string="Código Vendedor (Nesto)",
        help="Código del vendedor en Nesto (ej: 001, 002). "
             "Se usa para sincronización bidireccional.",
        index=True,
        readonly=True,
        copy=False
    )

    # user_id ya existe en res.partner estándar
    # No necesitamos redefinirlo
```

### 6. Sincronización Bidireccional (Odoo → Nesto)

**Archivo**: `core/odoo_publisher.py` - Actualizar método `_build_message_from_odoo()`

```python
def _build_message_from_odoo(self, record):
    """Construye mensaje para publicar a PubSub desde registro de Odoo"""

    # ... código existente ...

    # ⬇️ NUEVO: Añadir vendedor al mensaje
    if hasattr(record, 'vendedor_externo') and record.vendedor_externo:
        # Caso 1: Vendedor vino de Nesto, tenemos el código
        message['Vendedor'] = record.vendedor_externo

    elif hasattr(record, 'user_id') and record.user_id:
        # Caso 2: Vendedor asignado manualmente en Odoo
        # Intentar buscar código en tabla nesto.vendedor
        vendedor = self.env['nesto.vendedor'].sudo().search([
            ('user_id', '=', record.user_id.id)
        ], limit=1)

        if vendedor:
            message['Vendedor'] = vendedor.vendedor_externo
            # Actualizar vendedor_externo en el cliente para futuras sincronizaciones
            record.sudo().write({'vendedor_externo': vendedor.vendedor_externo})
        else:
            _logger.warning(
                f"Cliente {record.name} (ID={record.id}) tiene user_id={record.user_id.id} "
                f"pero no hay mapeo en nesto.vendedor. No se puede sincronizar vendedor a Nesto."
            )

    return message
```

---

## 🧪 Tests

**Archivo**: `tests/test_vendedor_transformer.py`

```python
from odoo.tests.common import TransactionCase
from ..transformers.field_transformers import FieldTransformerRegistry

class TestVendedorTransformer(TransactionCase):

    def setUp(self):
        super().setUp()
        self.transformer = FieldTransformerRegistry.get_transformer('vendedor')

        # Crear usuario para auto-mapeo
        self.user_juan = self.env['res.users'].create({
            'name': 'Juan Pérez',
            'login': 'juan@nuevavision.es',
            'email': 'juan@nuevavision.es',
        })

    def test_auto_mapeo_exitoso(self):
        """Test: Auto-mapeo por email funciona correctamente"""
        record_values = {
            'VendedorEmail': 'juan@nuevavision.es'
        }

        result = self.transformer.transform('001', record_values, self.env)

        self.assertEqual(result['user_id'], self.user_juan.id)
        self.assertEqual(result['vendedor_externo'], '001')

    def test_auto_mapeo_email_case_insensitive(self):
        """Test: Auto-mapeo ignora mayúsculas/minúsculas"""
        record_values = {
            'VendedorEmail': 'JUAN@NUEVAVISION.ES',
        }

        result = self.transformer.transform('001', record_values, self.env)

        self.assertEqual(result['user_id'], self.user_juan.id)

    def test_auto_mapeo_falla_usuario_no_existe(self):
        """Test: Email no existe → intenta fallback"""
        record_values = {
            'VendedorEmail': 'noexiste@nuevavision.es',
        }

        result = self.transformer.transform('999', record_values, self.env)

        self.assertFalse(result['user_id'])
        self.assertEqual(result['vendedor_externo'], '999')

    def test_fallback_manual_exitoso(self):
        """Test: Fallback a tabla nesto.vendedor funciona"""
        # Crear mapeo manual
        self.env['nesto.vendedor'].create({
            'vendedor_externo': '002',
            'name': 'María García',
            'user_id': self.user_juan.id,  # Reutilizamos usuario
        })

        record_values = {
            'VendedorEmail': 'email_diferente@nv.es',  # Email no coincide
        }

        result = self.transformer.transform('002', record_values, self.env)

        self.assertEqual(result['user_id'], self.user_juan.id)
        self.assertEqual(result['vendedor_externo'], '002')

    def test_sin_vendedor(self):
        """Test: Vendedor vacío → no asigna user_id"""
        record_values = {}

        result = self.transformer.transform('', record_values, self.env)

        self.assertFalse(result['user_id'])
        self.assertFalse(result['vendedor_externo'])

    def test_sin_email_sin_fallback(self):
        """Test: Sin email ni fallback → warning y user_id=False"""
        record_values = {
            'Vendedor': '999'
            # Sin VendedorEmail
        }

        result = self.transformer.transform('999', record_values, self.env)

        self.assertFalse(result['user_id'])
        self.assertEqual(result['vendedor_externo'], '999')
```

---

## 📊 Plan de Implementación

### Sesión 1: Implementación Core (3-4 horas)

**Backend Odoo**:
- [ ] Crear modelo `nesto.vendedor`
- [ ] Crear vistas XML (`nesto_vendedor_views.xml`)
- [ ] Implementar `VendedorTransformer`
- [ ] Añadir campo `vendedor_externo` en `res.partner`
- [ ] Actualizar `entity_configs.py`
- [ ] Añadir modelo a `__manifest__.py`

**Tests**:
- [ ] Crear `test_vendedor_transformer.py`
- [ ] Ejecutar tests: `odoo-bin -c odoo.conf --test-enable -d odoo_test -u nesto_sync --stop-after-init`

**Documentación**:
- [ ] Actualizar README con sección de vendedores
- [ ] Crear guía: "Qué hacer si un vendedor no se mapea"

### Sesión 2: Integración NestoAPI + Sincronización Bidireccional (2-3 horas)

**Backend NestoAPI** (coordinado con equipo de C#):
- [ ] Añadir campos `Vendedor`, `VendedorEmail` al DTO
- [ ] Modificar query SQL para hacer JOIN con tabla `Vendedores`
- [ ] Publicar campos en mensaje PubSub
- [ ] Procesar campo `Vendedor` en mensajes entrantes (suscripción)

**Backend Odoo**:
- [ ] Implementar sincronización Odoo → Nesto en `odoo_publisher.py`
- [ ] Test end-to-end: Cambiar vendedor en Odoo → verificar en Nesto

**Validación**:
- [ ] Sincronizar 10 clientes de prueba desde Nesto
- [ ] Verificar que vendedores se asignan correctamente
- [ ] Revisar logs: ¿Cuántos auto-mapeos exitosos? ¿Cuántos warnings?

### Sesión 3: Despliegue y Monitoreo (1 hora)

**Despliegue**:
- [ ] Actualizar módulo en desarrollo: `odoo-bin -u nesto_sync`
- [ ] Verificar que tabla `nesto_vendedor` se crea
- [ ] Crear mapeos manuales para excepciones (si existen)

**Monitoreo**:
- [ ] Dashboard SQL para clientes sin vendedor:
  ```sql
  SELECT COUNT(*) FROM res_partner
  WHERE customer_rank > 0
    AND cliente_externo IS NOT NULL
    AND user_id IS NULL;
  ```
- [ ] Analizar logs: Ratio éxito/fallo del auto-mapeo
- [ ] Ajustar según resultados

---

## 📈 Métricas de Éxito

### KPIs

1. **% de clientes con vendedor asignado**
   - **Target**: >95%
   - **Query**:
     ```sql
     SELECT
       COUNT(*) FILTER (WHERE user_id IS NOT NULL) * 100.0 / COUNT(*) as porcentaje
     FROM res_partner
     WHERE customer_rank > 0 AND cliente_externo IS NOT NULL;
     ```

2. **% de auto-mapeo exitoso**
   - **Target**: >90%
   - **Fuente**: Logs del transformer

3. **Clientes sin vendedor**
   - **Target**: <5%
   - **Query**: Ver arriba

4. **Mapeos manuales necesarios**
   - **Target**: <10 registros en `nesto.vendedor`
   - **Query**: `SELECT COUNT(*) FROM nesto_vendedor;`

### Dashboard SQL

```sql
-- Vista de vendedores: Auto-mapeo vs Manual
SELECT
  CASE
    WHEN user_id IS NOT NULL THEN 'Con vendedor'
    WHEN vendedor_externo IS NOT NULL THEN 'Sin mapear'
    ELSE 'Sin vendedor en Nesto'
  END as estado,
  COUNT(*) as cantidad
FROM res_partner
WHERE customer_rank > 0 AND cliente_externo IS NOT NULL
GROUP BY estado;
```

---

## ⚠️ Riesgos y Mitigaciones

### Riesgo 1: Emails no coinciden entre Nesto y Odoo

**Probabilidad**: Media
**Impacto**: Medio (vendedor no se asigna)

**Mitigación**:
- ✅ Fallback a tabla manual
- ✅ Logs claros para detectar casos
- ✅ Dashboard para monitorear

### Riesgo 2: Vendedor sin email en Nesto

**Probabilidad**: Baja
**Impacto**: Bajo (solo afecta a ese vendedor)

**Mitigación**:
- ✅ Validación en NestoAPI (no publicar si email vacío)
- ✅ Fallback a tabla manual
- ✅ Log de warning

### Riesgo 3: Performance con miles de clientes

**Probabilidad**: Baja
**Impacto**: Medio (sincronización lenta)

**Mitigación**:
- ✅ Índice en `nesto.vendedor.vendedor_externo`
- ✅ Índice en `res.users.login`
- ✅ Búsquedas con `.search(..., limit=1)`
- ✅ Uso de `.sudo()` para evitar chequeos de permisos innecesarios

### Riesgo 4: Admin cambia vendedor en Odoo y no se sincroniza a Nesto

**Probabilidad**: Media
**Impacto**: Medio (datos inconsistentes)

**Mitigación**:
- ✅ Campo `vendedor_externo` como fuente de verdad
- ✅ Buscar en tabla `nesto.vendedor` para obtener código
- ✅ Log de warning si no se puede sincronizar
- ⚠️ Documentar: "Al asignar vendedor manual, debe existir en nesto.vendedor"

---

## 📚 Documentación para Usuarios

### Guía: "Mi cliente no tiene vendedor asignado"

**Síntomas**:
- Cliente sincronizado desde Nesto
- Campo "Vendedor" (Salesperson) vacío en Odoo
- Logs muestran: "⚠️ Vendedor XXX no se pudo mapear"

**Causas posibles**:

1. **Email del vendedor en Nesto no coincide con login en Odoo**
   - Nesto: `juan@nv.es`
   - Odoo: `juan@nuevavision.es`

2. **Vendedor no existe como usuario en Odoo**
   - El vendedor está en Nesto pero no tiene cuenta en Odoo

3. **Vendedor sin email en Nesto**
   - Campo `Vendedores.Mail` está vacío

**Solución**:

#### Opción A: Crear mapeo manual (recomendado)

1. Ir a: **Configuración → Sincronización Nesto → Vendedores Nesto**
2. Crear nuevo registro:
   - **Código Vendedor Nesto**: `001` (del log)
   - **Nombre Vendedor**: `Juan Pérez`
   - **Usuario Odoo**: Seleccionar usuario
   - **Notas**: "Email en Nesto diferente al login Odoo"
3. Guardar
4. Reprocesar cliente (o esperar a próxima sincronización)

#### Opción B: Corregir email en Nesto

1. Actualizar `Vendedores.Mail` en Nesto para que coincida con login en Odoo
2. La próxima sincronización auto-mapeará correctamente

#### Opción C: Asignar manualmente en Odoo

1. Abrir cliente en Odoo
2. Asignar vendedor en campo "Salesperson"
3. ⚠️ **Importante**: Para que se sincronice a Nesto, debe existir mapeo en tabla `nesto.vendedor`

---

## 🔗 Referencias

- [PROPUESTA_SINCRONIZACION_VENDEDORES_v2.md](PROPUESTA_SINCRONIZACION_VENDEDORES_v2.md) - Análisis técnico completo
- [ARQUITECTURA_EXTENSIBLE.md](ARQUITECTURA_EXTENSIBLE.md) - Arquitectura del sistema
- [transformers/field_transformers.py](transformers/field_transformers.py) - Sistema de transformers
- Odoo res.partner: `user_id`, `team_id`
- NestoAPI: Tablas `Vendedores`, `EquiposVenta`, `Clientes`

---

## ✅ Checklist de Aceptación

### Sincronización Nesto → Odoo

- [ ] Cuando Nesto publica cliente con vendedor válido → Se asigna `user_id` en Odoo
- [ ] Cuando email coincide → Auto-mapeo exitoso (log: "✅")
- [ ] Cuando email no coincide pero existe mapeo manual → Fallback exitoso (log: "✅")
- [ ] Cuando vendedor no se puede mapear → Log warning, cliente se crea sin vendedor
- [ ] Campo `vendedor_externo` siempre se guarda (para sincronización bidireccional)

### Sincronización Odoo → Nesto

- [ ] Cuando admin cambia `user_id` en Odoo → Se publica a Nesto si existe `vendedor_externo`
- [ ] Cuando admin cambia `user_id` pero no hay `vendedor_externo` → Log warning, no sincroniza
- [ ] Si usuario tiene mapeo en `nesto.vendedor` → Se actualiza `vendedor_externo` y sincroniza

### UI y Configuración

- [ ] Menú "Vendedores Nesto" accesible en Configuración → Sincronización Nesto
- [ ] Formulario permite crear/editar mapeos manuales
- [ ] Vista tree muestra todos los mapeos existentes

### Tests

- [ ] Todos los tests en `test_vendedor_transformer.py` pasan
- [ ] Test end-to-end: Publicar cliente desde Nesto → Vendedor asignado en Odoo
- [ ] Test bidireccional: Cambiar vendedor en Odoo → Actualizado en Nesto

### Documentación

- [ ] README actualizado con sección de vendedores
- [ ] Guía "Qué hacer si vendedor no se mapea"
- [ ] Changelog actualizado (v2.9.0)

---

**Issue creada**: [Fecha]
**Asignado a**: [Desarrollador]
**Sprint**: [Siguiente sesión]
**Etiquetas**: `enhancement`, `sync`, `vendedores`, `phase-1`
