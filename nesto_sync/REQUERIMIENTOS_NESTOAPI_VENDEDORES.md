# Requerimientos para NestoAPI: Sincronización de Vendedores

> **Destinatario**: Equipo de desarrollo NestoAPI (C# / WebApi)
> **Fecha**: 2025-12-12
> **Issue relacionada**: [ISSUE_SINCRONIZACION_VENDEDORES.md](ISSUE_SINCRONIZACION_VENDEDORES.md)

---

## 📋 Resumen

Para implementar la sincronización de vendedores en clientes, necesitamos que NestoAPI publique información adicional del vendedor en los mensajes de PubSub de clientes.

**Cambios necesarios**:
1. ✅ Añadir 3 campos nuevos al mensaje de cliente
2. ✅ Hacer JOIN con tabla `Vendedores`
3. ✅ Implementar endpoint para recibir actualizaciones desde Odoo (opcional, Fase 1b)

---

## 🔴 FASE 1A: Nesto → Odoo (PRIORITARIO)

### Cambio en Mensaje PubSub de Cliente

**Ubicación**: `NestoAPI/Services/PubSubPublisher.cs` (o archivo similar)

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

**Campos a AÑADIR** (3 nuevos):
```json
{
  "Cliente": "12345",
  "Contacto": "0",
  // ... campos existentes ...

  // ⬇️ NUEVOS CAMPOS (Fase 1A)
  "Vendedor": "001",                     // Clientes.Vendedor (CHAR(3))
  "VendedorEmail": "juan@nuevavision.es", // Vendedores.Mail (VARCHAR)
  "VendedorNombre": "Juan Pérez"         // Vendedores.Descripción (VARCHAR)
}
```

### Query SQL Necesario en NestoAPI

**Pseudocódigo C#**:

```csharp
// Método: BuildClienteMessage() o similar
// Ubicación: Services/PubSubPublisher.cs o Controllers/ClientesController.cs

public ClienteDTO BuildClienteMessage(string empresa, string cliente, string contacto)
{
    // Query actual (aproximado)
    var clienteData = dbContext.Clientes
        .Where(c => c.Empresa == empresa &&
                    c.NºCliente == cliente &&
                    c.Contacto == contacto)
        .FirstOrDefault();

    if (clienteData == null) return null;

    // ⬇️ NUEVO: JOIN con tabla Vendedores
    var vendedor = dbContext.Vendedores
        .Where(v => v.Empresa == clienteData.Empresa &&
                    v.Número == clienteData.Vendedor)
        .FirstOrDefault();

    // Construir DTO
    return new ClienteDTO
    {
        Cliente = clienteData.NºCliente,
        Contacto = clienteData.Contacto,
        Nombre = clienteData.Nombre,
        Direccion = clienteData.Dirección,
        // ... resto de campos existentes ...

        // ⬇️ NUEVOS CAMPOS
        Vendedor = clienteData.Vendedor,           // CHAR(3) - Ej: "001"
        VendedorEmail = vendedor?.Mail,            // VARCHAR - Ej: "juan@nv.es"
        VendedorNombre = vendedor?.Descripción     // VARCHAR - Ej: "Juan Pérez"
    };
}
```

**SQL equivalente** (para referencia):
```sql
SELECT
    c.Empresa,
    c.[Nº Cliente] AS Cliente,
    c.Contacto,
    c.Nombre,
    c.Dirección,
    c.Vendedor,
    -- ... otros campos ...

    -- ⬇️ NUEVOS: JOIN con Vendedores
    v.Mail AS VendedorEmail,
    v.Descripción AS VendedorNombre

FROM Clientes c
LEFT JOIN Vendedores v ON v.Empresa = c.Empresa
                       AND v.Número = c.Vendedor

WHERE c.Empresa = @empresa
  AND c.[Nº Cliente] = @cliente
  AND c.Contacto = @contacto;
```

### Validaciones Recomendadas

**Antes de publicar** el mensaje a PubSub:

```csharp
// Validación 1: Cliente sin vendedor asignado
if (string.IsNullOrWhiteSpace(dto.Vendedor))
{
    _logger.LogWarning($"Cliente {dto.Cliente}-{dto.Contacto} sin vendedor asignado");
    // No incluir campos de vendedor en el mensaje
    dto.Vendedor = null;
    dto.VendedorEmail = null;
    dto.VendedorNombre = null;
}

// Validación 2: Vendedor sin email (auto-mapeo fallará en Odoo)
else if (string.IsNullOrWhiteSpace(dto.VendedorEmail))
{
    _logger.LogWarning(
        $"Vendedor {dto.Vendedor} del cliente {dto.Cliente}-{dto.Contacto} " +
        $"sin email. Auto-mapeo fallará en Odoo."
    );
    // Publicar de todas formas, Odoo usará fallback manual
}

// Validación 3: Vendedor no existe en tabla Vendedores
else if (vendedor == null)
{
    _logger.LogWarning(
        $"Vendedor {dto.Vendedor} del cliente {dto.Cliente}-{dto.Contacto} " +
        $"no encontrado en tabla Vendedores"
    );
    // Publicar solo código, sin email ni nombre
    dto.VendedorEmail = null;
    dto.VendedorNombre = null;
}
```

### DTO (Data Transfer Object)

**Añadir propiedades** a la clase `ClienteDTO` (o similar):

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

    [JsonProperty("VendedorNombre")]
    public string VendedorNombre { get; set; }
}
```

---

## 🔵 FASE 1B: Odoo → Nesto (OPCIONAL, menor prioridad)

### Endpoint para Recibir Actualizaciones desde Odoo

Cuando un usuario cambia el vendedor asignado a un cliente en Odoo, Odoo publicará un mensaje a PubSub que NestoAPI debe procesar.

**Ubicación**: `NestoAPI/Controllers/ClientesController.cs` (o similar)

**Endpoint nuevo** (o ampliar uno existente):

```csharp
[HttpPost]
[Route("api/clientes/actualizar")]
public async Task<IActionResult> ActualizarCliente([FromBody] ClienteUpdateDTO dto)
{
    try
    {
        // Validar datos de entrada
        if (string.IsNullOrWhiteSpace(dto.Empresa) ||
            string.IsNullOrWhiteSpace(dto.Cliente) ||
            string.IsNullOrWhiteSpace(dto.Contacto))
        {
            return BadRequest("Empresa, Cliente y Contacto son obligatorios");
        }

        // Buscar cliente
        var cliente = await _dbContext.Clientes
            .Where(c => c.Empresa == dto.Empresa &&
                        c.NºCliente == dto.Cliente &&
                        c.Contacto == dto.Contacto)
            .FirstOrDefaultAsync();

        if (cliente == null)
        {
            return NotFound($"Cliente {dto.Cliente}-{dto.Contacto} no encontrado");
        }

        // Procesar solo los campos que vienen en el DTO
        // (Odoo solo enviará campos modificados)

        // ⬇️ NUEVO: Actualizar vendedor
        if (!string.IsNullOrWhiteSpace(dto.Vendedor))
        {
            // Validar que el vendedor existe
            var vendedor = await _dbContext.Vendedores
                .Where(v => v.Empresa == dto.Empresa &&
                            v.Número == dto.Vendedor)
                .FirstOrDefaultAsync();

            if (vendedor == null)
            {
                return BadRequest($"Vendedor {dto.Vendedor} no existe en tabla Vendedores");
            }

            // Actualizar
            cliente.Vendedor = dto.Vendedor;
        }

        // Actualizar otros campos si vienen en el DTO
        // (nombre, dirección, teléfono, etc.)

        // Campos de auditoría
        cliente.Usuario = User.Identity?.Name ?? "Odoo";
        cliente.FechaModificacion = DateTime.Now;

        // Guardar cambios
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation(
            $"Cliente {dto.Cliente}-{dto.Contacto} actualizado desde Odoo. " +
            $"Vendedor: {dto.Vendedor}"
        );

        return Ok(new {
            success = true,
            message = "Cliente actualizado correctamente",
            vendedor = dto.Vendedor
        });
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, $"Error al actualizar cliente {dto.Cliente}");
        return StatusCode(500, "Error interno del servidor");
    }
}
```

**DTO para actualizaciones**:

```csharp
public class ClienteUpdateDTO
{
    [Required]
    public string Empresa { get; set; }

