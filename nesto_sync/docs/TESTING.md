# Testing - Módulo nesto_sync

## Ejecutar Tests

### Todos los tests del módulo
```bash
# Desde el directorio de Odoo
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo/odoo-bin \
  -c /etc/odoo16.conf \
  -d odoo_test \
  -i nesto_sync \
  --test-enable \
  --stop-after-init \
  --log-level=test
```

### Solo tests de BOM
```bash
# Tests unitarios de BOM
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo/odoo-bin \
  -c /etc/odoo16.conf \
  -d odoo_test \
  --test-tags=nesto_sync.test_bom_sync \
  --stop-after-init \
  --log-level=test

# Tests de integración de BOM
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo/odoo-bin \
  -c /etc/odoo16.conf \
  -d odoo_test \
  --test-tags=nesto_sync.test_bom_integration \
  --stop-after-init \
  --log-level=test
```

### Tests específicos
```bash
# Test específico por nombre de clase
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo/odoo-bin \
  -c /etc/odoo16.conf \
  -d odoo_test \
  --test-tags=/TestBomSync \
  --stop-after-init \
  --log-level=test
```

## Cobertura de Tests

### Tests BOM Sync (test_bom_sync.py)
- ✅ `test_sync_bom_create_simple`: Crear BOM básica
- ✅ `test_sync_bom_update_components`: Actualizar componentes
- ✅ `test_sync_bom_delete_empty`: Eliminar BOM con ProductosKit vacío
- ✅ `test_sync_bom_missing_component`: Error con componente faltante
- ✅ `test_sync_bom_direct_cycle`: Detectar ciclo directo (A → A)
- ✅ `test_sync_bom_indirect_cycle`: Detectar ciclo indirecto (A → B → A)
- ✅ `test_sync_bom_format_objects`: Formato objetos
- ✅ `test_sync_bom_format_ids`: Formato array IDs
- ✅ `test_sync_bom_format_json_string`: Formato JSON string
- ✅ `test_sync_bom_no_change_skip_update`: Skip update sin cambios
- ✅ `test_producto_mtp_not_saleable`: MTP no vendible
- ✅ `test_producto_normal_saleable`: Productos normales vendibles

### Tests BOM Integration (test_bom_integration.py)
- ✅ `test_flow_nesto_to_odoo_to_nesto`: Flujo completo bidireccional
- ✅ `test_multiple_kits_shared_components`: Kits con componentes compartidos
- ✅ `test_nested_bom_valid`: BOMs anidadas sin ciclos
- ✅ `test_update_bom_from_nesto`: Actualizar BOM desde Nesto
- ✅ `test_delete_bom_from_nesto`: Eliminar BOM desde Nesto
- ✅ `test_modify_bom_in_odoo_publishes_to_nesto`: Modificar en Odoo → Publicar
- ✅ `test_producto_mtp_in_bom_not_saleable`: MTP como componente

**Total:** 19 tests

## Crear Base de Datos de Prueba

```bash
# Crear nueva base de datos para tests
createdb -U odoo odoo_test

# Inicializar con módulo nesto_sync
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo/odoo-bin \
  -c /etc/odoo16.conf \
  -d odoo_test \
  -i nesto_sync \
  --stop-after-init
```

## Tests en CI/CD

Para integración continua, usar:

```bash
# Ejecutar todos los tests y generar reporte
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo/odoo-bin \
  -c /etc/odoo16.conf \
  -d odoo_test \
  --test-enable \
  --stop-after-init \
  --log-level=test \
  2>&1 | tee test_results.log

# Verificar resultado (exit code 0 = éxito)
echo $?
```

## Debugging Tests

### Ver logs detallados
```bash
# Ejecutar con debug completo
/opt/odoo16/odoo-venv/bin/python3 /opt/odoo16/odoo/odoo-bin \
  -c /etc/odoo16.conf \
  -d odoo_test \
  --test-tags=nesto_sync.test_bom_sync \
  --stop-after-init \
  --log-level=debug
```

### Ejecutar test individual con pdb
```python
# Añadir breakpoint en el test
import pdb; pdb.set_trace()
```

## Limpiar Base de Datos de Tests

```bash
# Eliminar base de datos de tests
dropdb -U odoo odoo_test
```

## Checklist Pre-Deploy

Antes de desplegar a producción, ejecutar:

- [ ] Todos los tests unitarios pasan
- [ ] Todos los tests de integración pasan
- [ ] No hay warnings en los logs
- [ ] Verificar performance de tests (< 30s total)
- [ ] Revisar cobertura de código (opcional con coverage.py)

## Troubleshooting

### Error: "database 'odoo_test' does not exist"
```bash
createdb -U odoo odoo_test
```

### Error: "module nesto_sync not found"
Verificar que el módulo está en el addons_path:
```bash
grep addons_path /etc/odoo16.conf
```

### Tests muy lentos
Usar base de datos en memoria (solo Linux):
```bash
# Crear tmpfs para PostgreSQL
sudo mount -t tmpfs -o size=2G tmpfs /var/lib/postgresql/test_data
```
