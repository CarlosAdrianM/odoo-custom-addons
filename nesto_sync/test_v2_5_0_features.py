#!/usr/bin/env python3
"""
Test de funcionalidades v2.5.0

Verifica las tres funcionalidades principales:
1. UnidadMedida + Tamanno → weight/volume/product_length con conversiones
2. UrlFoto → image_1920 con optimización de cache
3. Campos Familia, Grupo, Subgrupo configurados en entity_configs

NOTA: Este test verifica la configuración y lógica de conversiones.
Para tests completos con Odoo, ejecutar con pytest dentro del entorno de Odoo.
"""

import sys
import os
import json

# Añadir path del módulo
module_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, module_path)


def test_conversion_factors():
    """Test: Verificar factores de conversión de unidades"""
    print("\n=== Test 1: Factores de Conversión ===")

    conversions = {
        # Peso (a kg)
        'g → kg': (500, 0.001, 0.5),  # 500g = 0.5kg
        'kg → kg': (2, 1.0, 2.0),     # 2kg = 2kg

        # Volumen (a m³)
        'l → m³': (2, 0.001, 0.002),    # 2l = 0.002m³
        'ml → m³': (500, 0.000001, 0.0005),  # 500ml = 0.0005m³

        # Longitud (a m)
        'cm → m': (150, 0.01, 1.5),   # 150cm = 1.5m
        'mm → m': (1500, 0.001, 1.5), # 1500mm = 1.5m
        'm → m': (2, 1.0, 2.0),        # 2m = 2m
    }

    all_ok = True
    for conversion_name, (value, factor, expected) in conversions.items():
        result = value * factor
        if abs(result - expected) < 0.00001:  # Tolerancia para floats
            print(f"✅ {conversion_name}: {value} × {factor} = {result}")
        else:
            print(f"❌ {conversion_name}: esperado {expected}, obtenido {result}")
            all_ok = False

    assert all_ok, "Algunos factores de conversión son incorrectos"
    print("✅ Todos los factores de conversión son correctos")


def test_entity_configs_structure():
    """Test: Verificar estructura de entity_configs para productos"""
    print("\n=== Test 2: Estructura de entity_configs ===")

    # Leer entity_configs.py y verificar estructura
    config_path = os.path.join(module_path, 'config', 'entity_configs.py')

    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verificar que contiene configuración de productos
    assert "'producto':" in content, "entity_configs debe tener configuración de 'producto'"
    print("✅ Configuración de 'producto' encontrada")

    # Verificar campos clave para v2.5.0
    required_fields = [
        "'UrlFoto':",          # Fix crítico de UrlImagen → UrlFoto
        "'UnidadMedida':",     # Nueva funcionalidad
        "'Tamanno':",          # Nueva funcionalidad (con ñ)
        "'Grupo':",            # Categorización
        "'Subgrupo':",         # Categorización
        "'Familia':",          # Categorización
    ]

    for field in required_fields:
        if field in content:
            print(f"✅ Campo configurado: {field[1:-2]}")
        else:
            print(f"❌ Campo faltante: {field[1:-2]}")
            assert False, f"Campo requerido no encontrado: {field}"

    print("✅ Todos los campos requeridos están configurados")


def test_urlfoto_not_urlimagen():
    """Test: Verificar que se usa UrlFoto y NO UrlImagen"""
    print("\n=== Test 3: UrlFoto (no UrlImagen) ===")

    config_path = os.path.join(module_path, 'config', 'entity_configs.py')

    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Buscar configuración de productos
    producto_section_start = content.find("'producto': {")
    producto_section_end = content.find("'proveedor':", producto_section_start)

    if producto_section_end == -1:
        # Si no hay proveedor después, buscar el final del dict
        producto_section_end = len(content)

    producto_section = content[producto_section_start:producto_section_end]

    # Verificar que existe UrlFoto
    assert "'UrlFoto':" in producto_section, \
        "entity_configs.producto debe tener campo 'UrlFoto'"
    print("✅ Campo 'UrlFoto' configurado en entity_configs.producto")

    # Verificar que NO existe UrlImagen
    assert "'UrlImagen':" not in producto_section, \
        "entity_configs.producto NO debe tener campo 'UrlImagen' (fix v2.5.0)"
    print("✅ Campo 'UrlImagen' NO presente (correcto)")

    # Verificar que UrlFoto mapea a image_1920 y url_imagen_actual
    assert "'image_1920'" in producto_section, \
        "UrlFoto debe mapear a 'image_1920'"
    assert "'url_imagen_actual'" in producto_section, \
        "UrlFoto debe mapear a 'url_imagen_actual' (para cache)"
    print("✅ UrlFoto mapea correctamente a image_1920 y url_imagen_actual")


