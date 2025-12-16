# Requerimientos para NestoAPI: Sincronización de Vendedores

> **Destinatario**: Equipo de desarrollo NestoAPI (C# / WebApi)
> **Fecha**: 2025-12-12 (Actualizado: 2025-12-16)
> **Issue relacionada**: [ISSUE_SINCRONIZACION_VENDEDORES.md](ISSUE_SINCRONIZACION_VENDEDORES.md)

---

## 📋 Resumen

Para implementar la sincronización de vendedores en clientes, necesitamos que NestoAPI publique información adicional del vendedor en los mensajes de PubSub de clientes.

**Cambios necesarios**:
1. ✅ Añadir 2 campos nuevos al mensaje de cliente: `Vendedor` y `VendedorEmail`
2. ✅ Hacer JOIN con tabla `Vendedores` para obtener el email
3. ✅ Procesar campo `Vendedor` en mensajes entrantes (ya suscrito a PubSub)

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

### 5. Procesar Mensajes Entrantes (Suscripción) - CON AUTO-MAPEO POR EMAIL

NestoAPI ya está suscrito al topic PubSub. Cuando reciba un mensaje de actualización de cliente desde Odoo (u otro sistema), debe procesar el campo `Vendedor`.

#### ⚠️ CASO ESPECIAL: Vendedor vacío + VendedorEmail presente

Cuando Odoo cambia el vendedor de un cliente seleccionando un usuario diferente, **Odoo no conoce el código del vendedor en Nesto**. En este caso, Odoo envía:

```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Vendedor": "",                              // ← Vacío (Odoo no conoce el código)
  "VendedorEmail": "inakimartinez@nuevavision.es"  // ← Email del nuevo vendedor
}
```

**NestoAPI debe hacer reverse lookup**: buscar el código de vendedor por email.

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

    // ⬇️ NUEVO: Procesar cambio de vendedor
    await ProcessVendedorChange(cliente, message);

    // Procesar otros campos...
    // ...

    cliente.FechaModificacion = DateTime.Now;
    cliente.Usuario = "PubSub";

    await dbContext.SaveChangesAsync();
}

