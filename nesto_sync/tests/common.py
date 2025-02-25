# nesto_sync/tests/common.py
from odoo.tests import TransactionCase
import json
import base64

class NestoSyncCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_data = {
            "Cliente": "TEST001",
            "Contacto": "CONTACT001",
            "ClientePrincipal": True,
            "Nombre": "Test Cliente",
            "Direccion": "Calle Test 123",
            "Telefono": "666777888 / 912345678 / 699888777"
        }

    def _create_test_pubsub_message(self, data):
        json_str = json.dumps(data)
        base64_data = base64.b64encode(json_str.encode()).decode()
        return {
            "message": {
                "data": base64_data
            }
        }