import unicodedata

class CountryManager:
    def __init__(self, env):
        self.env = env

    def get_spain_id(self):
        """ Devuelve el ID de España. """
        spain = self.env['res.country'].search([('code', '=', 'ES')], limit=1)
        if not spain:
            raise ValueError("El país España no está configurado en la base de datos")
        return spain.id

    def get_or_create_state(self, state_name):
        """ Busca o crea una provincia según su nombre. """
        if not state_name:
            raise ValueError("El nombre de la provincia no puede estar vacío")

        spain_id = self.get_spain_id()
        
        # Quitamos las tildes para que CORDOBA y CÓRDOBA sean iguales
        normalized_state_name = self.remove_accents(state_name)
        all_states = self.env['res.country.state'].search([])

        # Filtrar manualmente los estados que coincidan
        matching_state = next((state for state in all_states if self.remove_accents(state.name).lower() == normalized_state_name.lower()), None)


        if not matching_state:
            return None
        
        return matching_state.id

        

    def remove_accents(self, text):
        if not text:
            return ""
        return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
