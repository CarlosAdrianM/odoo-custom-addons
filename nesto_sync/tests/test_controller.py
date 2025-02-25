from odoo.tests import TransactionCase, tagged
from odoo import http, models
from unittest.mock import patch
import json
import base64

@tagged('post_install', '-at_install', 'nesto_sync')
class NestoSyncController(http.Controller, models.Model):
    _name = 'nesto_sync.controller'
    _description = 'Nesto Sync Controller'

    def setUp(self):
        super().setUp()
        self.controller = self.env['nesto_sync.controller'].browse()

    def _mock_request(self, data):
        class MockRequest:
            def __init__(self, data):
                self.httprequest = self
                self.data = data.encode('utf-8') if isinstance(data, str) else data
                self.env = self.env

            def get_data(self):
                return self.data

        return MockRequest(data)

    @patch('odoo.http.request')
    def test_invalid_message_handling(self, mock_request):
        """Prueba con un mensaje inválido"""
        mock_request.httprequest = self._mock_request("Invalid data")
        mock_request.env = self.env

        controller = self.env['nesto_sync.controller'].browse()
        response = controller.sync_nesto_client()

        self.assertEqual(response.status_code, 400)

    @patch('odoo.http.request')
    def test_successful_sync(self, mock_request):
        """Prueba con un mensaje válido"""
        valid_data = {
            "message": {
                "data": base64.b64encode(
                    json.dumps({"key": "value"}).encode("utf-8")
                ).decode('utf-8')
            }
        }

        mock_request.httprequest = self._mock_request(json.dumps(valid_data))
        mock_request.env = self.env

        controller = self.env['nesto_sync.controller'].browse()
        response = controller.sync_nesto_client()

        self.assertEqual(response.status_code, 200)