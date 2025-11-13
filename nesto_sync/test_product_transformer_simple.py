#!/usr/bin/env python3
"""
Test simple del transformer ficticio_to_detailed_type (sin imports de Odoo)
"""

def ficticio_to_detailed_type(value, context):
    """Copia de la lógica del transformer"""
    ficticio = bool(value) if value is not None else False

    if not ficticio:
        return {'detailed_type': 'product'}

    nesto_data = context.get('nesto_data', {})
    grupo = nesto_data.get('Grupo', '')

    if grupo == 'CUR':
        return {'detailed_type': 'service'}
    else:
        return {'detailed_type': 'consu'}

def test_transformer():
    print("Testing ficticio_to_detailed_type transformer\n")

    # Test 1: Producto almacenable (Ficticio=0)
    context = {
        'nesto_data': {
            'Producto': '17404',
            'Nombre': 'ROLLO PAPEL CAMILLA',
            'Grupo': 'ACC',
            'Ficticio': 0
        }
    }
    result = ficticio_to_detailed_type(0, context)
    print(f"✓ Test 1 - Ficticio=0, Grupo='ACC': {result}")
    assert result == {'detailed_type': 'product'}

    # Test 2: Servicio (Ficticio=1, Grupo='CUR')
    context['nesto_data']['Grupo'] = 'CUR'
    context['nesto_data']['Ficticio'] = 1
    result = ficticio_to_detailed_type(1, context)
    print(f"✓ Test 2 - Ficticio=1, Grupo='CUR': {result}")
    assert result == {'detailed_type': 'service'}

    # Test 3: Consumible (Ficticio=1, Grupo='ACC')
    context['nesto_data']['Grupo'] = 'ACC'
    result = ficticio_to_detailed_type(1, context)
    print(f"✓ Test 3 - Ficticio=1, Grupo='ACC': {result}")
    assert result == {'detailed_type': 'consu'}

    # Test 4: None value (default a product)
    result = ficticio_to_detailed_type(None, context)
    print(f"✓ Test 4 - Ficticio=None: {result}")
    assert result == {'detailed_type': 'product'}

    # Test 5: Consumible con otro grupo
    context['nesto_data']['Grupo'] = 'OTRO'
    result = ficticio_to_detailed_type(1, context)
    print(f"✓ Test 5 - Ficticio=1, Grupo='OTRO': {result}")
    assert result == {'detailed_type': 'consu'}

    print("\n✅ Todos los tests pasaron correctamente!")

if __name__ == '__main__':
    test_transformer()
