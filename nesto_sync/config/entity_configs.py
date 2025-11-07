"""
Entity Configurations - Configuración declarativa de entidades sincronizables

Este archivo define cómo se mapean las entidades de Nesto a Odoo.
Para añadir una nueva entidad, simplemente añade una entrada a ENTITY_CONFIGS.
"""

ENTITY_CONFIGS = {
    # ==========================================
    # CLIENTES
    # ==========================================
    'cliente': {
        # Modelo de Odoo donde se guardan los datos
        'odoo_model': 'res.partner',

        # Tipo de mensaje (para logs y detección)
        'message_type': 'cliente',

        # Campos que identifican unívocamente un registro
        # Se usan para buscar si el registro ya existe
        'id_fields': ['cliente_externo', 'contacto_externo', 'persona_contacto_externa'],

        # Mapeo de campos: Nesto -> Odoo
        'field_mappings': {
            # --- Campos simples (mapeo directo) ---
            'Nombre': {
                'odoo_field': 'name',
                'required': True,
                'default': '<Nombre cliente no proporcionado>'
            },
            'Direccion': {
                'odoo_field': 'street'
            },
            'Nif': {
                'odoo_field': 'vat'
            },
            'CodigoPostal': {
                'odoo_field': 'zip'
            },
            'Poblacion': {
                'odoo_field': 'city'
            },
            'Comentarios': {
                'odoo_field': 'comment'
            },

            # --- Campos con transformación ---
            'Telefono': {
                'transformer': 'phone',
                'odoo_fields': ['mobile', 'phone', 'comment']  # El comment se añade vía _append_comment
            },
            'Provincia': {
                'transformer': 'country_state',
                'odoo_fields': ['state_id']
            },
            'Estado': {
                'transformer': 'estado_to_active',
                'odoo_fields': ['active']
            },
            'ClientePrincipal': {
                'transformer': 'cliente_principal',
                'odoo_fields': ['is_company', 'type']
            },

            # --- Campos fijos ---
            '_country': {
                'type': 'fixed',
                'odoo_field': 'country_id',
                'value': 233  # ID de España (podría obtenerse dinámicamente)
            },
            # Note: es_ES language must be installed in Odoo for this to work
            # Commented out for compatibility with test environments
            # '_lang': {
            #     'type': 'fixed',
            #     'odoo_field': 'lang',
            #     'value': 'es_ES'
            # },

            # --- Campos de contexto (evaluados) ---
            '_company': {
                'type': 'context',
                'odoo_field': 'company_id',
                'source': 'env.user.company_id.id'
            },
        },

        # Mapeo de campos para children (PersonasContacto)
        'child_field_mappings': {
            'Nombre': {
                'odoo_field': 'name',
                'required': True,
                'default': '<Nombre no proporcionado>'
            },
            'CorreoElectronico': {
                'odoo_field': 'email'
            },
            'Telefono': {
                'transformer': 'phone',
                'odoo_fields': ['mobile', 'phone']
            },
            'Cargo': {
                'transformer': 'cargos',
                'odoo_fields': ['function']
            },
            'Comentarios': {
                'odoo_field': 'comment'
            },

            # Campos fijos para children
            '_type': {
                'type': 'fixed',
                'odoo_field': 'type',
                'value': 'contact'
            },
            # Note: es_ES language must be installed in Odoo for this to work
            # Commented out for compatibility with test environments
            # '_lang': {
            #     'type': 'fixed',
            #     'odoo_field': 'lang',
            #     'value': 'es_ES'
            # },
            '_company': {
                'type': 'context',
                'odoo_field': 'company_id',
                'source': 'env.user.company_id.id'
            },
        },

        # Configuración de jerarquía (parent/children)
        'hierarchy': {
            'enabled': True,
            'parent_field': 'parent_id',
            'child_types': ['PersonasContacto'],  # Nombres de campos en mensaje que contienen children
        },

        # Mapeo de IDs externos (Nesto -> Odoo)
        'external_id_mapping': {
            'cliente_externo': 'Cliente',
            'contacto_externo': 'Contacto',
            'persona_contacto_externa': 'Id',  # Para children, se busca en child_data
        },

        # Post-processors: Se ejecutan después de procesar todos los campos
        # Útil para lógica que depende de múltiples campos
        'post_processors': [
            'assign_email_from_children',  # Asigna email del primer child al parent
            'merge_comments',  # Combina _append_comment en comment final
        ],

        # Validadores: Se ejecutan antes de crear/actualizar
        # Útil para validar lógica de negocio compleja
        'validators': [
            'validate_cliente_principal_exists',  # Valida que existe el cliente principal
        ],
    },

    # ==========================================
    # PROVEEDORES (Ejemplo para futuro)
    # ==========================================
    # 'proveedor': {
    #     'odoo_model': 'res.partner',
    #     'message_type': 'proveedor',
    #     'id_fields': ['proveedor_externo'],
    #     'field_mappings': {
    #         'Nombre': {'odoo_field': 'name', 'required': True},
    #         'Nif': {'odoo_field': 'vat'},
    #         'Direccion': {'odoo_field': 'street'},
    #         'Telefono': {'transformer': 'phone', 'odoo_fields': ['mobile', 'phone']},
    #         # Campo fijo para marcar como proveedor
    #         '_supplier_rank': {'type': 'fixed', 'odoo_field': 'supplier_rank', 'value': 1},
    #         '_lang': {'type': 'fixed', 'odoo_field': 'lang', 'value': 'es_ES'},
    #         '_company': {'type': 'context', 'odoo_field': 'company_id', 'source': 'env.user.company_id.id'},
    #     },
    #     'external_id_mapping': {
    #         'proveedor_externo': 'Proveedor',
    #     },
    #     'hierarchy': {'enabled': False},
    #     'post_processors': [],
    #     'validators': [],
    # },

    # ==========================================
    # PRODUCTOS (Ejemplo para futuro)
    # ==========================================
    # 'producto': {
    #     'odoo_model': 'product.product',
    #     'message_type': 'producto',
    #     'id_fields': ['producto_externo'],
    #     'field_mappings': {
    #         'Nombre': {'odoo_field': 'name', 'required': True},
    #         'Referencia': {'odoo_field': 'default_code'},
    #         'DescripcionVenta': {'odoo_field': 'description_sale'},
    #         'PrecioVenta': {'transformer': 'price', 'odoo_fields': ['list_price']},
    #         'Activo': {'transformer': 'estado_to_active', 'odoo_fields': ['active']},
    #         '_type': {'type': 'fixed', 'odoo_field': 'type', 'value': 'product'},
    #         '_company': {'type': 'context', 'odoo_field': 'company_id', 'source': 'env.user.company_id.id'},
    #     },
    #     'external_id_mapping': {
    #         'producto_externo': 'Producto',
    #     },
    #     'hierarchy': {'enabled': False},
    #     'post_processors': [],
    #     'validators': [],
    # },
}


def get_entity_config(entity_type):
    """
    Helper para obtener configuración de una entidad

    Args:
        entity_type: Tipo de entidad

    Returns:
        Dict con configuración

    Raises:
        ValueError: Si la entidad no existe
    """
    if entity_type not in ENTITY_CONFIGS:
        raise ValueError(f"Entidad no configurada: {entity_type}")
    return ENTITY_CONFIGS[entity_type]


def get_available_entities():
    """
    Devuelve lista de entidades configuradas

    Returns:
        List con nombres de entidades
    """
    return list(ENTITY_CONFIGS.keys())
