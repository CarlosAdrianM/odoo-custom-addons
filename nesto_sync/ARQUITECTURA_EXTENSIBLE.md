# Arquitectura Extensible - Propuesta de Diseño

**Fecha**: 2025-11-07
**Estado**: Propuesta para revisión

## Problema a Resolver

Actualmente, añadir una nueva entidad (Proveedores, Productos, etc.) requiere:
1. Crear un nuevo Processor específico con lógica hardcodeada
2. Crear un nuevo Service específico
3. Modificar el Controller para enrutar el nuevo tipo
4. Replicar lógica similar en cada componente

**Objetivo**: Añadir una nueva entidad debe ser tan simple como crear un archivo de configuración.

## Principios de Diseño

1. **Configuración sobre Código**: Los mapeos de campos se definen en configuración, no en código
2. **Separación de Responsabilidades**: Cada componente tiene una única responsabilidad clara
3. **Reutilización**: La lógica común se escribe una sola vez
4. **Extensibilidad**: Fácil añadir nuevas entidades sin modificar código existente
5. **Retrocompatibilidad**: El código actual debe seguir funcionando

## Arquitectura Propuesta

### 1. Sistema de Configuración de Entidades

Cada entidad se configura mediante un diccionario Python que define:

```python
# config/entity_configs.py

ENTITY_CONFIGS = {
    'cliente': {
        'odoo_model': 'res.partner',
        'message_type': 'cliente',  # Para identificar el tipo de mensaje
        'id_fields': ['cliente_externo', 'contacto_externo', 'persona_contacto_externa'],
        'field_mappings': {
            # Mapeos simples (directo)
            'Nombre': {'odoo_field': 'name', 'required': True, 'default': '<Sin nombre>'},
            'Direccion': {'odoo_field': 'street'},
            'Nif': {'odoo_field': 'vat'},
            'CodigoPostal': {'odoo_field': 'zip'},
            'Poblacion': {'odoo_field': 'city'},
            'Comentarios': {'odoo_field': 'comment'},

            # Mapeos con transformación
            'Telefono': {
                'transformer': 'phone_processor',  # Referencia a un transformer
                'odoo_fields': ['mobile', 'phone', 'comment']  # Múltiples campos destino
            },
            'Provincia': {
                'transformer': 'country_state_processor',
                'odoo_fields': ['state_id']
            },
            'Estado': {
                'transformer': 'estado_to_active',
                'odoo_fields': ['active']
            },

            # Campos calculados
            'ClientePrincipal': {
                'transformer': 'cliente_principal_processor',
                'odoo_fields': ['is_company', 'type']
            },

            # Campos fijos
            '_country': {
                'type': 'fixed',
                'odoo_field': 'country_id',
                'value': 'ES'  # Código de país
            },
            '_lang': {
                'type': 'fixed',
                'odoo_field': 'lang',
                'value': 'es_ES'
            },
            '_company': {
                'type': 'context',
                'odoo_field': 'company_id',
                'source': 'env.user.company_id.id'
            }
        },

        # Relaciones jerárquicas
        'hierarchy': {
            'enabled': True,
            'parent_field': 'parent_id',
            'parent_criteria': {'parent_id': False},  # Cómo identificar el parent
            'child_types': ['PersonasContacto']  # Sub-entidades
        },

        # Campos de identificación externa
        'external_id_mapping': {
            'cliente_externo': 'Cliente',
            'contacto_externo': 'Contacto',
            'persona_contacto_externa': 'PersonaContacto.Id'
        },

        # Validaciones personalizadas
        'validators': ['validate_cliente_principal_exists'],

        # Procesamiento especial
        'post_processors': ['assign_email_from_children']
    },

    # Configuración para Proveedores (ejemplo futuro)
    'proveedor': {
        'odoo_model': 'res.partner',
        'message_type': 'proveedor',
        'id_fields': ['proveedor_externo'],
        'field_mappings': {
            'Nombre': {'odoo_field': 'name', 'required': True},
            'Nif': {'odoo_field': 'vat'},
            # ... más campos
            '_is_supplier': {
                'type': 'fixed',
                'odoo_field': 'supplier_rank',
                'value': 1
            }
        },
        'hierarchy': {'enabled': False}
    },

    # Configuración para Productos (ejemplo futuro)
    'producto': {
        'odoo_model': 'product.product',
        'message_type': 'producto',
        'id_fields': ['producto_externo'],
        'field_mappings': {
            'Nombre': {'odoo_field': 'name', 'required': True},
            'Referencia': {'odoo_field': 'default_code'},
            'PrecioVenta': {
                'transformer': 'price_processor',
                'odoo_fields': ['list_price']
            },
            # ... más campos
        },
        'hierarchy': {'enabled': False}
    }
}
```

