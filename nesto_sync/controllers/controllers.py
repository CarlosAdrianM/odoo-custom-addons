from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response
from ..models.google_pubsub_message_adapter import GooglePubSubMessageAdapter
from ..models.client_service import ClientService
from ..models.client_processor import ClientProcessor, RequirePrincipalClientError

class NestoSyncController(http.Controller):
    
    @http.route('/nesto_sync', auth='public', methods=['POST'], csrf=False)
    def sync_nesto_client(self, **post):
        try:
            adapter = GooglePubSubMessageAdapter()
            processor = ClientProcessor(request.env)
            service = ClientService(request.env)

            # Decodificar mensaje
            raw_data = request.httprequest.data
            message = adapter.decode_message(raw_data)

            # Procesar cliente y obtener valores
            values = processor.process_client(message)

            # Crear o actualizar contacto principal
            service._create_or_update_contact(values)

            return Response(status=200, response="Clientes sincronizados correctamente")

        except RequirePrincipalClientError as e:
            return Response(status=200, response=str(e))
        except ValueError as e:
            return Response(status=500, response=str(e))
        except Exception as e:
            return Response(status=400, response=str(e))