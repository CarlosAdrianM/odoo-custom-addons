class ClientDataValidator:
    @staticmethod
    def validate_required_fields(message):
        """ Valida que los campos obligatorios estén presentes. """
        if 'Cliente' not in message or not message['Cliente'].strip() or \
           'Contacto' not in message or not message['Contacto'].strip():
            raise ValueError("Faltan datos obligatorios: Cliente o Contacto")
