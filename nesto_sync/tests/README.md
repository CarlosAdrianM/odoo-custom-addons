# Tests de nesto_sync

## Ejecutar tests

Desde el directorio `/opt/odoo16`:

```bash
# Todos los tests del módulo
./run_tests.sh

# Solo tests de regresión críticos
./run_tests.sh regression

# Modo verbose (ver detalle de cada test)
./run_tests.sh -v

# Ayuda
./run_tests.sh --help
```

## Estructura de tests

### Tests por funcionalidad

| Archivo | Descripción | Tags |
|---------|-------------|------|
| `test_transformers.py` | Transformers de campos (phone, vendedor, etc.) | `nesto_sync` |
| `test_odoo_publisher.py` | Publicación Odoo → Nesto (VendedorEmail) | `nesto_sync` |
| `test_nombre_regression.py` | **CRÍTICO**: Evitar que nombres se pisen | `nesto_sync`, `regression` |
| `test_bidirectional_sync.py` | Sincronización bidireccional | `nesto_sync` |
| `test_generic_service.py` | Servicio genérico de entidades | `nesto_sync` |
| `test_integration_end_to_end.py` | Tests de integración completos | `nesto_sync` |
| `test_bom_sync.py` | Sincronización de BOMs | `nesto_sync` |

### Tests de regresión críticos

Los tests en `test_nombre_regression.py` son **críticos** y deben ejecutarse siempre antes de desplegar:

```bash
./run_tests.sh regression
```

Estos tests previenen el bug donde el nombre de una persona de contacto sobrescribía el nombre fiscal del cliente.

## Añadir nuevos tests

1. Crear archivo `test_*.py` en `/opt/odoo16/custom_addons/nesto_sync/tests/`
2. Usar el decorador `@tagged`:
   ```python
   from odoo.tests import tagged

   @tagged('post_install', '-at_install', 'nesto_sync')
   class TestMiFeature(TransactionCase):
       ...
   ```
3. Añadir import en `__init__.py`:
   ```python
   from . import test_mi_feature
   ```

### Tags disponibles

- `nesto_sync`: Todos los tests del módulo
- `regression`: Tests críticos de regresión
- `post_install`: Tests que requieren el módulo instalado
- `-at_install`: No ejecutar durante instalación

## Configuración

- **Archivo de config**: `/opt/odoo16/odoo-test.conf`
- **Base de datos de test**: `odoo_test`
- **Log de última ejecución**: `/tmp/odoo_test_output.log`

## Troubleshooting

### Error de conexión a PostgreSQL

Si ves `Peer authentication failed`:

```bash
# Verificar que el usuario existe
sudo -u postgres psql -c "\du"

# Crear BD de test si no existe
sudo -u postgres createdb -O odoo16 odoo_test
```

### Tests muy lentos

Ejecutar solo los tests específicos que necesitas:

```bash
./run_tests.sh regression  # Solo regresión (~30 seg)
```

### Ver output completo

```bash
./run_tests.sh -v
# o revisar el log
cat /tmp/odoo_test_output.log
```
