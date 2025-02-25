from odoo.tests import tagged
import unittest

@tagged('post_install', '-at_install', 'nesto_sync')
class TestMessageParser:
    """Test unitarios para el parsing de mensajes"""
    
    def setUp(self):
        self.raw_message = {
            "Cliente": "TEST001",
            "Contacto": "CONTACT001",
            "ClientePrincipal": True,
            "Nombre": "Test Cliente",
            "Direccion": "Calle Test 123",
            "Telefono": "666777888 / 912345678 / 699888777"
        }

    def test_parse_phones(self):
        """Test el parsing de teléfonos funciona correctamente"""
        phones = "666777888 / 912345678 / 699888777"
        mobile, phone, extra = self._parse_phones(phones)
        
        self.assertEqual(mobile, "666777888")
        self.assertEqual(phone, "912345678")
        self.assertEqual(extra, "699888777")

    def test_parse_empty_phones(self):
        """Test manejo de teléfonos vacíos"""
        phones = ""
        mobile, phone, extra = self._parse_phones(phones)
        
        self.assertFalse(mobile)
        self.assertFalse(phone)
        self.assertFalse(extra)
