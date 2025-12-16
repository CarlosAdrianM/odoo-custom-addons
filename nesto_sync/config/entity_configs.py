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

            # --- Campo PersonaContacto (cuando viene en la raíz del mensaje) ---
            # Nesto envía mensajes planos donde PersonaContacto está directamente en la raíz
            # Este campo determina junto con Cliente y Contacto el registro único
            'PersonaContacto': {
                'odoo_field': 'persona_contacto_externa'
            },

            # --- Vendedor (auto-mapeo por email) ---
            # Nesto envía Vendedor (código) + VendedorEmail (email del vendedor)
            # El transformer busca usuario en Odoo por email y asigna user_id
            # Si no viene Vendedor en el mensaje, no se hace nada (comportamiento conservador)
            'Vendedor': {
                'transformer': 'vendedor',
                'odoo_fields': ['user_id', 'vendedor_externo']
            },

            # --- Campos fijos ---
            '_country': {
                'transformer': 'spain_country',
                'odoo_fields': ['country_id']
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
            'Telefonos': {
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
            '_country': {
                'transformer': 'spain_country',
                'odoo_fields': ['country_id']
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

        # ==========================================
        # SINCRONIZACIÓN BIDIRECCIONAL
        # ==========================================

        # Activar sincronización bidireccional (Odoo → Nesto)
        'bidirectional': True,

        # Topic de PubSub donde publicar
        'pubsub_topic': 'sincronizacion-tablas',

        # Tabla en Nesto
        'nesto_table': 'Clientes',

        # Mapeo inverso: Odoo → Nesto
        # IMPORTANTE: Los campos se mapean con nombres en ESPAÑOL (como en field_mappings)
        # Solo especificamos los identificadores críticos aquí
        # El resto se infieren automáticamente desde field_mappings
        'reverse_field_mappings': {
            # ⚠️ IDENTIFICADORES CRÍTICOS - DEBEN IR SIEMPRE
            'cliente_externo': {'nesto_field': 'Cliente'},
            'contacto_externo': {'nesto_field': 'Contacto'},
            # Vendedor: sincroniza código hacia Nesto
            'vendedor_externo': {'nesto_field': 'Vendedor'},
            # Los demás campos (Nombre, Direccion, etc.) se infieren automáticamente
            # y mantienen sus nombres en español
        },

        # Mapeo inverso para children (PersonasContacto)
        'reverse_child_field_mappings': {
            # ⚠️ IDENTIFICADOR CRÍTICO
            'persona_contacto_externa': {'nesto_field': 'Id'},
            # Los demás campos (Nombre, CorreoElectronico, etc.) se infieren automáticamente
            # y mantienen sus nombres en español
        },
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
    # PRODUCTOS
    # ==========================================
    'producto': {
        # Modelo de Odoo donde se guardan los datos
        'odoo_model': 'product.template',

        # Tipo de mensaje (para logs y detección)
        'message_type': 'producto',

        # Campos que identifican unívocamente un registro
        'id_fields': ['producto_externo'],

        # Mapeo de campos: Nesto -> Odoo
        'field_mappings': {
            # --- Campos simples (mapeo directo) ---
            'Producto': {
                'odoo_field': 'default_code',
                'required': False,
                'help': 'Referencia interna del producto'
            },
            'Nombre': {
                'odoo_field': 'name',
                'required': True,
                'default': '<Nombre producto no proporcionado>'
            },
            'PrecioProfesional': {
                'odoo_field': 'list_price',
                'required': False,
                'default': 0.0
            },
            # Tamaño y UnidadMedida se procesan juntos con un transformer especial
            # El transformer detecta el tipo (peso/volumen/longitud) y mapea al campo correcto
            # dimensional_uom_id se omite porque es un campo related que maneja product_dimension
            'Tamanno': {
                'transformer': 'unidad_medida_y_tamanno',
                'odoo_fields': ['weight', 'volume', 'product_length', 'uom_id', 'uom_po_id']
            },
            'CodigoBarras': {
                'odoo_field': 'barcode',
                'required': False
            },

            # --- Campos con transformación ---
            'Estado': {
                'transformer': 'estado_to_active',
                'odoo_fields': ['active']
            },
            'Ficticio': {
                'transformer': 'ficticio_to_detailed_type',
                'odoo_fields': ['detailed_type']
            },
            'Grupo': {
                'transformer': 'grupo',
                'odoo_fields': ['grupo_id', 'sale_ok']
            },
            'Subgrupo': {
                'transformer': 'subgrupo',
                'odoo_fields': ['subgrupo_id']
            },
            'Familia': {
                'transformer': 'familia',
                'odoo_fields': ['familia_id']
            },

            # UrlFoto: Descargar imagen del producto
            # Optimizado: Solo descarga si cambió la URL (comparando con url_imagen_actual)
            'UrlFoto': {
                'transformer': 'url_to_image',
                'odoo_fields': ['image_1920', 'url_imagen_actual']
            },

            # UnidadMedida necesitará un transformer para mapear a uom_id
            # Por ahora lo dejamos comentado para la fase 2
            # 'UnidadMedida': {
            #     'transformer': 'unidad_medida',
            #     'odoo_fields': ['uom_id', 'uom_po_id']
            # },

            # --- Campos fijos ---
            '_company': {
                'type': 'context',
                'odoo_field': 'company_id',
                'source': 'env.user.company_id.id'
            },
        },

        # Mapeo de IDs externos (Nesto -> Odoo)
        'external_id_mapping': {
            'producto_externo': 'Producto',
        },

        # Sin jerarquía por ahora
        'hierarchy': {
            'enabled': False
        },

        # Post-processors
        'post_processors': [
            'sync_product_bom',  # Sincronizar BOM desde ProductosKit
        ],

        # Validadores
        'validators': [],

        # ==========================================
        # SINCRONIZACIÓN BIDIRECCIONAL
        # ==========================================

        # Activar sincronización bidireccional (Odoo → Nesto)
        'bidirectional': True,

        # Topic de PubSub donde publicar
        'pubsub_topic': 'sincronizacion-tablas',

        # Tabla en Nesto
        'nesto_table': 'Productos',

        # Mapeo inverso: Odoo → Nesto
        'reverse_field_mappings': {
            # ⚠️ IDENTIFICADOR CRÍTICO
            'producto_externo': {'nesto_field': 'Producto'},
            # Los demás campos se infieren automáticamente
        },
    },
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
