"""
Field Transformers - Sistema de transformación de campos

Los transformers convierten valores del formato de Nesto al formato de Odoo.
Cada transformer es una clase con un método transform().
"""

from ..models.phone_processor import PhoneProcessor
from ..models.country_manager import CountryManager


class FieldTransformerRegistry:
    """Registry central de transformers disponibles"""

    _transformers = {}

    @classmethod
    def register(cls, name):
        """Decorador para registrar un transformer"""
        def decorator(transformer_class):
            cls._transformers[name] = transformer_class
            return transformer_class
        return decorator

    @classmethod
    def get(cls, name):
        """Obtiene una instancia de un transformer por nombre"""
        transformer_class = cls._transformers.get(name)
        if not transformer_class:
            raise ValueError(f"Transformer no encontrado: {name}")
        return transformer_class()

    @classmethod
    def get_all(cls):
        """Devuelve todos los transformers registrados"""
        return cls._transformers.keys()


@FieldTransformerRegistry.register('phone')
class PhoneTransformer:
    """Transforma cadena de teléfonos en mobile, phone y extras"""

    def transform(self, value, context):
        """
        Procesa números de teléfono

        Args:
            value: String con teléfonos separados por /
            context: Dict con contexto de ejecución

        Returns:
            Dict con campos mobile, phone y opcionalmente _append_comment
        """
        mobile, phone, extra = PhoneProcessor.process_phone_numbers(value)

        result = {
            'mobile': mobile,
            'phone': phone
        }

        # Los teléfonos extra se añaden al comment
        if extra:
            result['_append_comment'] = f"[Teléfonos extra] {extra}"

        return result


@FieldTransformerRegistry.register('country_state')
class CountryStateTransformer:
    """Transforma nombre de provincia a state_id de Odoo"""

    def transform(self, value, context):
        """
        Obtiene o crea provincia

        Args:
            value: Nombre de la provincia
            context: Dict con country_manager

        Returns:
            Dict con state_id
        """
        if not value:
            return {'state_id': None}

        country_manager = context.get('country_manager')
        if not country_manager:
            raise ValueError("CountryManager no disponible en contexto")

        state_id = country_manager.get_or_create_state(value)
        return {'state_id': state_id}


@FieldTransformerRegistry.register('estado_to_active')
class EstadoToActiveTransformer:
    """Convierte campo Estado de Nesto a active de Odoo"""

    def transform(self, value, context):
        """
        Convierte Estado >= 0 a active=True

        Args:
            value: Valor del campo Estado (int)
            context: Dict con contexto

        Returns:
            Dict con campo active
        """
        return {'active': value >= 0 if value is not None else True}


@FieldTransformerRegistry.register('cliente_principal')
class ClientePrincipalTransformer:
    """Transforma ClientePrincipal en is_company y type"""

    def transform(self, value, context):
        """
        Determina is_company y type según ClientePrincipal

        Args:
            value: Boolean indicando si es cliente principal
            context: Dict con contexto

        Returns:
            Dict con is_company y type
        """
        return {
            'is_company': value,
            'type': 'invoice' if value else 'delivery'
        }


@FieldTransformerRegistry.register('spain_country')
class SpainCountryTransformer:
    """Devuelve el ID de España usando CountryManager"""

    def transform(self, value, context):
        """
        Obtiene el ID de España desde la BD

        Args:
            value: No se usa (puede ser None)
            context: Dict con country_manager

        Returns:
            Dict con country_id de España
        """
        country_manager = context.get('country_manager')
        if not country_manager:
            raise ValueError("CountryManager no disponible en contexto")

        spain_id = country_manager.get_spain_id()
        return {'country_id': spain_id}


@FieldTransformerRegistry.register('country_code')
class CountryCodeTransformer:
    """Transforma código de país a country_id de Odoo"""

    def transform(self, value, context):
        """
        Busca país por código

        Args:
            value: Código ISO del país (ej: 'ES')
            context: Dict con env

        Returns:
            Dict con country_id
        """
        if not value:
            return {'country_id': None}

        env = context.get('env')
        if not env:
            raise ValueError("Environment no disponible en contexto")

        country = env['res.country'].search([('code', '=', value)], limit=1)
        return {'country_id': country.id if country else None}