### 2. Sistema de Transformers

Los transformers son funciones reutilizables que transforman valores:

```python
# transformers/field_transformers.py

class FieldTransformerRegistry:
    """Registry de transformers disponibles"""

    _transformers = {}

    @classmethod
    def register(cls, name):
        def decorator(func):
            cls._transformers[name] = func
            return func
        return decorator

    @classmethod
    def get(cls, name):
        return cls._transformers.get(name)


@FieldTransformerRegistry.register('phone_processor')
def transform_phone(value, context):
    """Procesa teléfonos y devuelve dict con múltiples campos"""
    mobile, phone, extra = PhoneProcessor.process_phone_numbers(value)
    result = {
        'mobile': mobile,
        'phone': phone
    }
    # Extra phones van al comment (se combina después)
    if extra:
        result['_append_comment'] = f"[Teléfonos extra] {extra}"
    return result


@FieldTransformerRegistry.register('country_state_processor')
def transform_state(value, context):
    """Obtiene o crea provincia"""
    if not value:
        return {'state_id': None}
    country_manager = context.get('country_manager')
    state_id = country_manager.get_or_create_state(value)
    return {'state_id': state_id}


@FieldTransformerRegistry.register('estado_to_active')
def transform_estado(value, context):
    """Convierte Estado a active"""
    return {'active': value >= 0 if value is not None else True}


@FieldTransformerRegistry.register('cliente_principal_processor')
def transform_cliente_principal(value, context):
    """Determina is_company y type según ClientePrincipal"""
    return {
        'is_company': value,
        'type': 'invoice' if value else 'delivery'
    }


@FieldTransformerRegistry.register('price_processor')
def transform_price(value, context):
    """Procesa precios (ejemplo futuro)"""
    # Podría hacer conversión de moneda, redondeo, etc.
    return {'list_price': float(value) if value else 0.0}
```

### 3. Processor Genérico

Un único processor que usa la configuración:

```python
# models/generic_entity_processor.py

class GenericEntityProcessor:
    """Processor genérico basado en configuración"""

    def __init__(self, env, entity_config):
        self.env = env
        self.config = entity_config
        self.country_manager = CountryManager(env)

    def process(self, message):
        """Procesa un mensaje según la configuración de la entidad"""

        # 1. Validar campos requeridos
        self._validate_required_fields(message)

        # 2. Construir valores base
        values = self._build_values(message)

        # 3. Aplicar validadores personalizados
        self._run_validators(message, values)

        # 4. Procesar jerarquía si aplica
        if self.config.get('hierarchy', {}).get('enabled'):
            return self._process_hierarchy(message, values)

        return {'parent': values, 'children': []}

    def _build_values(self, message):
        """Construye dict de valores para Odoo"""
        values = {}
        context = {
            'env': self.env,
            'country_manager': self.country_manager,
            'message': message
        }

        for nesto_field, mapping in self.config['field_mappings'].items():
            # Campos fijos
            if mapping.get('type') == 'fixed':
                values[mapping['odoo_field']] = mapping['value']
                continue

            # Campos de contexto
            if mapping.get('type') == 'context':
                values[mapping['odoo_field']] = eval(mapping['source'], {'env': self.env})
                continue

            # Obtener valor del mensaje
            nesto_value = self._get_nested_value(message, nesto_field)

            # Aplicar default si es None y hay default
            if nesto_value is None and 'default' in mapping:
                nesto_value = mapping['default']

            # Mapeo simple
            if 'odoo_field' in mapping and 'transformer' not in mapping:
                values[mapping['odoo_field']] = nesto_value
                continue

            # Mapeo con transformer
            if 'transformer' in mapping:
                transformer = FieldTransformerRegistry.get(mapping['transformer'])
                if transformer:
                    transformed = transformer(nesto_value, context)
                    # Manejar campos especiales (_append_comment, etc.)
                    for key, val in transformed.items():
                        if key.startswith('_append_'):
                            target = key.replace('_append_', '')
                            values[target] = values.get(target, '') + '\n' + val
                        else:
                            values[key] = val

        # Añadir IDs externos
        for odoo_field, nesto_path in self.config['external_id_mapping'].items():
            values[odoo_field] = self._get_nested_value(message, nesto_path)

        return values

    def _get_nested_value(self, data, path):
        """Obtiene valor de un path anidado (ej: 'PersonaContacto.Id')"""
        if '.' not in path:
            return data.get(path)

        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _validate_required_fields(self, message):
        """Valida campos requeridos"""
        for nesto_field, mapping in self.config['field_mappings'].items():
            if mapping.get('required') and not message.get(nesto_field):
                raise ValueError(f"Campo requerido faltante: {nesto_field}")

    def _run_validators(self, message, values):
        """Ejecuta validadores personalizados"""
        # Aquí se llamarían validadores como validate_cliente_principal_exists
        pass

    def _process_hierarchy(self, message, parent_values):
        """Procesa jerarquías (parent/children)"""
        # Similar a la lógica actual de ClientProcessor
        # Pero genérica según config['hierarchy']
        pass
```

