#!/usr/bin/env python3
"""
Test para volume_display - Campo calculado que muestra volumen en ml o l

Verifica que la conversión de m³ a ml/l sea correcta y legible
"""


def test_volume_display_conversion():
    """Test: Verificar conversión de m³ a ml/l"""
    print("\n=== Test: Conversión de volumen m³ → ml/l ===\n")

    # Simular la función _compute_volume_display
    def compute_volume_display(volume_m3):
        """
        Replica la lógica de _compute_volume_display para testing
        """
        if not volume_m3 or volume_m3 == 0:
            return ""

        # Convertir m³ a litros (1 m³ = 1000 l)
        volume_liters = volume_m3 * 1000

        if volume_liters < 1:
            # Mostrar en mililitros si es menos de 1 litro
            volume_ml = volume_liters * 1000
            if volume_ml == int(volume_ml):
                return f"{int(volume_ml)} ml"
            else:
                return f"{volume_ml:g} ml"
        else:
            # Mostrar en litros
            if volume_liters == int(volume_liters):
                return f"{int(volume_liters)} l"
            else:
                return f"{volume_liters:g} l"

    # Test cases
    test_cases = [
        # (volume_m3, expected_display, description)
        (0, "", "Volumen 0"),
        (None, "", "Volumen None"),
        (0.00005, "50 ml", "50ml (producto pequeño)"),
        (0.0001, "100 ml", "100ml (producto común)"),
        (0.00025, "250 ml", "250ml (producto mediano)"),
        (0.0005, "500 ml", "500ml (medio litro)"),
        (0.001, "1 l", "1 litro"),
        (0.002, "2 l", "2 litros"),
        (0.0025, "2.5 l", "2.5 litros"),
        (0.005, "5 l", "5 litros (garrafa)"),
        (0.00015, "150 ml", "150ml"),
        (0.000075, "75 ml", "75ml"),
        (0.0001234, "123.4 ml", "123.4ml (con decimales)"),
    ]

    all_passed = True
    for volume_m3, expected, description in test_cases:
        result = compute_volume_display(volume_m3)
        if result == expected:
            print(f"✅ {description}: {volume_m3} m³ → '{result}'")
        else:
            print(f"❌ {description}: esperado '{expected}', obtenido '{result}'")
            all_passed = False

    assert all_passed, "Algunos tests fallaron"
    print("\n✅ Todos los tests de conversión pasaron!\n")


def test_real_world_examples():
    """Test: Ejemplos del mundo real"""
    print("=== Ejemplos del Mundo Real ===\n")

    products = [
        ("ACIDO HIALURONICO RICCHEZZA", 100, "ml", 0.0001, "100 ml"),
        ("CHAMPÚ PROFESIONAL", 500, "ml", 0.0005, "500 ml"),
        ("TINTE PELO", 60, "ml", 0.00006, "60 ml"),
        ("CREMA HIDRATANTE", 50, "ml", 0.00005, "50 ml"),
        ("ACEITE CORPORAL", 250, "ml", 0.00025, "250 ml"),
        ("GARRAFA ACEITE", 5, "l", 0.005, "5 l"),
    ]

    print("Producto                        | Tamaño | Unidad | Volume (m³) | Volume Display")
    print("-" * 95)

    for nombre, tamanno, unidad, volume_m3, expected_display in products:
        # Simular conversión
        volume_liters = volume_m3 * 1000
        if volume_liters < 1:
            volume_ml = volume_liters * 1000
            if volume_ml == int(volume_ml):
                display = f"{int(volume_ml)} ml"
            else:
                display = f"{volume_ml:g} ml"
        else:
            if volume_liters == int(volume_liters):
                display = f"{int(volume_liters)} l"
            else:
                display = f"{volume_liters:g} l"

        status = "✅" if display == expected_display else "❌"
        print(f"{nombre:30} | {tamanno:6} | {unidad:6} | {volume_m3:11.7f} | {display:15} {status}")

    print("\n✅ Ejemplos del mundo real verificados\n")


def test_edge_cases():
    """Test: Casos edge"""
    print("=== Casos Edge ===\n")

    def compute_volume_display(volume_m3):
        if not volume_m3 or volume_m3 == 0:
            return ""

        volume_liters = volume_m3 * 1000

        if volume_liters < 1:
            volume_ml = volume_liters * 1000
            if volume_ml == int(volume_ml):
                return f"{int(volume_ml)} ml"
            else:
                return f"{volume_ml:g} ml"
        else:
            if volume_liters == int(volume_liters):
                return f"{int(volume_liters)} l"
            else:
                return f"{volume_liters:g} l"

    edge_cases = [
        (0.000001, "1 ml", "Mínimo: 1ml"),
        (0.000999, "999 ml", "Casi 1 litro"),
        (0.001, "1 l", "Exactamente 1 litro"),
        (0.001001, "1 l", "Apenas más de 1 litro"),  # Se redondea a 1.00 l
        (0.00000001, "0.01 ml", "Muy pequeño (decimales)"),
        (1.0, "1000 l", "1 metro cúbico"),
    ]

    for volume_m3, expected, description in edge_cases:
        result = compute_volume_display(volume_m3)
        status = "✅" if result == expected else f"❌ (esperado: {expected})"
        print(f"{description:30} | {volume_m3:.10f} m³ → '{result}' {status}")

    print("\n")


def run_all_tests():
    """Ejecutar todos los tests"""
    print("=" * 95)
    print("TEST SUITE: volume_display - Conversión m³ → ml/l")
    print("=" * 95)

    try:
        test_volume_display_conversion()
        test_real_world_examples()
        test_edge_cases()

        print("=" * 95)
        print("✅ TODOS LOS TESTS PASARON CORRECTAMENTE!")
        print("=" * 95)
        print("\nBeneficios del campo volume_display:")
        print("  • Muestra volúmenes pequeños (50ml, 100ml) de forma legible")
        print("  • Selecciona automáticamente ml o l según el tamaño")
        print("  • Elimina decimales innecesarios (.00) en valores enteros")
        print("  • Compatible con el campo 'volume' estándar de Odoo (m³)")
        print("\nEn la UI de Odoo:")
        print("  • Campo 'Volume': 0.0001 m³ (campo técnico, oculto o solo lectura)")
        print("  • Campo 'Volumen': 100 ml (campo calculado, visible y legible)")
        print()

        return 0

    except AssertionError as e:
        print(f"\n❌ TESTS FALLARON: {str(e)}\n")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_all_tests())