@FieldTransformerRegistry.register('cargos')
class CargosTransformer:
    """Transforma código de cargo de Nesto a función de Odoo"""

    def transform(self, value, context):
        """
        Mapea cargo de Nesto a función de Odoo

        Args:
            value: Código de cargo (int)
            context: Dict con cargos_funciones

        Returns:
            Dict con function
        """
        from ..models.cargos import cargos_funciones

        function = cargos_funciones.get(value, None)
        return {'function': function}


# Transformer para precios (ejemplo para futuras entidades)
@FieldTransformerRegistry.register('price')
class PriceTransformer:
    """Transforma precio a formato Odoo"""

    def transform(self, value, context):
        """
        Convierte precio a float

        Args:
            value: Precio (string, int o float)
            context: Dict con contexto

        Returns:
            Dict con precio formateado
        """
        try:
            price = float(value) if value else 0.0
        except (ValueError, TypeError):
            price = 0.0

        return {'list_price': price}


# Transformer para cantidades (ejemplo para futuras entidades)
@FieldTransformerRegistry.register('quantity')
class QuantityTransformer:
    """Transforma cantidad a formato Odoo"""

    def transform(self, value, context):
        """
        Convierte cantidad a float

        Args:
            value: Cantidad (string, int o float)
            context: Dict con contexto

        Returns:
            Dict con cantidad formateada
        """
        try:
            qty = float(value) if value else 0.0
        except (ValueError, TypeError):
            qty = 0.0

        return {'qty_available': qty}


@FieldTransformerRegistry.register('ficticio_to_detailed_type')
class FicticioToDetailedTypeTransformer:
    """
    Transforma los campos Ficticio y Grupo a detailed_type de Odoo

    Lógica:
    - Si Ficticio == 0 → 'product' (almacenable)
    - Si Ficticio == 1 y Grupo == "CUR" → 'service' (servicio)
    - Si Ficticio == 1 y Grupo != "CUR" → 'consu' (consumible)
    """

    def transform(self, value, context):
        """
        Determina el tipo de producto según Ficticio y Grupo

        Args:
            value: Valor del campo Ficticio (int o bool)
            context: Dict con 'nesto_data' que contiene el campo 'Grupo'

        Returns:
            Dict con detailed_type
        """
        # Obtener el valor de Ficticio (puede venir como int o bool)
        ficticio = bool(value) if value is not None else False

        # Si Ficticio es 0 (False), es producto almacenable
        if not ficticio:
            return {'detailed_type': 'product'}

        # Si Ficticio es 1 (True), depende del Grupo
        nesto_data = context.get('nesto_data', {})
        grupo = nesto_data.get('Grupo', '')

        # Si el grupo es CUR, es servicio; si no, es consumible
        if grupo == 'CUR':
            return {'detailed_type': 'service'}
        else:
            return {'detailed_type': 'consu'}


@FieldTransformerRegistry.register('product_category')
class ProductCategoryTransformer:
    """
    Transforma nombre de categoría a product.category
    Busca o crea la categoría bajo un padre específico
    """

    def transform(self, value, context):
        """
        Busca o crea una categoría de producto

        Args:
            value: Nombre de la categoría (ej: "Cosméticos", "Cremas", "Eva Visnú")
            context: Dict con:
                - env: Environment de Odoo
                - parent_category_name: Nombre de la categoría padre (opcional)
                - field_name: Nombre del campo para logs

        Returns:
            Dict con category_id
        """
        if not value:
            return {context.get('target_field', 'categ_id'): None}

        env = context.get('env')
        if not env:
            raise ValueError("Environment no disponible en contexto")

        # Obtener nombre de categoría padre si existe
        parent_name = context.get('parent_category_name')
        field_name = context.get('field_name', 'categoría')
        target_field = context.get('target_field', 'categ_id')

        # Buscar o crear categoría padre si se especificó
        parent_id = None
        if parent_name:
            parent = env['product.category'].sudo().search([('name', '=', parent_name)], limit=1)
            if not parent:
                parent = env['product.category'].sudo().create({
                    'name': parent_name,
                    'parent_id': None
                })
            parent_id = parent.id

        # Buscar categoría existente
        domain = [('name', '=', value)]
        if parent_id:
            domain.append(('parent_id', '=', parent_id))
        else:
            # Si no hay padre, buscar solo categorías de nivel raíz
            domain.append(('parent_id', '=', False))

        category = env['product.category'].sudo().search(domain, limit=1)

        # Crear si no existe
        if not category:
            category = env['product.category'].sudo().create({
                'name': value,
                'parent_id': parent_id
            })
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Categoría creada: {value} (parent: {parent_name or 'ninguno'}) - ID: {category.id}")

        return {target_field: category.id}


