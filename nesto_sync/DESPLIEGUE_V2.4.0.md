# Despliegue v2.4.0 - Enriquecimiento de Productos

## Fecha
2025-11-14

## Versión
**2.4.0** - Enriquecimiento de sincronización de productos

## Resumen de Cambios

### Nuevos Campos Mapeados
1. **Estado** → `active` (booleano)
   - `Estado >= 0` → `active = true` (producto activo)
   - `Estado < 0` → `active = false` (producto inactivo)

2. **Grupo** → `grupo_id` (Many2one a product.category)
   - Categoría principal: Cosméticos, Aparatos, Accesorios
   - Se crea automáticamente bajo categoría padre "Grupos"

3. **Subgrupo** → `subgrupo_id` (Many2one a product.category)
   - Subcategoría del producto: Cremas Faciales, IPL, Depilación, etc.
   - Se crea automáticamente bajo categoría padre "Subgrupos"

4. **Familia** → `familia_id` (Many2one a product.category)
   - Marca del producto: Eva Visnú, L'Oréal, etc.
   - Se crea automáticamente bajo categoría padre "Familias/Marcas"

5. **UrlImagen** → `image_1920` (binario)
   - Descarga automática de imagen desde URL
   - Validación con Pillow (PIL)
   - Conversión a base64
   - Timeout: 10 segundos
   - Genera automáticamente 5 resoluciones

### Nuevos Componentes

**Transformers:**
- `grupo` - Busca/crea categoría de Grupo
- `subgrupo` - Busca/crea categoría de Subgrupo
- `familia` - Busca/crea categoría de Familia/Marca
- `url_to_image` - Descarga y procesa imágenes desde URL

**Campos en product.template:**
- `grupo_id` (Many2one)
- `subgrupo_id` (Many2one)
- `familia_id` (Many2one)

**Mejoras en OdooPublisher:**
- Campo `Usuario` con formato `ODOO\{login}` en mensajes Odoo → Nesto

## Requisitos Previos

### Dependencias
- ✅ Pillow (PIL) - **Ya instalado** en el entorno virtual
- ✅ requests - **Ya instalado** en el entorno virtual

Verificar en producción:
```bash
source /opt/odoo16/odoo-venv/bin/activate
pip list | grep -E "Pillow|requests"
```

Si no están instalados:
```bash
pip install Pillow requests
```

## Instrucciones de Despliegue en Producción

### 1. Conectar al Servidor de Producción
```bash
ssh root@217.61.212.170
```

### 2. Ir al Directorio del Módulo
```bash
cd /opt/odoo/custom_addons/nesto_sync
```

### 3. Verificar Estado del Repositorio
```bash
git status
git log --oneline -3
```

### 4. Hacer Pull de los Cambios
```bash
git pull origin main
```

**Verificar que aparezca:**
```
44db018 feat: Enriquecimiento de sincronización de productos v2.4.0
```

### 5. Actualizar el Módulo en Odoo

**Opción A - Actualización en caliente (recomendado):**
```bash
cd /opt/odoo
/opt/odoo/odoo-venv/bin/python3 /opt/odoo/odoo-bin \
  -c /opt/odoo/odoo.conf \
  -u nesto_sync \
  --stop-after-init \
  --logfile=/tmp/odoo_upgrade_v240.log
```

**Opción B - Reinicio completo:**
```bash
systemctl restart odoo16
```

### 6. Verificar que los Campos se Crearon

```bash
sudo -u postgres psql -d odoo16 -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'product_template'
  AND column_name IN ('grupo_id', 'subgrupo_id', 'familia_id')
ORDER BY column_name;
"
```

**Salida esperada:**
```
 column_name | data_type
-------------+-----------
 familia_id  | integer
 grupo_id    | integer
 subgrupo_id | integer
(3 rows)
```

### 7. Verificar Logs de Actualización

```bash
tail -50 /tmp/odoo_upgrade_v240.log | grep -E "(nesto_sync|product_template|grupo_id|subgrupo_id|familia_id)"
```

**Buscar líneas como:**
```
INFO odoo.modules.loading: Loading module nesto_sync (X/Y)
DEBUG odoo.schema: Table 'product_template': added column 'grupo_id' of type int4
DEBUG odoo.schema: Table 'product_template': added column 'subgrupo_id' of type int4
DEBUG odoo.schema: Table 'product_template': added column 'familia_id' of type int4
INFO odoo.modules.loading: Module nesto_sync loaded in X.XXs
```

### 8. Verificar que Odoo Está Activo

```bash
systemctl status odoo16
```

### 9. Monitorear Logs en Tiempo Real

```bash
sudo journalctl -u odoo16 -f
```

Mantener abierto y esperar a que llegue un mensaje de producto desde Nesto.

## Pruebas Post-Despliegue

### Test 1: Verificar Endpoint
```bash
curl -X GET http://localhost:8069/nesto_sync/logs
```

