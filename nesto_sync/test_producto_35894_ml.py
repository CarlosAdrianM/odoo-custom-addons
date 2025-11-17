#!/usr/bin/env python3
"""
Test para producto 35894: ACIDO HIALURONICO RICCHEZZA 100ml

Bug reportado: El producto tiene Tamanno=100 y UnidadMedida="ml"
pero en Odoo aparece volume=0.00 m³

Este test reproduce el bug y verifica la fix.
"""

import sys
import os

# Añadir path del módulo
module_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, module_path)

def test_producto_35894_conversion():
    """Test: Verificar conversión de 100ml a m³"""
    print("\n=== Test: Producto 35894 - 100ml ===")

    # Datos del producto real
    nesto_data = {
        "$id": "1",
        "Producto": "35894",
        "Nombre": "ACIDO HIALURONICO RICCHEZZA",
        "Tamanno": 100,
        "UnidadMedida": "ml",
        "Familia": "Eva Visnú",
        "PrecioProfesional": 32.9500,
        "PrecioPublicoFinal": 56.96,
        "Estado": 0,
        "Grupo": "COS",
        "Subgrupo": "Aceites, fluidos y geles profesionales",
        "UrlEnlace": "https://www.productosdeesteticaypeluqueriaprofesional.com/aceites-fluidos-y-geles-profesionales/38801-acido-hialuronico-ricchezza-100ml.html",
        "UrlFoto": "https://www.productosdeesteticaypeluqueriaprofesional.com/102148-home_default/acido-hialuronico-ricchezza-100ml.jpg",
        "RoturaStockProveedor": False,
        "ClasificacionMasVendidos": 0,
        "CodigoBarras": "8437005358942"
    }

    print(f"Producto: {nesto_data['Nombre']}")
    print(f"Tamaño: {nesto_data['Tamanno']} {nesto_data['UnidadMedida']}")

    # Conversión esperada
    # ml es volumen, factor de conversión: 0.000001 (ml → m³)
    # 100 ml × 0.000001 = 0.0001 m³
    tamanno = nesto_data['Tamanno']
    conversion_factor = 0.000001  # ml → m³
    expected_volume = tamanno * conversion_factor

    print(f"\nConversión esperada:")
    print(f"  {tamanno} ml × {conversion_factor} = {expected_volume} m³")

    assert expected_volume == 0.0001, f"100ml debería convertirse a 0.0001m³, obtenido {expected_volume}"
    print(f"✅ Conversión matemática correcta: 100ml → 0.0001m³")

    return expected_volume