@FieldTransformerRegistry.register('grupo')
class GrupoTransformer:
    """
    Transformer específico para campo Grupo

    Los Grupos son categorías de nivel raíz (sin padre).
    Bajo cada Grupo se crean los Subgrupos como hijos.
    Ejemplo: ACC > Desechables, Cosméticos > Cremas Faciales
    """

    def transform(self, value, context):
        """
        Busca o crea categoría de Grupo a nivel raíz (sin padre)

        Args:
            value: Nombre del grupo (ej: "ACC", "Cosméticos", "Aparatos")
            context: Dict con contexto

        Returns:
            Dict con grupo_id
        """
        if not value:
            return {'grupo_id': None}

        context_with_config = {
            **context,
            'parent_category_name': None,  # Sin padre - nivel raíz
            'field_name': 'Grupo',
            'target_field': 'grupo_id'
        }

        transformer = ProductCategoryTransformer()
        return transformer.transform(value, context_with_config)


@FieldTransformerRegistry.register('subgrupo')
class SubgrupoTransformer:
    """
    Transformer específico para campo Subgrupo

    IMPORTANTE: El Subgrupo es dependiente del Grupo.
    Crea la categoría bajo el Grupo como padre, no bajo "Subgrupos".
    Ejemplo: ACC > Desechables, Cosméticos > Cremas Faciales
    """

    def transform(self, value, context):
        """
        Busca o crea categoría de Subgrupo bajo el Grupo correspondiente

        Args:
            value: Nombre del subgrupo (ej: "Desechables", "Cremas Faciales")
            context: Debe contener 'nesto_data' con el campo 'Grupo'

        Returns:
            Dict con subgrupo_id
        """
        if not value:
            return {'subgrupo_id': None}

        # Obtener el Grupo desde el mensaje de Nesto
        nesto_data = context.get('nesto_data', {})
        grupo_nombre = nesto_data.get('Grupo')

        if not grupo_nombre:
            # Si no hay Grupo, crear bajo "Subgrupos" genérico (fallback)
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Subgrupo '{value}' sin Grupo asociado. Usando padre genérico 'Subgrupos'.")
            parent_category_name = 'Subgrupos'
        else:
            # Usar el Grupo como padre del Subgrupo
            parent_category_name = grupo_nombre

        context_with_config = {
            **context,
            'parent_category_name': parent_category_name,
            'field_name': 'Subgrupo',
            'target_field': 'subgrupo_id'
        }

        transformer = ProductCategoryTransformer()
        return transformer.transform(value, context_with_config)


@FieldTransformerRegistry.register('familia')
class FamiliaTransformer:
    """Transformer específico para campo Familia (Marca)"""

    def transform(self, value, context):
        """Busca o crea categoría de Familia bajo 'Familias/Marcas'"""
        if not value:
            return {'familia_id': None}

        context_with_config = {
            **context,
            'parent_category_name': 'Familias/Marcas',
            'field_name': 'Familia',
            'target_field': 'familia_id'
        }

        transformer = ProductCategoryTransformer()
        return transformer.transform(value, context_with_config)


