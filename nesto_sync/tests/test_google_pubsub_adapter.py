# nesto_sync/tests/test_google_pubsub_message_adapter.py
import json
import base64
from odoo.tests import common, tagged
from ..models.google_pubsub_message_adapter import GooglePubSubMessageAdapter
import unittest

@tagged('post_install', '-at_install', 'nesto_sync')
class TestGooglePubSubMessageAdapter(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.adapter = GooglePubSubMessageAdapter()

    def test_decode_message_success(self):
        """Debe decodificar correctamente un mensaje válido en base64."""
        payload = {"key": "value"}
        encoded_data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

        raw_message = json.dumps({
            "message": {"data": encoded_data}
        })

        decoded_message = self.adapter.decode_message(raw_message)
        self.assertEqual(decoded_message, payload)

    def test_decode_message_no_data(self):
        """Debe lanzar ValueError si falta el campo 'data' en el mensaje."""
        raw_message = json.dumps({"message": {}})
        
        with self.assertRaises(ValueError) as context:
            self.adapter.decode_message(raw_message)

        self.assertEqual(str(context.exception), "No se encontró el campo 'data'")

    def test_decode_message_bytes_input(self):
        """Debe aceptar una entrada en bytes y decodificar correctamente."""
        payload = {"key": "value"}
        encoded_data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

        raw_message = json.dumps({
            "message": {"data": encoded_data}
        }).encode("utf-8")  # Simula la entrada en bytes

        decoded_message = self.adapter.decode_message(raw_message)
        self.assertEqual(decoded_message, payload)