/// <summary>
/// Procesa cambio de vendedor con auto-mapeo por email cuando el código viene vacío
/// </summary>
private async Task ProcessVendedorChange(Cliente cliente, ClienteUpdateMessage message)
{
    string vendedorCodigo = message.Vendedor?.Trim();
    string vendedorEmail = message.VendedorEmail?.Trim().ToLower();

    // CASO 1: Viene código de vendedor válido → usar directamente
    if (!string.IsNullOrWhiteSpace(vendedorCodigo))
    {
        var vendedorExiste = await dbContext.Vendedores
            .AnyAsync(v => v.Empresa == cliente.Empresa &&
                          v.Número == vendedorCodigo);

        if (vendedorExiste)
        {
            cliente.Vendedor = vendedorCodigo;
            _logger.LogInformation(
                $"Vendedor actualizado: Cliente {cliente.NºCliente} → Vendedor {vendedorCodigo}");
        }
        else
        {
            _logger.LogWarning(
                $"Vendedor {vendedorCodigo} no existe en Nesto, ignorando");
        }
        return;
    }

    // CASO 2: Código vacío + Email presente → AUTO-MAPEO POR EMAIL
    if (!string.IsNullOrWhiteSpace(vendedorEmail))
    {
        var vendedor = await dbContext.Vendedores
            .Where(v => v.Empresa == cliente.Empresa &&
                        v.Mail.ToLower() == vendedorEmail)
            .FirstOrDefaultAsync();

        if (vendedor != null)
        {
            cliente.Vendedor = vendedor.Número;
            _logger.LogInformation(
                $"Vendedor auto-mapeado por email: Cliente {cliente.NºCliente} → " +
                $"Email {vendedorEmail} → Vendedor {vendedor.Número}");
        }
        else
        {
            _logger.LogWarning(
                $"No se encontró vendedor con email {vendedorEmail} en Nesto. " +
                $"Cliente {cliente.NºCliente} no actualizado.");
        }
        return;
    }

    // CASO 3: Ni código ni email → no hacer nada
    _logger.LogDebug($"Cliente {cliente.NºCliente}: Sin datos de vendedor en mensaje");
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

### Flujo 2: Otros Sistemas → Nesto (Suscripción) - CON CÓDIGO

```
1. Usuario cambia vendedor en Odoo (cliente que YA tenía vendedor_externo)
         ↓
2. Odoo PUBLICA mensaje a PubSub:
   {
     "Tabla": "Clientes",
     "Cliente": "12345",
     "Contacto": "0",
     "Vendedor": "002",                    // ← Odoo conoce el código
     "VendedorEmail": "maria@nuevavision.es"
   }
         ↓
3. NestoAPI (SUSCRITO) recibe mensaje
         ↓
4. NestoAPI valida que vendedor "002" existe
         ↓
5. NestoAPI actualiza Clientes.Vendedor = "002"
         ↓
6. Cambio guardado en BD Nesto ✅
```

### Flujo 3: Otros Sistemas → Nesto (Suscripción) - SIN CÓDIGO (Auto-mapeo por Email)

```
1. Usuario cambia vendedor en Odoo (selecciona usuario, pero NO conoce código Nesto)
         ↓
2. Odoo PUBLICA mensaje a PubSub:
   {
     "Tabla": "Clientes",
     "Cliente": "12345",
     "Contacto": "0",
     "Vendedor": "",                       // ← Vacío (Odoo no conoce el código)
     "VendedorEmail": "inaki@nuevavision.es"  // ← Solo email del usuario seleccionado
   }
         ↓
3. NestoAPI (SUSCRITO) recibe mensaje
         ↓
4. NestoAPI detecta Vendedor vacío + VendedorEmail presente
         ↓
5. NestoAPI busca en tabla Vendedores: WHERE Mail = 'inaki@nuevavision.es'
         ↓
6. Encuentra vendedor "IMZ" → Actualiza Clientes.Vendedor = "IMZ"
         ↓
7. Cambio guardado en BD Nesto ✅
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

- [ ] **Procesar campo `Vendedor`** en mensajes entrantes
- [ ] **Validar** que vendedor existe antes de actualizar
- [ ] **⚠️ AUTO-MAPEO POR EMAIL**: Si `Vendedor` vacío + `VendedorEmail` presente:
  - [ ] Buscar vendedor por email en tabla `Vendedores`
  - [ ] Si existe → usar ese código
  - [ ] Si no existe → log warning, no actualizar
- [ ] **Logs** cuando vendedor no existe
- [ ] **Testing**:
  - [ ] Mensaje con vendedor válido → Actualiza
  - [ ] Mensaje con vendedor inexistente → Log warning, no actualiza
  - [ ] **Mensaje con Vendedor="" + VendedorEmail válido → Auto-mapea y actualiza**
  - [ ] **Mensaje con Vendedor="" + VendedorEmail inexistente → Log warning, no actualiza**

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
1. ✅ Mensaje de cliente incluye 2 campos nuevos: `Vendedor`, `VendedorEmail`
2. ✅ Si cliente tiene vendedor válido → Campos completos
3. ✅ Si cliente sin vendedor → Campos vienen como `null`
4. ✅ Si vendedor sin email → `VendedorEmail` es `null`, `Vendedor` tiene código

### Suscripción (PubSub → Nesto)
5. ✅ NestoAPI procesa campo `Vendedor` en mensajes entrantes
6. ✅ **Si `Vendedor` tiene código válido → Actualiza directamente**
7. ✅ **Si `Vendedor` vacío + `VendedorEmail` presente → Auto-mapea por email y actualiza**
8. ✅ **Si `VendedorEmail` no existe en tabla Vendedores → Log warning, no actualiza vendedor**

### General
9. ✅ No rompe sincronización de clientes existente
10. ✅ Performance similar a mensajes actuales (<100ms por mensaje)

---

**Fecha de entrega estimada**: Próxima sesión de desarrollo
**Prioridad**: Alta