Debería devolver JSON con logs recientes.

### Test 2: Simular Mensaje de Producto (Opcional)

Crear archivo `/tmp/test_producto_prod.json`:
```json
{
  "message": {
    "data": "eyJUYWJsYSI6ICJQcm9kdWN0b3MiLCAiUHJvZHVjdG8iOiAiVEVTVDAwMSIsICJOb21icmUiOiAiUFJVRUJBIFBST0RVQ0NJw5NOIiwgIkVzdGFkbyI6IDEsICJHcnVwbyI6ICJBY2Nlc29yaW9zIiwgIlN1YmdydXBvIjogIkRlc2VjaGFibGVzIiwgIkZhbWlsaWEiOiAiR2Vuw6lyaWNvcyJ9"
  }
}
```

Enviar:
```bash
curl -X POST http://localhost:8069/nesto_sync \
  -H "Content-Type: application/json" \
  -d @/tmp/test_producto_prod.json
```

**Respuesta esperada:**
```json
{"message": "Sincronización completada"}
```

### Test 3: Verificar Producto en Base de Datos
```bash
sudo -u postgres psql -d odoo16 -c "
SELECT
  pt.id,
  pt.name,
  pt.active,
  g.name as grupo,
  s.name as subgrupo,
  f.name as familia
FROM product_template pt
LEFT JOIN product_category g ON pt.grupo_id = g.id
LEFT JOIN product_category s ON pt.subgrupo_id = s.id
LEFT JOIN product_category f ON pt.familia_id = f.id
WHERE pt.producto_externo = 'TEST001';
"
```

### Test 4: Verificar Categorías Creadas
```bash
sudo -u postgres psql -d odoo16 -c "
SELECT
  c.id,
  c.name,
  p.name as parent_name
FROM product_category c
LEFT JOIN product_category p ON c.parent_id = p.id
WHERE c.name IN ('Grupos', 'Subgrupos', 'Familias/Marcas')
   OR p.name IN ('Grupos', 'Subgrupos', 'Familias/Marcas')
ORDER BY c.parent_id NULLS FIRST, c.id;
"
```

## Rollback (Si es Necesario)

### Opción 1: Volver a Versión Anterior
```bash
cd /opt/odoo/custom_addons/nesto_sync
git log --oneline -5  # Identificar commit anterior
git checkout <commit-anterior>
systemctl restart odoo16
```

### Opción 2: Desactivar Campos sin Borrarlos
Los campos nuevos quedarán en la base de datos pero no se usarán.
No requiere acción (compatibilidad hacia atrás garantizada).

## Puntos de Atención

### ⚠️ Descarga de Imágenes
- **Timeout**: 10 segundos por imagen
- **Impacto**: Si muchos productos tienen imágenes, la sincronización será más lenta
- **Manejo de errores**: Si falla la descarga, se registra WARNING en logs pero continúa la sincronización

### ⚠️ Creación Automática de Categorías
- Las categorías se crean automáticamente bajo padres específicos:
  - "Grupos" → "Cosméticos", "Aparatos", "Accesorios"
  - "Subgrupos" → "Cremas Faciales", "IPL", etc.
  - "Familias/Marcas" → "Eva Visnú", "L'Oréal", etc.
- **No hay validación de nombres**: Cualquier valor se creará como categoría

### ✅ Permisos
- Todos los transformers usan `.sudo()` para funcionar con endpoint público
- No requiere configuración adicional de permisos

## Logs a Monitorear

**Logs de éxito:**
```
INFO: Categoría creada: Cosméticos (parent: Grupos) - ID: X
INFO: Descargando imagen desde: https://...
INFO: Imagen descargada correctamente: https://... (XXXX bytes)
INFO: product.template creado con ID: X
```

**Logs de advertencia (normales):**
```
WARNING: URL de imagen inválida (no HTTP/HTTPS): 0
WARNING: Timeout al descargar imagen: https://...
```

**Logs de error (requieren atención):**
```
ERROR: Error en transformer grupo: ...
ERROR: Error inesperado al procesar imagen: ...
```

## Contacto

**Desarrollador:** Carlos Adrián Martínez
**Email:** carlosadrian@nuevavision.es
**Fecha de Implementación:** 2025-11-14

---

## Checklist de Despliegue

- [ ] Conectado al servidor de producción
- [ ] Pull de cambios realizado (commit 44db018)
- [ ] Módulo actualizado con `-u nesto_sync`
- [ ] Campos verificados en base de datos (grupo_id, subgrupo_id, familia_id)
- [ ] Logs revisados sin errores
- [ ] Odoo activo y funcionando
- [ ] Primer producto sincronizado con éxito
- [ ] Categorías creadas automáticamente
- [ ] Imagen descargada correctamente

**Estado:** ⬜ Pendiente | ✅ Completado | ❌ Fallido