    [Required]
    public string Cliente { get; set; }

    [Required]
    public string Contacto { get; set; }

    // Campos opcionales (solo se actualizan si vienen en el JSON)
    public string Vendedor { get; set; }
    public string Nombre { get; set; }
    public string Direccion { get; set; }
    // ... otros campos según necesidad ...
}
```

**Ejemplo de request desde Odoo**:

```http
POST /api/clientes/actualizar HTTP/1.1
Content-Type: application/json

{
  "Empresa": "001",
  "Cliente": "12345",
  "Contacto": "0",
  "Vendedor": "002"
}
```

---

## 🔄 Flujo Completo

### Flujo 1: Nesto → Odoo (Creación/Actualización de Cliente)

```
1. Usuario crea/modifica cliente en Nesto
         ↓
2. Trigger SQL detecta cambio
         ↓
3. NestoAPI recibe notificación
         ↓
4. NestoAPI hace JOIN con tabla Vendedores
         ↓
5. NestoAPI construye mensaje con:
   - Vendedor: "001"
   - VendedorEmail: "juan@nuevavision.es"
   - VendedorNombre: "Juan Pérez"
         ↓
6. NestoAPI publica mensaje a PubSub
         ↓
7. Odoo recibe mensaje
         ↓
8. VendedorTransformer de Odoo:
   a) Busca usuario por email (auto-mapeo)
   b) Si falla, busca en tabla nesto.vendedor (fallback)
   c) Asigna user_id al cliente
         ↓
