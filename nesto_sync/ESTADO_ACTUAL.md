# ESTADO ACTUAL - Nesto Sync

**Fecha**: 2025-11-07
**Versión**: 1.0
**Dirección**: Unidireccional (Nesto → Odoo)

## Resumen Ejecutivo

Módulo funcional que sincroniza clientes desde Nesto hacia Odoo mediante Google PubSub. La sincronización es unidireccional, robusta y con buena separación de responsabilidades.

## Arquitectura Actual

### Flujo de Datos
```
Google PubSub → Controller → Adapter → Processor → Service → Odoo DB
```

### Componentes Principales

#### 1. Controller ([controllers/controllers.py](controllers/controllers.py))
- **Responsabilidad**: Endpoint HTTP que recibe mensajes PubSub
- **Ruta**: `POST /nesto_sync`
- **Características**:
  - Autenticación pública (auth='public')
  - Sin CSRF (csrf=False)
  - Manejo de excepciones específicas (RequirePrincipalClientError)
  - Respuestas HTTP estándar (200, 400, 500)

#### 2. GooglePubSubMessageAdapter ([models/google_pubsub_message_adapter.py](models/google_pubsub_message_adapter.py))
- **Responsabilidad**: Decodificar mensajes de Google PubSub
- **Funcionalidad**:
  - Decodifica base64
  - Parsea JSON anidado
  - Validación básica de estructura

#### 3. ClientProcessor ([models/client_processor.py](models/client_processor.py))
- **Responsabilidad**: Transformar datos de Nesto a formato Odoo
- **Funcionalidades**:
  - Validación de campos obligatorios
  - Procesamiento de teléfonos (divide en mobile/phone/extras)
  - Gestión de direcciones (provincia, país)
  - Manejo de clientes principales vs. contactos de entrega
  - Procesamiento de personas de contacto secundarias
  - Asignación de cargos/funciones
  - Gestión del campo `active` basado en estado
- **Dependencias**:
  - CountryManager: Gestión de países y provincias
  - PhoneProcessor: Procesamiento de números de teléfono
  - ClientDataValidator: Validación de datos
  - cargos_funciones: Mapeo de cargos

#### 4. ClientService ([models/client_service.py](models/client_service.py))
- **Responsabilidad**: Operaciones CRUD en Odoo
- **Funcionalidades**:
  - Crear partners
  - Actualizar partners
  - Búsqueda por claves externas (cliente_externo, contacto_externo, persona_contacto_externa)
  - Gestión de relaciones parent/child
  - Commits/rollbacks de transacciones
  - Logging de operaciones
- **Características**:
  - Modo test (evita commits)
  - Búsquedas con `sudo()` para permisos completos
  - Búsquedas incluyen registros activos e inactivos

#### 5. ResPartner (Extension) ([models/res_partner.py](models/res_partner.py))
- **Responsabilidad**: Extender modelo res.partner de Odoo
- **Campos añadidos**:
  - `cliente_externo`: ID del cliente en Nesto
  - `contacto_externo`: ID del contacto en Nesto
  - `persona_contacto_externa`: ID de persona de contacto en Nesto
- **Validaciones**:
  - Constraint de unicidad en combinaciones de claves externas
  - Búsqueda personalizada por cliente_externo (numérico)
- **Funcionalidades**:
  - Búsqueda mejorada: permite buscar por cliente_externo cuando se busca por nombre con valor numérico

### Módulos de Soporte

#### PhoneProcessor ([models/phone_processor.py](models/phone_processor.py))
- Divide cadena de teléfonos en: mobile, phone, extras
- Prioriza móviles (prefijos españoles: 6, 7)

#### CountryManager ([models/country_manager.py](models/country_manager.py))
- Obtiene ID de España
- Crea/recupera provincias españolas

#### ClientDataValidator ([models/client_data_validator.py](models/client_data_validator.py))
- Valida campos obligatorios del mensaje

#### cargos_funciones ([models/cargos.py](models/cargos.py))
- Mapeo de códigos de cargo de Nesto a funciones de Odoo

## Estructura de Datos

### Mensaje Entrante (desde Nesto)
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

### Estructura Procesada (output de ClientProcessor)
```python
{
  'parent': {
    'cliente_externo': '12345',
    'contacto_externo': '1',
    'persona_contacto_externa': None,
    'name': 'Empresa S.L.',
    'street': 'Calle Principal 123',
    'phone': '912345678',
    'mobile': '666123456',
    'email': 'juan@empresa.com',  # Tomado del primer contacto
    'parent_id': None,  # O ID del parent si no es principal
    'company_id': 1,
    'vat': 'B12345678',
    'zip': '28001',
    'city': 'Madrid',
    'lang': 'es_ES',
    'comment': '[Teléfonos extra] ...\nCliente importante',
    'country_id': 233,  # ID de España
    'state_id': 45,  # ID de provincia
    'is_company': True,
    'type': 'invoice',  # o 'delivery' si no es principal
    'active': True
  },
  'children': [
    {
      'cliente_externo': '12345',
      'contacto_externo': '1',
      'persona_contacto_externa': '1',
      'name': 'Juan Pérez',
      'email': 'juan@empresa.com',
      'phone': None,
      'mobile': '666999888',
      'type': 'contact',
      'function': 'Director',
      'comment': 'Contacto principal',
      'company_id': 1,
      'lang': 'es_ES',
      'parent_id': None  # Se asigna en Service
    }
  ]
}
```

