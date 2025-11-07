# Prompt para NestoAPI - Sincronización Bidireccional

**Fecha de generación**: 2025-11-07
**Proyecto origen**: nesto_sync (Odoo 16)
**Proyecto destino**: NestoAPI (C# WebApi 2)
**Repositorio NestoAPI**: https://github.com/CarlosAdrianM/NestoAPI

---

## Contexto del Proyecto

Estoy trabajando en un sistema de sincronización bidireccional entre Odoo 16 y Nesto mediante Google Cloud PubSub. Actualmente, la sincronización funciona **unidireccionalmente** (Nesto → Odoo) para la tabla de clientes.

## Estado Actual en Odoo (nesto_sync)

### Arquitectura Implementada
```
Google PubSub → Controller → Adapter → Processor → Service → Odoo DB
```

### Componentes Principales
1. **Controller**: Endpoint HTTP `/nesto_sync` que recibe mensajes PubSub
2. **GooglePubSubMessageAdapter**: Decodifica mensajes base64 de PubSub
3. **ClientProcessor**: Transforma datos de Nesto a formato Odoo
4. **ClientService**: Realiza operaciones CRUD en res.partner de Odoo

### Flujo Actual (Nesto → Odoo)
1. Nesto publica cambio en cliente a Google PubSub
2. PubSub envía POST a endpoint `/nesto_sync` de Odoo
3. Odoo decodifica mensaje, procesa y actualiza/crea el cliente
4. Retorna HTTP 200 si todo OK

### Estructura del Mensaje Actual (JSON)
```json
{
  "Cliente": "12345",
  "Contacto": "1",
  "ClientePrincipal": true,
  "Nombre": "Empresa S.L.",
  "Direccion": "Calle Principal 123",
  "Telefono": "666123456;912345678",
  "Nif": "B12345678",
  "CodigoPostal": "28001",
  "Poblacion": "Madrid",
  "Provincia": "Madrid",
  "Comentarios": "Cliente importante",
  "Estado": 1,
  "PersonasContacto": [
    {
      "Id": "1",
      "Nombre": "Juan Pérez",
      "Telefono": "666999888",
      "CorreoElectronico": "juan@empresa.com",
      "Cargo": "DIR",
      "Comentarios": "Contacto principal"
    }
  ]
}
```

### Claves de Identificación
- **cliente_externo**: ID del cliente en Nesto (string)
- **contacto_externo**: ID del contacto en Nesto (string)
- **persona_contacto_externa**: ID de persona de contacto en Nesto (string o null)

Estas tres claves identifican unívocamente un registro en Odoo.

## Objetivo: Sincronización Bidireccional

Necesito implementar el flujo **Odoo → Nesto**:
1. Usuario modifica cliente en Odoo
2. Odoo publica cambio a Google PubSub
3. PubSub envía mensaje a endpoint de NestoAPI
4. NestoAPI procesa y actualiza base de datos de Nesto

## Reto Principal: Evitar Bucle Infinito

### Problema
```
Odoo actualiza → PubSub → Nesto actualiza → PubSub → Odoo actualiza → ...
```

### Solución Propuesta
**Detección de cambios reales antes de actualizar**:
- Cuando llega un mensaje de sincronización, comparar campo por campo con el valor actual en BD
- Si TODOS los campos son iguales → NO ACTUALIZAR → Fin del bucle
- Si ALGÚN campo cambió → ACTUALIZAR → Publicar a PubSub

Esta lógica debe implementarse tanto en Odoo como en NestoAPI.

## Tareas para NestoAPI

### 1. Endpoint de Recepción (Nesto ← Odoo)
Crear un endpoint HTTP (ej: `POST /api/sync/clientes`) que:
- Reciba mensajes de Google PubSub con el formato de Odoo
- Decodifique el mensaje (base64, JSON anidado)
- Valide campos obligatorios

### 2. Comparador de Cambios
Crear una clase/servicio que:
- Compare el mensaje entrante con el registro actual en BD de Nesto
- Retorne `true` si hay cambios reales, `false` si todo es igual
- Considere campos relevantes (ignorar timestamps internos, etc.)

### 3. Actualizador de BD
Si hay cambios reales:
- Actualizar registro en BD de Nesto
- **NO publicar a PubSub** (el mensaje ya vino de PubSub, evitamos bucle)

### 4. Publisher para Cambios Locales
Cuando un cambio se origina en Nesto (no desde PubSub):
- Publicar mensaje a Google PubSub con los datos del cliente
- Usar el formato JSON especificado arriba
- Incluir todas las claves de identificación

### 5. Mapeo de Campos
Definir el mapeo entre:
- Campos de Odoo (res.partner) ↔ Campos de BD Nesto

Campos principales a sincronizar:
- Nombre
- Dirección (calle, CP, población, provincia)
- Teléfonos (móvil, fijo)
- Email
- NIF/CIF
- Estado (activo/inactivo)
- Jerarquía (cliente principal vs contacto de entrega)
- Personas de contacto asociadas

### 6. Testing
- Tests unitarios del comparador de cambios
- Tests del endpoint de recepción
- Test de integración simulando el flujo completo

## Arquitectura Recomendada para Extensibilidad

Como vamos a añadir más entidades en el futuro (Proveedores, Productos, Seguimientos), te recomiendo:

1. **Separar responsabilidades**:
   - Adapter: decodificar PubSub
   - Processor: transformar datos
   - Comparator: detectar cambios
   - Service: CRUD en BD
   - Publisher: publicar a PubSub

2. **Configuración declarativa**:
   - Definir mapeo de campos en configuración/diccionario
   - Factory/registry de procesadores por tipo de entidad

3. **Reutilización de código**:
   - Lógica de comparación genérica (no específica de clientes)
   - Publisher genérico que acepte cualquier mensaje

## Estructura del Mensaje desde Odoo

Odoo enviará mensajes PubSub con esta estructura (similar a la actual):
```json
{
  "message": {
    "data": "<base64_encoded_json>",
    "messageId": "...",
    "publishTime": "..."
  }
}
```

Donde `data` decodificado contiene el JSON con los datos del cliente.

## Consideraciones Importantes

1. **Identificación de origen**: Considera añadir un campo `origen` al mensaje para saber si vino de Odoo o Nesto (opcional, pero útil para debugging)

2. **Versionado**: Si cambias la estructura del mensaje, considera añadir un campo `version` para compatibilidad futura

3. **Idempotencia**: Las operaciones deben ser idempotentes (recibir el mismo mensaje varias veces no debe causar problemas)

4. **Manejo de errores**: Si falla una actualización, considera estrategia de retry o DLQ (Dead Letter Queue)

5. **Logging**: Log exhaustivo para debugging (qué llegó, qué cambió, qué se actualizó)

## Preguntas para Considerar

1. ¿Qué campos de la tabla Clientes de Nesto deben sincronizarse?
2. ¿Hay campos calculados o derivados que NO deban sincronizarse?
3. ¿Cómo se gestionan las personas de contacto en Nesto? ¿Tabla separada?
4. ¿Cómo se representa la jerarquía cliente principal/contacto entrega en Nesto?
5. ¿Hay campos en Nesto que no existen en Odoo y viceversa? ¿Cómo se manejan?

## Próximos Pasos Coordinados

1. Implementar endpoint de recepción en NestoAPI
2. Implementar comparador de cambios en NestoAPI
3. En paralelo, implementar publicación desde Odoo
4. Testing de integración con ambos sistemas publicando
5. Verificar que se evitan bucles infinitos
6. Expandir a otras entidades (Proveedores, Productos, etc.)

## Información Adicional

- **Odoo version**: 16
- **Python**: 3.x
- **Google Cloud PubSub**: Protocolo de mensajería
- **Autenticación PubSub**: Configurada en Google Cloud (webhook push a endpoint público)

---

## Resumen Ejecutivo

**Necesito que implementes en NestoAPI**:
1. Endpoint que reciba actualizaciones de clientes desde Odoo vía PubSub
2. Sistema de comparación de cambios para evitar bucles infinitos
3. Actualizador de BD que solo actualice si hay cambios reales
4. Publisher que publique a PubSub cuando el cambio se origina en Nesto
5. Todo diseñado de forma extensible para añadir más entidades fácilmente

**Objetivo**: Sincronización bidireccional robusta, sin bucles infinitos, extensible a múltiples entidades.

---

**Generado para**: NestoAPI (C# WebApi 2)
**Contexto origen**: nesto_sync (Odoo 16)
**Fecha**: 2025-11-07