### 4. Service Genérico

```python
# models/generic_entity_service.py

class GenericEntityService:
    """Service genérico para cualquier entidad"""

    def __init__(self, env, entity_config, test_mode=False):
        self.env = env
        self.config = entity_config
        self.test_mode = test_mode
        self.model = env[entity_config['odoo_model']]

    def create_or_update(self, values):
        """Crea o actualiza entidad según configuración"""

        # Construir dominio de búsqueda basado en id_fields
        domain = self._build_search_domain(values)

        # Buscar registro existente
        record = self.model.sudo().search(domain, limit=1)

        if record:
            # Detectar cambios antes de actualizar
            if self._has_changes(record, values):
                return self._update(record, values)
            else:
                _logger.info(f"No hay cambios para {self.config['odoo_model']}: {domain}")
                return Response(
                    response=json.dumps({'message': 'Sin cambios'}),
                    status=200,
                    content_type='application/json'
                )
        else:
            return self._create(values)

    def _build_search_domain(self, values):
        """Construye dominio de búsqueda basado en id_fields"""
        domain = []
        for id_field in self.config['id_fields']:
            domain.append((id_field, '=', values.get(id_field)))

        # Añadir búsqueda en activos e inactivos
        domain.append('|')
        domain.append(('active', '=', True))
        domain.append(('active', '=', False))

        return domain

    def _has_changes(self, record, new_values):
        """Detecta si hay cambios reales (ANTI-BUCLE)"""
        for field, new_value in new_values.items():
            if field not in record._fields:
                continue

            current_value = getattr(record, field)

            # Comparar según tipo de campo
            if isinstance(current_value, models.BaseModel):
                # Campo relacional (many2one)
                current_value = current_value.id if current_value else None

            if current_value != new_value:
                _logger.info(f"Cambio detectado en {field}: {current_value} -> {new_value}")
                return True

        return False

    def _create(self, values):
        """Crea registro"""
        # Similar al actual ClientService._create_partner
        pass

    def _update(self, record, values):
        """Actualiza registro"""
        # Similar al actual ClientService._update_partner
        pass
```

### 5. Controller con Registry

```python
# controllers/controllers.py (refactorizado)

class NestoSyncController(http.Controller):

    def __init__(self):
        self.entity_registry = EntityRegistry()

    @http.route('/nesto_sync', auth='public', methods=['POST'], csrf=False)
    def sync_nesto(self, **post):
        try:
            # Decodificar mensaje
            adapter = GooglePubSubMessageAdapter()
            raw_data = request.httprequest.data
            message = adapter.decode_message(raw_data)

            # Determinar tipo de entidad
            entity_type = self._detect_entity_type(message)

            # Obtener procesador y servicio para esta entidad
            processor = self.entity_registry.get_processor(entity_type, request.env)
            service = self.entity_registry.get_service(entity_type, request.env)

            # Procesar y sincronizar
            values = processor.process(message)
            service.create_or_update(values)

            return Response(status=200, response="Sincronizado correctamente")

        except Exception as e:
            _logger.error(f"Error en sincronización: {str(e)}")
            return Response(status=400, response=str(e))

    def _detect_entity_type(self, message):
        """Detecta el tipo de entidad del mensaje"""
        # Opción 1: Campo explícito en el mensaje
        if 'entity_type' in message:
            return message['entity_type']

        # Opción 2: Por campos presentes
        if 'Cliente' in message:
            return 'cliente'
        elif 'Proveedor' in message:
            return 'proveedor'
        elif 'Producto' in message:
            return 'producto'

        raise ValueError("No se pudo determinar el tipo de entidad")
```

### 6. Entity Registry

