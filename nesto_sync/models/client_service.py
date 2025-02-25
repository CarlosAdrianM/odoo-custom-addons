from odoo.http import Response
import json
import logging

_logger = logging.getLogger(__name__)

class ClientService:
    def __init__(self, env, test_mode=False):
        self.env = env
        self.test_mode = test_mode

    def _create_partner(self, values):
        try:
            partner = self.env['res.partner'].sudo().create(values)
            if partner:
                _logger.info(f"Cliente creado: {partner.id}")
                if not self.test_mode:
                    self.env.cr.commit()
                return Response(
                    response=json.dumps({'message': 'Cliente creado'}),
                    status=200,
                    content_type='application/json'
                )
            else:
                _logger.error("Error al crear el cliente")
                self.env.cr.rollback()
                return Response(
                    response=json.dumps({"error": "Error al crear el cliente"}),
                    status=500,
                    content_type='application/json'
                )
        except Exception as e:
            _logger.error(f"Error al crear partner: {str(e)}")
            self.env.cr.rollback()
            return Response(
                response=json.dumps({"error": str(e)}),
                status=500,
                content_type='application/json'
            )

    def _update_partner(self, partner, values):
        try:
            partner.sudo().write(values)
            _logger.info(f"Cliente actualizado: {partner.id}")
            if not self.test_mode:
                self.env.cr.commit()
            return Response(
                response=json.dumps({'message': 'Cliente actualizado'}),
                status=200,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error al actualizar partner: {str(e)}")
            self.env.cr.rollback()
            return Response(
                response=json.dumps({"error": str(e)}),
                status=500,
                content_type='application/json'
            )

    def _create_or_update_contact(self, client_data):
        """Crea o actualiza un cliente principal y sus contactos secundarios."""
        parent_values = client_data.get('parent')
        child_values_list = client_data.get('children', [])

        # Crear o actualizar el cliente principal
        self._create_or_update_single_contact(parent_values)

        # Crear o actualizar los contactos secundarios
        for child_values in child_values_list:
            self._create_or_update_single_contact(child_values)

    def _create_or_update_single_contact(self, values):
        """Crea o actualiza un solo contacto según los valores proporcionados."""
        parent_partner = None

        if values.get('persona_contacto_externa') is not None:
            parent_partner = self.env['res.partner'].sudo().search([
                ('cliente_externo', '=', values.get('cliente_externo')),
                ('contacto_externo', '=', values.get('contacto_externo')),
                ('persona_contacto_externa', '=', None)
            ], limit=1)
        else:
            parent_partner = self.env['res.partner'].sudo().search([
                ('cliente_externo', '=', values.get('cliente_externo')),
                ('parent_id', '=', False)
            ], limit=1)

        partner = self.env['res.partner'].sudo().search([
            ('cliente_externo', '=', values.get('cliente_externo')),
            ('contacto_externo', '=', values.get('contacto_externo')),
            ('persona_contacto_externa', '=', values.get('persona_contacto_externa'))
        ], limit=1)

        if parent_partner and partner.id != parent_partner.id:
            values['parent_id'] = parent_partner.id

        if partner:
            return self._update_partner(partner, values)
        return self._create_partner(values)

