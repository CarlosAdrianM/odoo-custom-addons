#!/usr/bin/env python3
"""
Test de sanitización de valores para logging

Verifica que _sanitize_value_for_logging funcione correctamente
sin necesidad de cargar todo Odoo
"""


def _sanitize_value_for_logging(value):
    """
    Sanitiza un valor individual para logging, reemplazando datos binarios grandes con resúmenes

    Args:
        value: Valor a sanitizar (puede ser str, bytes, o cualquier otro tipo)

    Returns:
        Valor sanitizado apto para logging
    """
    # Detectar si es un campo de imagen (base64 o bytes)
    if isinstance(value, bytes):
        return f"<binary_data: {len(value)} bytes>"

    if isinstance(value, str):
        # Detectar base64 de imágenes o string representation de bytes
        # Típicamente empiezan con caracteres específicos o "b'..."
        is_image_data = (
            value.startswith('iVBOR') or  # PNG base64
            value.startswith('/9j/') or    # JPEG base64
            value.startswith('R0lGOD') or  # GIF base64
            value.startswith("b'iVBOR") or  # String repr of PNG bytes
            value.startswith("b'/9j/") or   # String repr of JPEG bytes
            value.startswith('b"iVBOR') or
            value.startswith('b"/9j/')
        )

        # Si parece imagen y es suficientemente largo, sanitizar
        if is_image_data and len(value) > 100:
            return f"<image_data: {len(value)} bytes>"

        # Truncar strings muy largos (no imagen)
        if len(value) > 200:
            return value[:200] + "..."

    return value


def test_sanitization():
    """Test: Verificar sanitización de valores"""
    print("\n=== Test: Sanitización de Valores para Logging ===\n")

    # Test 1: Base64 PNG
    test_base64_png = 'iVBORw0KGgoAAAANSUhEUgAAARoAAAFCCAYAAAAubhIgAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAgAElEQVR' + 'A' * 1000
    result = _sanitize_value_for_logging(test_base64_png)
    assert '<image_data:' in result and 'bytes>' in result, "Base64 PNG debe sanitizarse"
    print(f"✅ Base64 PNG sanitizado: {result}")

    # Test 2: Base64 JPEG
    test_base64_jpeg = '/9j/4AAQSkZJRgABAQAAAQABAAD' + 'A' * 1000
    result = _sanitize_value_for_logging(test_base64_jpeg)
    assert '<image_data:' in result and 'bytes>' in result, "Base64 JPEG debe sanitizarse"
    print(f"✅ Base64 JPEG sanitizado: {result}")

    # Test 3: Base64 PNG con prefijo b' (como aparece en logs)
    test_base64_with_prefix = "b'iVBORw0KGgoAAAA" + 'A' * 1000
    result = _sanitize_value_for_logging(test_base64_with_prefix)
    assert '<image_data:' in result and 'bytes>' in result, "Base64 con prefijo b' debe sanitizarse"
    print(f"✅ Base64 con prefijo b' sanitizado: {result}")

    # Test 4: Bytes
    test_bytes = b'binary data here' * 100
    result = _sanitize_value_for_logging(test_bytes)
    assert '<binary_data:' in result and 'bytes>' in result, "Bytes debe sanitizarse"
    print(f"✅ Bytes sanitizado: {result}")

    # Test 5: String largo (no imagen)
    test_long_string = 'A' * 300
    result = _sanitize_value_for_logging(test_long_string)
    assert len(result) <= 203, "String largo debe truncarse a 200 + '...'"
    assert result.endswith('...'), "String truncado debe terminar con '...'"
    print(f"✅ String largo truncado: {result[:50]}... (length: {len(result)})")

    # Test 6: String corto normal
    test_normal = 'Producto ABC'
    result = _sanitize_value_for_logging(test_normal)
    assert result == test_normal, "String normal no debe modificarse"
    print(f"✅ String normal sin cambios: {result}")

    # Test 7: Número
    test_number = 12345
    result = _sanitize_value_for_logging(test_number)
    assert result == test_number, "Números no deben modificarse"
    print(f"✅ Número sin cambios: {result}")

    # Test 8: None
    test_none = None
    result = _sanitize_value_for_logging(test_none)
    assert result is None, "None no debe modificarse"
    print(f"✅ None sin cambios: {result}")

    # Test 9: Caso real del log reportado
    real_log_case = "b'iVBORw0KGgoAAAANSUhEUgAAARoAAAFCCAYAAAAubhIgAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAgAElEQVR42uy9eZBcyXkn9st8r6q6uqvvE2iggcF9DIAZYDDDOTjD4ZAcmZI2JFG7FLUrO7yW/YcjvBGyww6Hvbthx2rXG..."
    result = _sanitize_value_for_logging(real_log_case)
    assert '<image_data:' in result and 'bytes>' in result, "Caso real del log debe sanitizarse"
    print(f"✅ Caso real sanitizado: {result}")

    print("\n✅ TODOS LOS TESTS DE SANITIZACIÓN PASARON!\n")
    print("Antes del fix, los logs mostraban:")
    print("  Cambio en image_1920: 'b'iVBORw0KGgoAAAA... (miles de caracteres)")
    print("\nDespués del fix, los logs mostrarán:")
    print("  Cambio en image_1920: '<image_data: 109328 bytes>' -> '<image_data: 110000 bytes>'")
    print("\n✅ Fix completo y funcional\n")


if __name__ == '__main__':
    test_sanitization()