9. Cliente guardado en Odoo con vendedor asignado ✅
```

### Flujo 2: Odoo → Nesto (Cambio de Vendedor)

```
1. Usuario cambia vendedor de cliente en Odoo
         ↓
2. BidirectionalSyncMixin detecta cambio
         ↓
3. Odoo publica mensaje a PubSub:
   {
     "Tabla": "Clientes",
     "Operacion": "UPDATE",
     "Datos": {
       "Cliente": "12345",
       "Contacto": "0",
       "Vendedor": "002"
     }
   }
         ↓
4. NestoAPI recibe mensaje de PubSub
         ↓
5. NestoAPI llama a endpoint /api/clientes/actualizar
         ↓
6. Valida que vendedor "002" existe
         ↓
7. Actualiza Clientes.Vendedor = "002"
         ↓
8. Guarda en base de datos ✅
```

---

## ✅ Checklist de Implementación en NestoAPI

### Fase 1A: Nesto → Odoo (PRIORITARIO)

- [ ] **Modificar DTO**: Añadir propiedades `Vendedor`, `VendedorEmail`, `VendedorNombre`
- [ ] **Modificar query**: Hacer LEFT JOIN con tabla `Vendedores`
- [ ] **Añadir validaciones**:
  - [ ] Cliente sin vendedor
  - [ ] Vendedor sin email
  - [ ] Vendedor no existe en tabla
- [ ] **Actualizar logs**: Registrar warnings cuando falten datos
- [ ] **Testing**:
  - [ ] Cliente con vendedor válido → Campos completos
  - [ ] Cliente sin vendedor → Campos null
  - [ ] Vendedor sin email → Solo código, email=null

### Fase 1B: Odoo → Nesto (OPCIONAL)

- [ ] **Crear endpoint**: POST `/api/clientes/actualizar`
- [ ] **Validar vendedor**: Verificar que existe en tabla `Vendedores`
- [ ] **Actualizar cliente**: `UPDATE Clientes SET Vendedor = @vendedor WHERE ...`
- [ ] **Logs**: Registrar actualizaciones desde Odoo
- [ ] **Testing**:
  - [ ] Actualización con vendedor válido → OK
  - [ ] Actualización con vendedor inexistente → BadRequest
  - [ ] Cliente inexistente → NotFound

---

## 📊 Datos de Ejemplo

### Ejemplo de Cliente CON Vendedor

**Nesto → Odoo** (mensaje PubSub):
```json
{
  "Cliente": "12345",
  "Contacto": "0",
  "Nombre": "Peluquería Ejemplo S.L.",
  "Direccion": "Calle Mayor 1",
  "Telefono": "912345678",
  "Vendedor": "001",
  "VendedorEmail": "juan.perez@nuevavision.es",
  "VendedorNombre": "Juan Pérez"
}
```

**Resultado en Odoo**:
- Cliente: "Peluquería Ejemplo S.L."
- Vendedor (user_id): Juan Pérez (auto-mapeado por email)
- vendedor_externo: "001"

### Ejemplo de Cliente SIN Vendedor

**Nesto → Odoo** (mensaje PubSub):
```json
{
  "Cliente": "67890",
  "Contacto": "0",
  "Nombre": "Cliente Sin Vendedor S.L.",
  "Direccion": "Calle Menor 2",
  "Telefono": "912345679",
  "Vendedor": null,
  "VendedorEmail": null,
  "VendedorNombre": null
}
```

**Resultado en Odoo**:
- Cliente: "Cliente Sin Vendedor S.L."
- Vendedor (user_id): (vacío)
- vendedor_externo: (vacío)
- Log: "Cliente sin vendedor asignado" (info, no error)

### Ejemplo de Vendedor SIN Email

**Nesto → Odoo** (mensaje PubSub):
```json
{
  "Cliente": "11111",
  "Contacto": "0",
  "Nombre": "Cliente con Vendedor Sin Email",
  "Vendedor": "099",
  "VendedorEmail": null,
  "VendedorNombre": "Vendedor Antiguo"
}
```

**Resultado en Odoo**:
- Cliente: "Cliente con Vendedor Sin Email"
- Vendedor (user_id): (vacío - auto-mapeo falla)
- vendedor_externo: "099" (se guarda para referencia)
- Log: "⚠️ Vendedor 099 sin email. Auto-mapeo fallará"
- **Solución**: Admin debe crear mapeo manual en Odoo

---

## 🔧 Troubleshooting

### Problema 1: "VendedorEmail siempre viene null"

**Causa**: Query no hace JOIN con tabla Vendedores

**Solución**:
```csharp
// ❌ MAL - Sin JOIN
var cliente = dbContext.Clientes.Find(empresa, nroCliente, contacto);
dto.Vendedor = cliente.Vendedor;  // Solo código
dto.VendedorEmail = null;         // ❌ Falta JOIN

