import json
from .country_manager import CountryManager
from .phone_processor import PhoneProcessor
from .client_data_validator import ClientDataValidator
from .cargos import cargos_funciones

class ClientProcessor:
    def __init__(self, env):
        self.env = env
        self.country_manager = CountryManager(env)

    def process_client(self, message):    
        # Si message es un string, lo convertimos a diccionario
        if isinstance(message, str):
            message = json.loads(message)
        
        # Validar campos obligatorios
        ClientDataValidator.validate_required_fields(message)
    
        # Extraer datos del mensaje
        cliente_externo = message.get('Cliente')
        contacto_externo = message.get('Contacto')
        cliente_principal = message.get('ClientePrincipal', False)
        nombre = message.get('Nombre') or "<Nombre cliente no proporcionado>"
        direccion = message.get('Direccion')
        telefono = message.get('Telefono')
        nif = message.get('Nif')
        codigo_postal = message.get('CodigoPostal')
        poblacion = message.get('Poblacion')
        provincia = message.get('Provincia')
        comentarios = message.get('Comentarios')
        active = message.get('Estado', 0) >= 0


        # Procesar números de teléfono
        mobile, phone, extra_phones = PhoneProcessor.process_phone_numbers(telefono)

        # Obtener el ID de España y estado/provincia si aplica
        spain_id = self.country_manager.get_spain_id()
        state_id = self.country_manager.get_or_create_state(provincia) if provincia else None

        # Construir comentarios adicionales
        comment_parts = []
        if extra_phones:
            comment_parts.append(f"[Teléfonos extra] {extra_phones}")
        if comentarios:
            comment_parts.append(comentarios)
        comment = "\n".join(comment_parts) if comment_parts else None

        # Inicializar el objeto parent (cliente principal o individual)
        parent = {
            'cliente_externo': cliente_externo,
            'contacto_externo': contacto_externo,
            'persona_contacto_externa': None,
            'name': nombre,
            'street': direccion,
            'phone': phone,
            'mobile': mobile,
            'parent_id': None,  # Siempre None para el cliente principal
            'company_id': self.env.user.company_id.id,
            'vat': nif,
            'zip': codigo_postal,
            'city': poblacion,
            'lang': 'es_ES',
            'comment': comment,
            'country_id': spain_id,
            'state_id': state_id,
            'is_company': cliente_principal,
            'type': 'invoice' if cliente_principal else 'delivery',
            'active': active
        }

        # Si el cliente no es principal, buscar el parent
        if not cliente_principal:
            parent_partner = self.env['res.partner'].sudo().search([
                ('cliente_externo', '=', cliente_externo),
                ('parent_id', '=', False)
            ], limit=1)
            if not parent_partner:
                raise RequirePrincipalClientError(
                    f"Es necesario crear primero el cliente principal para el cliente {cliente_externo}"
                )
            parent['parent_id'] = parent_partner.id

        # Procesar contactos secundarios
        children = []
        
        for persona in message.get('PersonasContacto', []):
            mobile, phone, extra_phones = PhoneProcessor.process_phone_numbers(persona.get('Telefono'))
            child = {
                'cliente_externo': cliente_externo,
                'contacto_externo': contacto_externo,
                'persona_contacto_externa': persona['Id'],
                'email': persona.get('CorreoElectronico'),
                'name': persona.get('Nombre') or "<Nombre no proporcionado>",
                'phone': phone,
                'mobile': mobile,
                'type': 'contact',
                'function': cargos_funciones.get(persona.get('Cargo'), None),
                'comment': persona.get('Comentarios'),
                'company_id': self.env.user.company_id.id,
                'lang': 'es_ES',
                'parent_id': None,  # Se asigna después
            }
            children.append(child)

        # Seleccionar el primer email disponible de los children
        parent['email'] = next((c['email'] for c in children if c.get('email')), None)

        return {
            'parent': parent,
            'children': children
        }


class RequirePrincipalClientError(Exception):
    """Excepción personalizada para indicar que se requiere crear primero el cliente principal."""
    pass