@FieldTransformerRegistry.register('url_to_image')
class UrlToImageTransformer:
    """
    Transforma URL de imagen a imagen en base64 para Odoo
    Descarga la imagen desde la URL y la convierte a base64

    OPTIMIZACIÓN: Solo descarga si la URL cambió respecto a url_imagen_actual
    """

    def transform(self, value, context):
        """
        Descarga imagen desde URL y la convierte a base64 (solo si cambió la URL)

        Args:
            value: URL de la imagen
            context: Dict con contexto (debe incluir 'existing_record' si existe)

        Returns:
            Dict con image_1920 en base64 y url_imagen_actual
        """
        import logging
        import requests
        import base64
        from io import BytesIO
        from PIL import Image

        _logger = logging.getLogger(__name__)

        if not value:
            return {'image_1920': None, 'url_imagen_actual': None}

        # Limpiar URL (a veces viene con espacios o caracteres raros)
        url = str(value).strip()

        # Si la URL es inválida o placeholder, retornar None
        if not url or url in ['0', 'N/A', 'null', '']:
            return {'image_1920': None, 'url_imagen_actual': None}

        # Validar que sea una URL válida
        if not url.startswith(('http://', 'https://')):
            _logger.warning(f"URL de imagen inválida (no HTTP/HTTPS): {url}")
            return {'image_1920': None, 'url_imagen_actual': None}

        # OPTIMIZACIÓN: Verificar si la URL cambió
        existing_record = context.get('existing_record')
        if existing_record and hasattr(existing_record, 'url_imagen_actual'):
            url_actual = existing_record.url_imagen_actual
            if url_actual == url:
                _logger.info(f"URL de imagen no cambió ({url}), no se descarga nuevamente")
                # No retornar nada para que no se sobrescriba la imagen
                return {}

        try:
            # Descargar imagen con timeout
            _logger.info(f"Descargando imagen desde: {url}")
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()

            # Verificar que sea una imagen
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                _logger.warning(f"URL no devuelve una imagen (Content-Type: {content_type}): {url}")
                return {'url_imagen_actual': url}  # Guardar URL pero no imagen

            # Leer la imagen y convertirla
            image_data = response.content

            # Validar que sea una imagen válida usando PIL
            try:
                img = Image.open(BytesIO(image_data))
                img.verify()  # Verificar integridad
            except Exception as e:
                _logger.warning(f"Imagen corrupta o formato inválido: {url} - Error: {e}")
                return {'url_imagen_actual': url}  # Guardar URL pero no imagen

            # Convertir a base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            _logger.info(f"Imagen descargada correctamente: {url} ({len(image_data)} bytes)")
            return {
                'image_1920': image_base64,
                'url_imagen_actual': url  # Guardar la URL para futuras comparaciones
            }

        except requests.exceptions.Timeout:
            _logger.warning(f"Timeout al descargar imagen: {url}")
            return {'url_imagen_actual': url}  # Guardar URL para reintentar después

        except requests.exceptions.HTTPError as e:
            _logger.warning(f"Error HTTP al descargar imagen ({e.response.status_code}): {url}")
            return {'url_imagen_actual': url}

        except requests.exceptions.RequestException as e:
            _logger.warning(f"Error al descargar imagen: {url} - Error: {e}")
            return {'url_imagen_actual': url}

        except Exception as e:
            _logger.error(f"Error inesperado al procesar imagen: {url} - Error: {e}")
            return {'url_imagen_actual': url}


@FieldTransformerRegistry.register('unidad_medida_y_tamanno')
class UnidadMedidaYTamannoTransformer:
    """
    Transformer que procesa UnidadMedida y Tamaño juntos

    Detecta el tipo de unidad (peso, volumen, longitud) y mapea Tamaño
    al campo correcto (weight, volume, product_length).

    También busca la unidad de medida en product.uom y la asigna a uom_id.
    """

    def transform(self, value, context):
        """
        Transforma UnidadMedida y Tamaño a campos de Odoo

        Args:
            value: Valor de Tamaño (puede ser None, se obtiene de context)
            context: Dict con 'env' y 'nesto_data'

        Returns:
            Dict con weight/volume/product_length, dimensional_uom_id, uom_id
        """
        from ..transformers.unidad_medida_transformer import transform_unidad_medida_y_tamanno

        env = context.get('env')
        nesto_data = context.get('nesto_data', {})

        if not env:
            raise ValueError("Environment no disponible en contexto")

        return transform_unidad_medida_y_tamanno(env, nesto_data)