// ✅ BIEN - Con JOIN
var vendedor = dbContext.Vendedores
    .Where(v => v.Empresa == cliente.Empresa &&
                v.Número == cliente.Vendedor)
    .FirstOrDefault();
dto.VendedorEmail = vendedor?.Mail;  // ✅
```

### Problema 2: "Vendedor no se actualiza desde Odoo"

**Causa**: Endpoint no implementado o URL incorrecta

**Solución**:
1. Verificar que endpoint `/api/clientes/actualizar` existe
2. Verificar que Odoo tiene la URL correcta configurada
3. Revisar logs de NestoAPI para ver si llegan requests

### Problema 3: "Performance lento con miles de clientes"

**Causa**: JOIN sin índices

**Solución**:
```sql
-- Crear índice en tabla Vendedores si no existe
CREATE NONCLUSTERED INDEX IX_Vendedores_Empresa_Numero
ON Vendedores (Empresa, Número)
INCLUDE (Mail, Descripción);
```

---

## 📞 Contacto

**Dudas sobre la implementación**:
- Revisar: [ISSUE_SINCRONIZACION_VENDEDORES.md](ISSUE_SINCRONIZACION_VENDEDORES.md)
- Análisis técnico: [PROPUESTA_SINCRONIZACION_VENDEDORES_v2.md](PROPUESTA_SINCRONIZACION_VENDEDORES_v2.md)

**Testing coordinado**:
- Ambiente: Desarrollo (Odoo18 + NestoAPI dev)
- Plan: Sincronizar 10 clientes de prueba con vendedores variados

---

## ✅ Criterios de Aceptación

### Para considerar Fase 1A completa:

1. ✅ Mensaje de cliente incluye 3 campos nuevos: `Vendedor`, `VendedorEmail`, `VendedorNombre`
2. ✅ Si cliente tiene vendedor válido → Campos completos
3. ✅ Si cliente sin vendedor → Campos vienen como `null`
4. ✅ Si vendedor sin email → `VendedorEmail` es `null`, otros campos completos
5. ✅ Logs claros cuando faltan datos
6. ✅ No rompe sincronización de clientes existente
7. ✅ Performance similar a mensajes actuales (<100ms por mensaje)

### Para considerar Fase 1B completa (opcional):

1. ✅ Endpoint `/api/clientes/actualizar` acepta cambio de vendedor
2. ✅ Valida que vendedor existe antes de actualizar
3. ✅ Actualiza base de datos correctamente
4. ✅ Retorna error descriptivo si vendedor no existe
5. ✅ Logs registran actualizaciones desde Odoo

---

**Fecha de entrega estimada**: Próxima sesión de desarrollo
**Prioridad**: Alta (Fase 1A) / Media (Fase 1B)