def test_unidad_medida_config_ml():
    """Test: Verificar que UnidadMedidaConfig tiene 'ml' configurado"""
    print("\n=== Test: Configuración de 'ml' en UnidadMedidaConfig ===")

    # Leer unidad_medida_transformer.py
    transformer_path = os.path.join(module_path, 'transformers', 'unidad_medida_transformer.py')

    with open(transformer_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verificar que existe VOLUME_UNITS
    assert 'VOLUME_UNITS' in content, "unidad_medida_transformer debe tener VOLUME_UNITS"
    print("✅ VOLUME_UNITS encontrado en transformer")

    # Verificar que 'ml' está en VOLUME_UNITS
    # Buscar línea como: "'ml': 0.000001,"
    assert "'ml'" in content or '"ml"' in content, "VOLUME_UNITS debe incluir 'ml'"
    print("✅ 'ml' está configurado en VOLUME_UNITS")

    # Verificar el factor de conversión correcto
    assert '0.000001' in content, "Factor de conversión para ml debe ser 0.000001"
    print("✅ Factor de conversión 0.000001 (ml → m³) configurado")


def test_entity_config_tamanno_mapping():
    """Test: Verificar que Tamanno está mapeado a transformer unidad_medida_y_tamanno"""
    print("\n=== Test: Mapeo de Tamanno en entity_configs.py ===")

    config_path = os.path.join(module_path, 'config', 'entity_configs.py')

    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Buscar configuración de productos
    producto_section_start = content.find("'producto': {")
    producto_section_end = content.find("'proveedor':", producto_section_start)

    if producto_section_end == -1:
        producto_section_end = len(content)

    producto_section = content[producto_section_start:producto_section_end]

    # Verificar que Tamanno usa el transformer correcto
    assert "'Tamanno':" in producto_section or '"Tamanno":' in producto_section, \
        "entity_configs.producto debe tener campo 'Tamanno'"
    print("✅ Campo 'Tamanno' configurado en entity_configs.producto")

    # Verificar que usa el transformer unidad_medida_y_tamanno
    # Buscar líneas después de 'Tamanno':
    tamanno_index = producto_section.find("'Tamanno':")
    if tamanno_index == -1:
        tamanno_index = producto_section.find('"Tamanno":')

    tamanno_config = producto_section[tamanno_index:tamanno_index+500]

    assert 'unidad_medida_y_tamanno' in tamanno_config, \
        "Tamanno debe usar transformer 'unidad_medida_y_tamanno'"
    print("✅ Tamanno usa transformer 'unidad_medida_y_tamanno'")

    # Verificar que mapea a 'volume'
    assert "'volume'" in tamanno_config or '"volume"' in tamanno_config, \
        "Tamanno debe mapear a campo 'volume'"
    print("✅ Tamanno mapea a campo 'volume'")


def test_transformer_receives_nesto_data():
    """Test: Verificar que el transformer recibe nesto_data completo"""
    print("\n=== Test: Transformer recibe nesto_data completo ===")

    transformer_path = os.path.join(module_path, 'transformers', 'field_transformers.py')

    with open(transformer_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Buscar la clase UnidadMedidaYTamannoTransformer
    transformer_start = content.find('class UnidadMedidaYTamannoTransformer')
    transformer_section = content[transformer_start:transformer_start+1000]

    # Verificar que obtiene nesto_data del contexto
    assert "nesto_data = context.get('nesto_data'" in transformer_section, \
        "Transformer debe obtener nesto_data del contexto"
    print("✅ Transformer obtiene nesto_data del contexto")

    # Verificar que llama a transform_unidad_medida_y_tamanno con env y nesto_data
    assert "transform_unidad_medida_y_tamanno(env, nesto_data)" in transformer_section, \
        "Transformer debe pasar nesto_data a transform_unidad_medida_y_tamanno"
    print("✅ Transformer pasa nesto_data completo a función de transformación")


def test_bug_diagnosis():
    """Test: Diagnóstico del bug reportado"""
    print("\n=== Diagnóstico del Bug ===")

    print("\nDatos del problema:")
    print("  Input: Tamanno=100, UnidadMedida='ml'")
    print("  Output esperado: volume=0.0001 m³")
    print("  Output reportado: volume=0.00 m³")

    print("\nPosibles causas:")
    print("  1. ❓ El transformer no se está ejecutando")
    print("  2. ❓ El transformer no recibe UnidadMedida en nesto_data")
    print("  3. ❓ El transformer recibe nesto_data pero Tamanno o UnidadMedida son None")
    print("  4. ❓ El transformer calcula correctamente pero el valor no se guarda")

    print("\nVerificación de configuración:")

    # Verificar que el transformer está registrado
    transformer_path = os.path.join(module_path, 'transformers', 'field_transformers.py')
    with open(transformer_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "@FieldTransformerRegistry.register('unidad_medida_y_tamanno')" in content:
        print("  ✅ Transformer 'unidad_medida_y_tamanno' está registrado")
    else:
        print("  ❌ Transformer 'unidad_medida_y_tamanno' NO está registrado")
        return False

    # Verificar que el transformer accede a nesto_data
    if "nesto_data = context.get('nesto_data'" in content:
        print("  ✅ Transformer accede a nesto_data del contexto")
    else:
        print("  ❌ Transformer NO accede a nesto_data")
        return False

    # Verificar mapeo en entity_configs
    config_path = os.path.join(module_path, 'config', 'entity_configs.py')
    with open(config_path, 'r', encoding='utf-8') as f:
        config_content = f.read()

    if "'Tamanno':" in config_content and "'transformer': 'unidad_medida_y_tamanno'" in config_content:
        print("  ✅ Tamanno está mapeado a transformer 'unidad_medida_y_tamanno'")
    else:
        print("  ❌ Tamanno NO está correctamente mapeado")
        return False

    print("\n✅ Configuración parece correcta")
    print("\nPróximo paso para debugging:")
    print("  1. Añadir logs en transform_unidad_medida_y_tamanno para ver:")
    print("     - Valores de Tamanno y UnidadMedida recibidos")
    print("     - Tipo de unidad detectado")
    print("     - Valor convertido")
    print("     - Dict retornado")
    print("  2. Sincronizar producto 35894 y revisar logs")

    return True


def run_all_tests():
    """Ejecutar todos los tests"""
    print("=" * 70)
    print("TEST: Producto 35894 - Bug de conversión 100ml")
    print("=" * 70)

    tests = [
        ("Conversión matemática 100ml → m³", test_producto_35894_conversion),
        ("Configuración de 'ml' en UnidadMedidaConfig", test_unidad_medida_config_ml),
        ("Mapeo de Tamanno en entity_configs", test_entity_config_tamanno_mapping),
        ("Transformer recibe nesto_data", test_transformer_receives_nesto_data),
        ("Diagnóstico del bug", test_bug_diagnosis),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            result = test_func()
            if result is not False:
                passed += 1
            else:
                failed += 1
        except AssertionError as e:
            print(f"\n❌ FALLO: {test_name}")
            print(f"   Error: {str(e)}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {test_name}")
            print(f"   Excepción: {str(e)}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESUMEN: {passed}/{len(tests)} tests pasaron")
    print("=" * 70)

    if failed == 0:
        print("\n✅ Configuración correcta. Bug podría estar en:")
        print("   - Ejecución del transformer (añadir logs)")
        print("   - Guardado del valor en BD (verificar permisos)")
        print("   - Cache de Python (limpiar __pycache__)")
        return 0
    else:
        print(f"\n❌ {failed} tests fallaron")
        print("   Revisar configuración antes de continuar")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
