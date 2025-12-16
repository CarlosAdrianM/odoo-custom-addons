# Requerimientos para NestoAPI: Sincronización de Vendedores

> **Destinatario**: Equipo de desarrollo NestoAPI (C# / WebApi)
> **Fecha**: 2025-12-12 (Actualizado: 2025-12-16)
> **Issue relacionada**: [ISSUE_SINCRONIZACION_VENDEDORES.md](ISSUE_SINCRONIZACION_VENDEDORES.md)

---

## 📋 Resumen

Para implementar la sincronización de vendedores en clientes, usamos **solo el email como fuente de verdad**. Cada sistema (Odoo, Nesto, Prestashop) resuelve el código de vendedor desde el email de forma independiente.

**Principio clave**: `VendedorEmail` es el identificador universal. El código `Vendedor` es específico de cada sistema.

**Cambios necesarios**:
1. ✅ Añadir campo `VendedorEmail` al mensaje de cliente (obligatorio)
2. ✅ Añadir campo `Vendedor` al mensaje (informativo, para otros sistemas)
3. ✅ Hacer JOIN con tabla `Vendedores` para obtener el email
4. ✅ **Procesar `VendedorEmail` en mensajes entrantes** → resolver código por email

---

## 🏗️ Arquitectura: Patrón PubSub Puro

**IMPORTANTE**: Todos los sistemas (Odoo, Nesto, Prestashop futuro, etc.) son **peers** que:
- **Publican** mensajes al topic PubSub
- **Se suscriben** al topic para recibir mensajes

```
                    ┌─────────────────┐
                    │   PubSub Topic  │
                    │ sincronizacion- │
                    │     tablas      │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
     ┌──────────┐      ┌──────────┐      ┌──────────┐
     │   Odoo   │      │  Nesto   │      │Prestashop│
     │          │      │          │      │ (futuro) │
     └──────────┘      └──────────┘      └──────────┘
           │                 │                 │
           │   PUBLICA       │   PUBLICA       │
           └────────►  PubSub  ◄────────────────┘
```

**NO hay endpoints directos entre sistemas**. Todo pasa por PubSub.

---

## 🔴 Cambios Requeridos en NestoAPI

### 1. Añadir Campos al Mensaje de Cliente (Publicación)

**Ubicación**: Donde se construye el mensaje de cliente para publicar a PubSub

**Campos actuales** (ejemplo):
```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Nombre": "Cliente Ejemplo S.L.",
  "Direccion": "Calle Ejemplo 123",
  "Nif": "B12345678",
  "Telefono": "912345678",
  "Provincia": "28",
  "CodigoPostal": "28001",
  "Poblacion": "Madrid",
  "Estado": 0,
  "PersonasContacto": [...]
}
```

**Campos a AÑADIR** (2 nuevos):
```json
{
  "Cliente": "12345",
  "Contacto": "0",
  // ... campos existentes ...

  // ⬇️ NUEVOS CAMPOS
  "Vendedor": "001",                      // Clientes.Vendedor (CHAR(3))
  "VendedorEmail": "juan@nuevavision.es"  // Vendedores.Mail (VARCHAR) - JOIN
}
```

**Nota**: `VendedorNombre` NO es necesario. Cada sistema tiene su propia forma de almacenar nombres.

### 2. Query SQL con JOIN

**Pseudocódigo C#**:

```csharp
public ClienteDTO BuildClienteMessage(string empresa, string cliente, string contacto)
{
    var clienteData = dbContext.Clientes
        .Where(c => c.Empresa == empresa &&
                    c.NºCliente == cliente &&
                    c.Contacto == contacto)
        .FirstOrDefault();

    if (clienteData == null) return null;

    // ⬇️ NUEVO: JOIN con tabla Vendedores para obtener email
    var vendedor = dbContext.Vendedores
        .Where(v => v.Empresa == clienteData.Empresa &&
                    v.Número == clienteData.Vendedor)
        .FirstOrDefault();

    return new ClienteDTO
    {
        Cliente = clienteData.NºCliente,
        Contacto = clienteData.Contacto,
        Nombre = clienteData.Nombre,
        // ... resto de campos existentes ...

        // ⬇️ NUEVOS CAMPOS
        Vendedor = clienteData.Vendedor,    // CHAR(3) - Ej: "001"
        VendedorEmail = vendedor?.Mail      // VARCHAR - Ej: "juan@nv.es"
    };
}
```

**SQL equivalente**:
```sql
SELECT
    c.Empresa,
    c.[Nº Cliente] AS Cliente,
    c.Contacto,
    c.Nombre,
    c.Dirección,
    c.Vendedor,
    -- ... otros campos ...

    -- ⬇️ NUEVO: JOIN con Vendedores
    v.Mail AS VendedorEmail

FROM Clientes c
LEFT JOIN Vendedores v ON v.Empresa = c.Empresa
                       AND v.Número = c.Vendedor

WHERE c.Empresa = @empresa
  AND c.[Nº Cliente] = @cliente
  AND c.Contacto = @contacto;
```

### 3. Actualizar DTO

**Añadir propiedades** a la clase `ClienteDTO`:

```csharp
public class ClienteDTO
{
    // ... propiedades existentes ...
    public string Cliente { get; set; }
    public string Contacto { get; set; }
    public string Nombre { get; set; }
    // ...

    // ⬇️ NUEVAS PROPIEDADES
    [JsonProperty("Vendedor")]
    public string Vendedor { get; set; }

    [JsonProperty("VendedorEmail")]
    public string VendedorEmail { get; set; }
}
```

### 4. Validaciones Recomendadas

```csharp
// Validación 1: Cliente sin vendedor asignado
if (string.IsNullOrWhiteSpace(dto.Vendedor))
{
    _logger.LogWarning($"Cliente {dto.Cliente}-{dto.Contacto} sin vendedor asignado");
    dto.Vendedor = null;
    dto.VendedorEmail = null;
}

// Validación 2: Vendedor sin email (auto-mapeo fallará en otros sistemas)
else if (string.IsNullOrWhiteSpace(dto.VendedorEmail))
{
    _logger.LogWarning(
        $"Vendedor {dto.Vendedor} del cliente {dto.Cliente}-{dto.Contacto} " +
        $"sin email. Auto-mapeo por email fallará."
    );
    // Publicar de todas formas con solo el código
}
```

### 5. Procesar Mensajes Entrantes (Suscripción) - SIEMPRE POR EMAIL

NestoAPI ya está suscrito al topic PubSub. Cuando reciba un mensaje de actualización de cliente desde Odoo (u otro sistema), debe procesar **solo el campo `VendedorEmail`**.

#### ⚠️ IMPORTANTE: Odoo solo envía VendedorEmail

Odoo **nunca** envía el código de vendedor. Solo envía el email del usuario asignado:

```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "VendedorEmail": "inakimartinez@nuevavision.es"  // ← Solo email
  // ... otros campos ...
}
```

**NestoAPI SIEMPRE debe resolver el código de vendedor desde el email.**

```csharp
// Al recibir mensaje de PubSub con actualización de cliente
public async Task ProcessClienteUpdate(ClienteUpdateMessage message)
{
    var cliente = await dbContext.Clientes
        .Where(c => c.Empresa == message.Empresa &&
                    c.NºCliente == message.Cliente &&
                    c.Contacto == message.Contacto)
        .FirstOrDefaultAsync();

    if (cliente == null)
    {
        _logger.LogWarning($"Cliente {message.Cliente}-{message.Contacto} no encontrado");
        return;
    }

    // ⬇️ Procesar cambio de vendedor POR EMAIL
    await ProcessVendedorByEmail(cliente, message);

    // Procesar otros campos...
    // ...

    cliente.FechaModificacion = DateTime.Now;
    cliente.Usuario = "PubSub";

    await dbContext.SaveChangesAsync();
}

/// <summary>
/// Procesa cambio de vendedor SIEMPRE por email
/// El email es la única fuente de verdad para identificar vendedores
/// </summary>
private async Task ProcessVendedorByEmail(Cliente cliente, ClienteUpdateMessage message)
{
    string vendedorEmail = message.VendedorEmail?.Trim().ToLower();

    // Si no viene email, no hacer nada
    if (string.IsNullOrWhiteSpace(vendedorEmail))
    {
        _logger.LogDebug($"Cliente {cliente.NºCliente}: Sin VendedorEmail en mensaje");
        return;
    }

    // Buscar vendedor por email
    var vendedor = await dbContext.Vendedores
        .Where(v => v.Empresa == cliente.Empresa &&
                    v.Mail.ToLower() == vendedorEmail)
        .FirstOrDefaultAsync();

    if (vendedor != null)
    {
        cliente.Vendedor = vendedor.Número;
        _logger.LogInformation(
            $"Vendedor asignado por email: Cliente {cliente.NºCliente} → " +
            $"Email {vendedorEmail} → Vendedor {vendedor.Número}");
    }
    else
    {
        _logger.LogWarning(
            $"No se encontró vendedor con email {vendedorEmail} en Nesto. " +
            $"Cliente {cliente.NºCliente} no actualizado.");
    }
}
```

---

## 🔄 Flujos Completos

### Flujo 1: Nesto → Otros Sistemas (Publicación)

```
1. Usuario crea/modifica cliente en Nesto
         ↓
2. Trigger SQL detecta cambio
         ↓
3. NestoAPI construye mensaje con:
   - Vendedor: "001"
   - VendedorEmail: "juan@nuevavision.es"
         ↓
4. NestoAPI PUBLICA mensaje a PubSub
         ↓
5. Sistemas suscritos (Odoo, Prestashop, etc.) reciben mensaje
         ↓
6. Cada sistema procesa según sus reglas:
   - Odoo: Auto-mapea por email → user_id
   - Prestashop: Usa el código para su lógica
```

### Flujo 2: Odoo → Nesto (Suscripción) - SIEMPRE POR EMAIL

```
1. Usuario cambia vendedor en Odoo (selecciona usuario)
         ↓
2. Odoo PUBLICA mensaje a PubSub:
   {
     "Tabla": "Clientes",
     "Cliente": "12345",
     "Contacto": "0",
     "VendedorEmail": "inaki@nuevavision.es"  // ← Solo email
   }
         ↓
3. NestoAPI (SUSCRITO) recibe mensaje
         ↓
4. NestoAPI busca en tabla Vendedores: WHERE Mail = 'inaki@nuevavision.es'
         ↓
5. Encuentra vendedor "IMZ" → Actualiza Clientes.Vendedor = "IMZ"
         ↓
6. Cambio guardado en BD Nesto ✅
```

---

## ✅ Checklist de Implementación

### Publicación (Nesto → PubSub)

- [ ] **Modificar DTO**: Añadir propiedades `Vendedor`, `VendedorEmail`
- [ ] **Modificar query**: Hacer LEFT JOIN con tabla `Vendedores`
- [ ] **Añadir validaciones**:
  - [ ] Cliente sin vendedor → campos null
  - [ ] Vendedor sin email → solo código, email null
- [ ] **Testing**:
  - [ ] Cliente con vendedor válido → Campos completos
  - [ ] Cliente sin vendedor → Campos null
  - [ ] Vendedor sin email → Solo código

### Suscripción (PubSub → Nesto)

- [ ] **Procesar campo `VendedorEmail`** en mensajes entrantes (SIEMPRE por email)
- [ ] **Buscar vendedor** por email en tabla `Vendedores`
- [ ] **Si existe** → usar código para actualizar `Clientes.Vendedor`
- [ ] **Si no existe** → log warning, no actualizar vendedor
- [ ] **Testing**:
  - [ ] Mensaje con VendedorEmail válido → Actualiza
  - [ ] Mensaje con VendedorEmail inexistente → Log warning, no actualiza
  - [ ] Mensaje sin VendedorEmail → No modifica vendedor

---

## 📊 Datos de Ejemplo

### Ejemplo de Cliente CON Vendedor

**Mensaje PubSub** (Nesto publica):
```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Nombre": "Peluquería Ejemplo S.L.",
  "Direccion": "Calle Mayor 1",
  "Telefono": "912345678",
  "Vendedor": "001",
  "VendedorEmail": "juan.perez@nuevavision.es"
}
```

### Ejemplo de Cliente SIN Vendedor

**Mensaje PubSub**:
```json
{
  "Cliente": "67890",
  "Contacto": "0",
  "Nombre": "Cliente Sin Vendedor S.L.",
  "Vendedor": null,
  "VendedorEmail": null
}
```

### Ejemplo de Vendedor SIN Email

**Mensaje PubSub**:
```json
{
  "Cliente": "11111",
  "Contacto": "0",
  "Nombre": "Cliente con Vendedor Sin Email",
  "Vendedor": "099",
  "VendedorEmail": null
}
```

---

## 🔧 Troubleshooting

### Problema 1: "VendedorEmail siempre viene null"

**Causa**: Query no hace JOIN con tabla Vendedores

**Solución**:
```csharp
// ✅ BIEN - Con JOIN
var vendedor = dbContext.Vendedores
    .Where(v => v.Empresa == cliente.Empresa &&
                v.Número == cliente.Vendedor)
    .FirstOrDefault();
dto.VendedorEmail = vendedor?.Mail;
```

### Problema 2: "Performance lento con miles de clientes"

**Causa**: JOIN sin índices

**Solución**:
```sql
-- Crear índice en tabla Vendedores si no existe
CREATE NONCLUSTERED INDEX IX_Vendedores_Empresa_Numero
ON Vendedores (Empresa, Número)
INCLUDE (Mail);
```

---

## ✅ Criterios de Aceptación

### Publicación (Nesto → PubSub)
1. ✅ Mensaje de cliente incluye `VendedorEmail` (obligatorio) y `Vendedor` (informativo)
2. ✅ Si cliente tiene vendedor válido → Ambos campos completos
3. ✅ Si cliente sin vendedor → Campos vienen como `null`
4. ✅ Si vendedor sin email → `VendedorEmail` es `null`, `Vendedor` tiene código

### Suscripción (PubSub → Nesto)
5. ✅ NestoAPI procesa **solo** campo `VendedorEmail` en mensajes entrantes
6. ✅ **SIEMPRE busca vendedor por email** → resuelve código desde email
7. ✅ **Si email existe** → Actualiza `Clientes.Vendedor` con el código encontrado
8. ✅ **Si email no existe** → Log warning, no actualiza vendedor

### General
9. ✅ No rompe sincronización de clientes existente
10. ✅ Performance similar a mensajes actuales (<100ms por mensaje)

---

**Fecha de entrega estimada**: Próxima sesión de desarrollo
**Prioridad**: Alta
