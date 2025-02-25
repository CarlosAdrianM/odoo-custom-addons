# nesto_sync/models/google_pubsub_message_adapter.py
import json
import base64
from odoo import models

class GooglePubSubMessageAdapter:
    def decode_message(self, raw_data):
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode('utf-8')
        
        message_data = json.loads(raw_data)
        pubsub_message = message_data.get('message', {})
        data = pubsub_message.get('data')
        
        if not data:
            raise ValueError("No se encontró el campo 'data'")
            
        decoded_data = base64.b64decode(data).decode('utf-8')
        return json.loads(decoded_data)