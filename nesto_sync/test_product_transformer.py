#!/usr/bin/env python3
"""
Test del transformer ficticio_to_detailed_type

Prueba los 3 casos:
1. Ficticio=0 → product
2. Ficticio=1 + Grupo='CUR' → service
3. Ficticio=1 + Grupo!='CUR' → consu
"""

import sys
sys.path.insert(0, '/opt/odoo16/custom_addons/nesto_sync')

from transformers.field_transformers import FieldTransformerRegistry

def test_transformer():
    transformer = FieldTransformerRegistry.get('ficticio_to_detailed_type')

    # Test 1: Producto almacenable (Ficticio=0)
    context = {
        'nesto_data': {
            'Producto': '17404',
            'Nombre': 'ROLLO PAPEL CAMILLA',
            'Grupo': 'ACC',
            'Ficticio': 0
        }
    }
    result = transformer.transform(0, context)
    print(f"Test 1 - Ficticio=0, Grupo='ACC': {result}")
    assert result == {'detailed_type': 'product'}, f"Esperado 'product', obtenido {result}"

    # Test 2: Servicio (Ficticio=1, Grupo='CUR')
    context['nesto_data']['Grupo'] = 'CUR'
    context['nesto_data']['Ficticio'] = 1
    result = transformer.transform(1, context)
    print(f"Test 2 - Ficticio=1, Grupo='CUR': {result}")
    assert result == {'detailed_type': 'service'}, f"Esperado 'service', obtenido {result}"

    # Test 3: Consumible (Ficticio=1, Grupo!='CUR')
    context['nesto_data']['Grupo'] = 'ACC'
    result = transformer.transform(1, context)
    print(f"Test 3 - Ficticio=1, Grupo='ACC': {result}")
    assert result == {'detailed_type': 'consu'}, f"Esperado 'consu', obtenido {result}"

    # Test 4: None value (default a product)
    result = transformer.transform(None, context)
    print(f"Test 4 - Ficticio=None: {result}")
    assert result == {'detailed_type': 'product'}, f"Esperado 'product', obtenido {result}"

    print("\n✅ Todos los tests pasaron correctamente!")

if __name__ == '__main__':
    test_transformer()
