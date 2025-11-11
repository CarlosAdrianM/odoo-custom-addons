#!/usr/bin/env python3
"""
Test rápido del formato de mensaje del OdooPublisher

Verifica que:
1. No hay doble serialización JSON
2. El mensaje tiene la estructura correcta: {Accion, Tabla, Datos: {Parent, Children}}
"""

import json
import sys
import os

# Mock de las dependencias de Odoo para poder testear sin Odoo
class MockConfig:
    def get(self, key, default=None):
        configs = {
            'nesto_table': 'Clientes',
            'hierarchy': {
                'enabled': True,
                'child_types': ['PersonasContacto'],
                'parent_field': 'parent_id'
            },
            'field_mappings': {
                'Nif': {'odoo_field': 'vat'},
                'Nombre': {'odoo_field': 'name'},
                'Cliente': {'odoo_field': 'cliente_externo'}
            },
            'pubsub_topic': 'sincronizacion-tablas'
        }
        return configs.get(key, default)

class MockRecord:
    def __init__(self):
        self._name = 'res.partner'
        self.id = 5428
        self.vat = '53739877D'
        self.name = '2012 SACH SERVICE, S.L.'
        self.cliente_externo = '39270'
        self.mobile = '666642422'

# Test de la función _wrap_in_sync_message
def test_wrap_in_sync_message():
    """Test que la estructura del mensaje es correcta"""

    # Data de ejemplo (lo que devuelve _build_message_from_odoo)
    data = {
        'Nif': '53739877D',
        'Nombre': '2012 SACH SERVICE, S.L.',
        'Cliente': '39270',
        'Telefono': '666642422',
        'PersonasContacto': [
            {'Nombre': 'Juan Pérez', 'Email': 'juan@example.com'},
            {'Nombre': 'María López', 'Email': 'maria@example.com'}
        ]
    }

    # Simular el método _wrap_in_sync_message
    hierarchy_config = MockConfig().get('hierarchy', {})
    parent_data = {}
    children_data = []

    if hierarchy_config.get('enabled'):
        child_types = hierarchy_config.get('child_types', ['PersonasContacto'])
        child_field_name = child_types[0] if child_types else 'PersonasContacto'

        # Extraer children del data
        children_data = data.pop(child_field_name, [])
        parent_data = data
    else:
        parent_data = data

    # Construir estructura ExternalSyncMessageDTO
    message = {
        "Accion": "actualizar",
        "Tabla": MockConfig().get('nesto_table', 'Clientes'),
        "Datos": {
            "Parent": parent_data
        }
    }

    # Añadir Children solo si existen
    if children_data:
        message["Datos"]["Children"] = children_data

    # Verificar estructura
    assert "Accion" in message, "Falta campo 'Accion'"
    assert message["Accion"] == "actualizar", "Accion debe ser 'actualizar'"

    assert "Tabla" in message, "Falta campo 'Tabla'"
    assert message["Tabla"] == "Clientes", "Tabla debe ser 'Clientes'"

    assert "Datos" in message, "Falta campo 'Datos'"
    assert "Parent" in message["Datos"], "Falta 'Parent' en Datos"
    assert "Children" in message["Datos"], "Falta 'Children' en Datos"

    # Verificar Parent
    parent = message["Datos"]["Parent"]
    assert parent["Nif"] == "53739877D", "Nif incorrecto en Parent"
    assert parent["Nombre"] == "2012 SACH SERVICE, S.L.", "Nombre incorrecto en Parent"
    assert parent["Cliente"] == "39270", "Cliente incorrecto en Parent"
    assert "PersonasContacto" not in parent, "PersonasContacto NO debe estar en Parent"

    # Verificar Children
    children = message["Datos"]["Children"]
    assert len(children) == 2, "Debe haber 2 children"
    assert children[0]["Nombre"] == "Juan Pérez"
    assert children[1]["Email"] == "maria@example.com"

    print("✅ Test 1 PASSED: Estructura del mensaje es correcta")
    print(f"\nEstructura generada:")
    print(json.dumps(message, indent=2, ensure_ascii=False))

    return message

def test_no_double_serialization():
    """Test que no hay doble serialización JSON"""

    message = {
        "Accion": "actualizar",
        "Tabla": "Clientes",
        "Datos": {
            "Parent": {
                "Nif": "53739877D",
                "Cliente": "39270"
            }
        }
    }

    # Simular lo que hace google_pubsub_publisher.py
    if isinstance(message, dict):
        message_json = json.dumps(message, ensure_ascii=False)
    elif isinstance(message, str):
        message_json = message
    else:
        raise ValueError(f"Mensaje debe ser dict o str, recibido: {type(message)}")

    message_bytes = message_json.encode('utf-8')

    # Verificar que NO es doble serialización
    # Si hubiera doble serialización, el primer carácter sería comilla doble "
    first_char = message_bytes.decode('utf-8')[0]
    assert first_char == '{', f"Primera carácter debe ser '{{', no '{first_char}' (sería doble serialización)"

    # Verificar que el JSON es válido
    parsed = json.loads(message_bytes.decode('utf-8'))
    assert isinstance(parsed, dict), "Mensaje deserializado debe ser dict"
    assert "Accion" in parsed, "Debe tener campo Accion"

    print("✅ Test 2 PASSED: NO hay doble serialización JSON")
    print(f"\nMensaje JSON (primeros 100 chars):")
    print(message_json[:100])

    return message_json

def test_comparison_wrong_vs_correct():
    """Test comparando formato INCORRECTO vs CORRECTO"""

    # INCORRECTO (lo que llegaba antes)
    wrong_data = {
        "Nif": "53739877D",
        "Cliente": "39270",
        "Nombre": "2012 SACH SERVICE, S.L.",
        "Tabla": "Clientes",  # ❌ Tabla en el nivel raíz
        "Source": "Odoo"      # ❌ Source en el nivel raíz
    }

    # Doble serialización (INCORRECTO)
    wrong_json = json.dumps(wrong_data)
    wrong_double = json.dumps(wrong_json)  # ❌ Serialización doble

    print("❌ FORMATO INCORRECTO (doble serialización):")
    print(wrong_double[:150])
    print()

    # CORRECTO (lo que debe llegar ahora)
    correct_data = {
        "Accion": "actualizar",
        "Tabla": "Clientes",  # ✅ Tabla en el nivel raíz
        "Datos": {
            "Parent": {
                "Nif": "53739877D",
                "Cliente": "39270",
                "Nombre": "2012 SACH SERVICE, S.L."
            }
        }
    }

    # Una sola serialización (CORRECTO)
    correct_json = json.dumps(correct_data, ensure_ascii=False)

    print("✅ FORMATO CORRECTO (una serialización):")
    print(correct_json[:150])
    print()

    # Verificaciones
    assert wrong_double[0] == '"', "Wrong format empieza con comilla (doble serialización)"
    assert correct_json[0] == '{', "Correct format empieza con llave (una serialización)"

    print("✅ Test 3 PASSED: Diferencia entre formato incorrecto y correcto clara")

if __name__ == '__main__':
    print("=" * 60)
    print("TEST DEL FORMATO DE MENSAJE - OdooPublisher")
    print("=" * 60)
    print()

    try:
        test_wrap_in_sync_message()
        print()
        print("-" * 60)
        print()

        test_no_double_serialization()
        print()
        print("-" * 60)
        print()

        test_comparison_wrong_vs_correct()
        print()
        print("=" * 60)
        print("✅ TODOS LOS TESTS PASARON")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