```python
# core/entity_registry.py

class EntityRegistry:
    """Registry central de entidades configuradas"""

    def __init__(self):
        self.configs = ENTITY_CONFIGS

    def get_config(self, entity_type):
        """Obtiene configuración de una entidad"""
        if entity_type not in self.configs:
            raise ValueError(f"Entidad no configurada: {entity_type}")
        return self.configs[entity_type]

    def get_processor(self, entity_type, env):
        """Obtiene processor para una entidad"""
        config = self.get_config(entity_type)
        return GenericEntityProcessor(env, config)

    def get_service(self, entity_type, env, test_mode=False):
        """Obtiene service para una entidad"""
        config = self.get_config(entity_type)
        return GenericEntityService(env, config, test_mode)

    def register_entity(self, entity_type, config):
        """Registra una nueva entidad dinámicamente"""
        self.configs[entity_type] = config
```

## Estructura de Directorios Propuesta

```
nesto_sync/
├── __init__.py
├── __manifest__.py
├── config/
│   ├── __init__.py
│   └── entity_configs.py          # Configuraciones de entidades
├── core/
│   ├── __init__.py
│   ├── entity_registry.py         # Registry central
│   ├── generic_processor.py       # Processor genérico
│   └── generic_service.py         # Service genérico
├── transformers/
│   ├── __init__.py
│   ├── field_transformers.py      # Transformers de campos
│   └── validators.py              # Validadores personalizados
├── models/
│   ├── __init__.py
│   ├── res_partner.py             # Extensión de res.partner
│   ├── google_pubsub_message_adapter.py
│   ├── country_manager.py         # Helpers existentes
│   ├── phone_processor.py
│   └── change_detector.py         # Nuevo: detector de cambios
├── controllers/
│   ├── __init__.py
│   └── controllers.py             # Controller refactorizado
├── legacy/
│   ├── __init__.py
│   ├── client_processor.py        # Código actual (backup)
│   └── client_service.py
└── tests/
    ├── __init__.py
    ├── test_generic_processor.py
    ├── test_generic_service.py
    └── test_transformers.py
```

## Ventajas de Esta Arquitectura

1. **Añadir nueva entidad**: Solo crear entrada en `entity_configs.py`
2. **Reutilización**: Transformers compartidos entre entidades
3. **Mantenibilidad**: Configuración declarativa vs código disperso
4. **Testing**: Fácil testear transformers y configuraciones
5. **Detección de cambios**: Implementado en GenericService (anti-bucle)
6. **Extensibilidad**: Fácil añadir nuevos transformers

## Plan de Migración

### Fase 1: Crear Infraestructura
- [ ] Crear estructura de directorios
- [ ] Implementar EntityRegistry
- [ ] Implementar FieldTransformerRegistry
- [ ] Crear transformers básicos

### Fase 2: Implementar Core Genérico
- [ ] Implementar GenericEntityProcessor
- [ ] Implementar GenericEntityService con detección de cambios
- [ ] Crear configuración para 'cliente'

### Fase 3: Migrar Cliente a Nueva Arquitectura
- [ ] Mover lógica de ClientProcessor a transformers
- [ ] Configurar entity_config para 'cliente'
- [ ] Actualizar Controller para usar registry
- [ ] Mantener código viejo en /legacy

### Fase 4: Testing y Validación
- [ ] Tests unitarios de transformers
- [ ] Tests de GenericProcessor con config de cliente
- [ ] Tests de integración
- [ ] Validar que todo funciona igual que antes

### Fase 5: Sincronización Bidireccional
- [ ] Implementar publicador a PubSub
- [ ] Implementar hooks en Odoo (write/create)
- [ ] Verificar detección de cambios (anti-bucle)

### Fase 6: Expandir a Nuevas Entidades
- [ ] Configurar 'proveedor'
- [ ] Configurar 'producto'
- [ ] etc.

## Preguntas para Decidir

1. **Configuración en Python vs JSON/YAML**: ¿Prefieres la flexibilidad de Python o la simplicidad de JSON?
2. **Transformers como funciones vs clases**: ¿Te gusta el enfoque funcional o prefieres clases?
3. **Validadores personalizados**: ¿Cómo quieres manejar lógica de negocio compleja (ej: RequirePrincipalClientError)?
4. **Jerarquías**: ¿La lógica de parent/children es suficientemente genérica o necesita más personalización?
5. **Campos calculados**: ¿El sistema de post_processors es suficiente para cosas como "email del primer hijo"?

## Próximos Pasos

1. Revisar y aprobar esta propuesta
2. Ajustar según feedback
3. Comenzar implementación por fases
4. Mantener código actual funcionando en paralelo

---

**Nota**: Esta es una propuesta. Podemos ajustar cualquier parte antes de empezar a implementar.