## Lógica de Negocio Importante

### Jerarquía de Clientes
1. **Cliente Principal** (`ClientePrincipal=true`):
   - `is_company=True`
   - `type='invoice'`
   - `parent_id=None`
   - Debe crearse PRIMERO

2. **Contacto de Entrega** (`ClientePrincipal=false`):
   - `is_company=False`
   - `type='delivery'`
   - `parent_id` = ID del cliente principal
   - Lanza `RequirePrincipalClientError` si no existe el principal

3. **Personas de Contacto**:
   - `type='contact'`
   - `parent_id` = ID del contacto de entrega o cliente principal
   - Tienen `persona_contacto_externa` != None

### Búsqueda de Duplicados
- **Cliente principal**: Búsqueda por `cliente_externo` y `parent_id=False`
- **Contacto de entrega**: Búsqueda por `cliente_externo`, `contacto_externo` y `persona_contacto_externa=None`
- **Persona de contacto**: Búsqueda por `cliente_externo`, `contacto_externo` y `persona_contacto_externa`

### Gestión de Estado
- Campo Nesto `Estado >= 0` → Odoo `active=True`
- Campo Nesto `Estado < 0` → Odoo `active=False`
- Las búsquedas incluyen ambos estados para permitir reactivación

## Testing

### Cobertura Actual
- Tests para GooglePubSubMessageAdapter
- Tests para ClientProcessor
- Tests para ClientService
- Tests para Controller
- Archivo común de utilidades ([tests/common.py](tests/common.py))

### Enfoque
- Tests unitarios por componente
- Mocking de dependencias Odoo
- Tests de integración del flujo completo

## Campos Sincronizados

### res.partner (Cliente Principal/Contacto)
- ✅ name (Nombre)
- ✅ street (Direccion)
- ✅ phone (Telefono - fijo)
- ✅ mobile (Telefono - móvil)
- ✅ email (de PersonasContacto)
- ✅ vat (Nif)
- ✅ zip (CodigoPostal)
- ✅ city (Poblacion)
- ✅ state_id (Provincia)
- ✅ country_id (España por defecto)
- ✅ comment (Comentarios + teléfonos extra)
- ✅ is_company (ClientePrincipal)
- ✅ type (invoice/delivery/contact)
- ✅ parent_id (relación jerárquica)
- ✅ company_id (empresa Odoo)
- ✅ lang (es_ES)
- ✅ active (basado en Estado)
- ✅ cliente_externo (ID Nesto)
- ✅ contacto_externo (ID Contacto Nesto)
- ✅ persona_contacto_externa (ID Persona Nesto)

### res.partner (Persona de Contacto)
- ✅ name (Nombre)
- ✅ email (CorreoElectronico)
- ✅ phone (Telefono - fijo)
- ✅ mobile (Telefono - móvil)
- ✅ function (Cargo mapeado)
- ✅ comment (Comentarios)
- ✅ type ('contact')
- ✅ parent_id (relación con cliente/contacto)
- ✅ cliente_externo
- ✅ contacto_externo
- ✅ persona_contacto_externa

## Limitaciones Actuales

### Funcionales
1. **Sincronización Unidireccional**: Solo Nesto → Odoo
2. **Una Sola Entidad**: Solo tabla de clientes (res.partner)
3. **Sin Detección de Cambios**: No compara si el valor realmente cambió
4. **Sin Historial**: No se guarda auditoría de cambios
5. **Mapeo Hardcodeado**: Campos mapeados en código, no configurables

### Técnicas
1. **Sin Retry**: Si falla, se pierde el mensaje
2. **Sin Rate Limiting**: Podría sobrecargarse con muchos mensajes simultáneos
3. **Commit por Mensaje**: No hay batching de operaciones
4. **Logging Básico**: Podría mejorarse para debugging

## Fortalezas

1. **Separación de Responsabilidades**: Arquitectura limpia y modular
2. **Testing**: Buena cobertura de tests
3. **Manejo de Errores**: Excepciones específicas y rollbacks
4. **Validaciones**: Constraints de BD para integridad de datos
5. **Flexible en Búsquedas**: Permite búsqueda por ID externo en interfaz Odoo
6. **Gestión de Estado**: Maneja clientes activos/inactivos correctamente

## Dependencias

### Odoo
- Versión: 16
- Módulo base: `base` (res.partner)

### Externas
- Google Cloud PubSub (protocolo de mensajería)
- Python 3 (estándar en Odoo 16)

## Próximos Pasos Recomendados

1. **Implementar sincronización bidireccional** (Odoo → Nesto)
2. **Sistema de detección de cambios** para evitar bucles infinitos
3. **Arquitectura extensible** para añadir más entidades fácilmente
4. **Sistema de configuración declarativa** de mapeos
5. **Mejoras en logging y auditoría**

---
**Última actualización**: 2025-11-07
**Revisado por**: Claude Code