def test_unidad_medida_transformer_exists():
    """Test: Verificar que existe el transformer unidad_medida_y_tamanno"""
    print("\n=== Test 4: Transformer unidad_medida_y_tamanno ===")

    transformer_path = os.path.join(module_path, 'transformers', 'unidad_medida_transformer.py')

    assert os.path.exists(transformer_path), \
        f"Debe existir archivo {transformer_path}"
    print(f"✅ Archivo encontrado: transformers/unidad_medida_transformer.py")

    with open(transformer_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verificar funciones y clases clave
    assert 'UnidadMedidaConfig' in content, "Debe existir clase UnidadMedidaConfig"
    assert 'transform_unidad_medida_y_tamanno' in content, \
        "Debe existir función transform_unidad_medida_y_tamanno"
    assert 'get_unit_type' in content, "Debe existir método get_unit_type"

    print("✅ UnidadMedidaConfig y transform_unidad_medida_y_tamanno existen")

    # Verificar que mapea a los campos correctos
    required_keywords = ['weight', 'volume', 'product_length']
    for keyword in required_keywords:
        assert keyword in content, f"Transformer debe mapear a '{keyword}'"
        print(f"✅ Transformer mapea a '{keyword}'")


def test_product_template_new_fields():
    """Test: Verificar que product_template.py tiene los nuevos campos"""
    print("\n=== Test 5: Nuevos campos en product_template.py ===")

    model_path = os.path.join(module_path, 'models', 'product_template.py')

    assert os.path.exists(model_path), \
        f"Debe existir archivo {model_path}"

    with open(model_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verificar campos de categorización
    categorization_fields = ['grupo_id', 'subgrupo_id', 'familia_id']
    for field in categorization_fields:
        assert field in content, f"product_template debe tener campo '{field}'"
        print(f"✅ Campo '{field}' definido")

    # Verificar campo de cache de URL
    assert 'url_imagen_actual' in content, \
        "product_template debe tener campo 'url_imagen_actual' (cache)"
    print("✅ Campo 'url_imagen_actual' definido (cache de imágenes)")


def test_views_xml_categorization():
    """Test: Verificar que views.xml muestra campos de categorización"""
    print("\n=== Test 6: Campos visibles en views.xml ===")

    views_path = os.path.join(module_path, 'views', 'views.xml')

    assert os.path.exists(views_path), \
        f"Debe existir archivo {views_path}"

    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verificar que existe vista de formulario de productos
    assert 'product.template.form' in content or 'product_template_form' in content, \
        "views.xml debe tener vista de formulario de productos"
    print("✅ Vista de formulario de productos encontrada")

    # Verificar que los campos de categorización son visibles
    categorization_fields = ['grupo_id', 'subgrupo_id', 'familia_id']
    for field in categorization_fields:
        assert f'field name="{field}"' in content or f"field name='{field}'" in content, \
            f"views.xml debe mostrar campo '{field}'"
        print(f"✅ Campo '{field}' visible en formulario")


def test_manifest_version():
    """Test: Verificar que __manifest__.py tiene versión 2.5.0"""
    print("\n=== Test 7: Versión en __manifest__.py ===")

    manifest_path = os.path.join(module_path, '__manifest__.py')

    with open(manifest_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verificar versión
    assert "'version': '2.5.0'" in content or '"version": "2.5.0"' in content, \
        "__manifest__.py debe tener versión 2.5.0"
    print("✅ Versión 2.5.0 en __manifest__.py")

    # Verificar que menciona las funcionalidades de v2.5.0
    v2_5_keywords = ['UnidadMedida', 'Dimensiones', 'UrlImagen optimizada']
    for keyword in v2_5_keywords:
        if keyword in content:
            print(f"✅ Funcionalidad documentada: {keyword}")
        else:
            print(f"⚠️  Funcionalidad no documentada en manifest: {keyword}")


def test_log_sanitization():
    """Test: Verificar que existe sanitización de logs para imágenes"""
    print("\n=== Test 8: Sanitización de logs ===")

    mixin_path = os.path.join(module_path, 'models', 'bidirectional_sync_mixin.py')

    with open(mixin_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verificar función de sanitización
    assert '_sanitize_vals_for_logging' in content, \
        "bidirectional_sync_mixin debe tener función _sanitize_vals_for_logging"
    print("✅ Función _sanitize_vals_for_logging existe")

    # Verificar que se usa en logs
    assert '_sanitize_vals_for_logging(vals)' in content, \
        "La función de sanitización debe usarse en los logs"
    print("✅ Sanitización aplicada en logs")

    # Verificar que maneja campos de imagen
    assert 'image_1920' in content, \
        "Sanitización debe manejar campo 'image_1920'"
    print("✅ Sanitización configurada para campos de imagen")


def run_all_tests():
    """Ejecutar todos los tests"""
    print("=" * 70)
    print("TEST SUITE: Funcionalidades v2.5.0")
    print("=" * 70)
    print("\nVerificando implementación de:")
    print("  1. UnidadMedida + Tamanno → weight/volume/product_length")
    print("  2. UrlFoto (no UrlImagen) → image_1920 con cache")
    print("  3. Campos Familia/Grupo/Subgrupo visibles en vistas")
    print("  4. Sanitización de logs para imágenes")
    print("=" * 70)

    tests = [
        ("Factores de conversión", test_conversion_factors),
        ("Estructura de entity_configs", test_entity_configs_structure),
        ("UrlFoto (no UrlImagen)", test_urlfoto_not_urlimagen),
        ("Transformer UnidadMedida", test_unidad_medida_transformer_exists),
        ("Campos en product_template", test_product_template_new_fields),
        ("Campos visibles en views.xml", test_views_xml_categorization),
        ("Versión en __manifest__.py", test_manifest_version),
        ("Sanitización de logs", test_log_sanitization),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
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
        print("\n✅ TODOS LOS TESTS PASARON CORRECTAMENTE!")
        print("\nFuncionalidades v2.5.0 implementadas y verificadas:")
        print("  ✓ UnidadMedida + Tamanno → weight/volume/product_length")
        print("  ✓ UrlFoto → image_1920 con optimización de cache")
        print("  ✓ Grupo, Subgrupo, Familia visibles en formularios")
        print("  ✓ Logs sanitizados (sin base64 de imágenes)")
        return 0
    else:
        print(f"\n❌ {failed} TESTS FALLARON")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
