-- =====================================================================
-- MIGRACIÓN DE DATOS v2.6.0
-- Migrar volúmenes existentes de volume (m³) a volume_ml (ml)
-- =====================================================================
-- IMPORTANTE: Este script solo debe ejecutarse UNA VEZ en producción
-- después de actualizar el módulo a v2.6.0
-- =====================================================================

\echo ''
\echo '====================================================================='
\echo 'MIGRACIÓN v2.6.0: Conversión de volume a volume_ml'
\echo '====================================================================='
\echo ''

-- 1. Verificar que el campo volume_ml existe
\echo '--- Paso 1: Verificar campo volume_ml ---'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_template'
        AND column_name = 'volume_ml'
    ) THEN
        RAISE EXCEPTION 'ERROR: Campo volume_ml no existe. Actualizar módulo primero.';
    END IF;
    RAISE NOTICE '✅ Campo volume_ml existe';
END $$;

-- 2. Contar productos afectados
\echo ''
\echo '--- Paso 2: Productos que serán migrados ---'
SELECT COUNT(*) as "Productos con volume > 0 y volume_ml = 0"
FROM product_template
WHERE volume > 0
AND (volume_ml IS NULL OR volume_ml = 0);

-- 3. Mostrar ejemplos de productos que se migrarán
\echo ''
\echo '--- Paso 3: Ejemplos de productos a migrar (top 10) ---'
SELECT
    id,
    default_code as "Código",
    name as "Nombre",
    volume as "Volume actual (m³)",
    (volume * 1000000)::numeric(16,2) as "volume_ml calculado (ml)",
    CASE
        WHEN (volume * 1000000) < 1000 THEN CONCAT((volume * 1000000)::numeric(16,2), ' ml')
        ELSE CONCAT(((volume * 1000000) / 1000)::numeric(16,2), ' l')
    END as "Display"
FROM product_template
WHERE volume > 0
AND (volume_ml IS NULL OR volume_ml = 0)
ORDER BY volume DESC
LIMIT 10;

-- 4. BACKUP de datos antes de migrar (por seguridad)
\echo ''
\echo '--- Paso 4: Crear tabla de backup ---'
DROP TABLE IF EXISTS product_template_volume_backup_v260;
CREATE TABLE product_template_volume_backup_v260 AS
SELECT
    id,
    default_code,
    name,
    volume,
    volume_ml,
    write_date
FROM product_template
WHERE volume > 0
AND (volume_ml IS NULL OR volume_ml = 0);

\echo ''
SELECT COUNT(*) as "Productos respaldados"
FROM product_template_volume_backup_v260;

-- 5. MIGRACIÓN: Convertir volume (m³) a volume_ml (ml)
\echo ''
\echo '--- Paso 5: EJECUTANDO MIGRACIÓN ---'
\echo 'Fórmula: volume_ml = volume × 1,000,000 (m³ → ml)'
\echo ''

UPDATE product_template
SET volume_ml = (volume * 1000000)::numeric(16,2)
WHERE volume > 0
AND (volume_ml IS NULL OR volume_ml = 0);

-- 6. Verificar resultados
\echo ''
\echo '--- Paso 6: Verificar resultados de migración ---'
SELECT
    COUNT(*) as "Total migrados",
    MIN(volume_ml) as "Volumen mínimo (ml)",
    MAX(volume_ml) as "Volumen máximo (ml)",
    AVG(volume_ml)::numeric(16,2) as "Volumen promedio (ml)"
FROM product_template
WHERE volume_ml > 0;

-- 7. Mostrar productos migrados (ejemplos)
\echo ''
\echo '--- Paso 7: Ejemplos de productos migrados (top 10) ---'
SELECT
    id,
    default_code as "Código",
    volume as "Volume (m³)",
    volume_ml as "volume_ml (ml)",
    CASE
        WHEN volume_ml < 1000 THEN CONCAT(volume_ml, ' ml')
        ELSE CONCAT((volume_ml / 1000)::numeric(16,2), ' l')
    END as "Display"
FROM product_template
WHERE volume_ml > 0
ORDER BY volume_ml DESC
LIMIT 10;

-- 8. Validar coherencia (volume y volume_ml deben coincidir)
\echo ''
\echo '--- Paso 8: Validar coherencia volume ↔ volume_ml ---'
SELECT
    COUNT(*) as "Productos con discrepancia"
FROM product_template
WHERE volume_ml > 0
AND volume > 0
AND ABS((volume * 1000000) - volume_ml) > 0.01;  -- Tolerancia de 0.01 ml

-- Si hay discrepancias, mostrarlas
DO $$
DECLARE
    discrepancias INT;
BEGIN
    SELECT COUNT(*) INTO discrepancias
    FROM product_template
    WHERE volume_ml > 0
    AND volume > 0
    AND ABS((volume * 1000000) - volume_ml) > 0.01;

    IF discrepancias > 0 THEN
        RAISE WARNING '⚠️  Se encontraron % productos con discrepancias', discrepancias;
        RAISE NOTICE 'Revisar manualmente estos productos';
    ELSE
        RAISE NOTICE '✅ Todos los productos tienen coherencia volume ↔ volume_ml';
    END IF;
END $$;

-- 9. Resumen final
\echo ''
\echo '====================================================================='
\echo 'RESUMEN DE MIGRACIÓN v2.6.0'
\echo '====================================================================='
\echo ''

SELECT
    'Total productos migrados' as "Métrica",
    COUNT(*)::text as "Valor"
FROM product_template_volume_backup_v260
UNION ALL
SELECT
    'Productos con volume_ml > 0',
    COUNT(*)::text
FROM product_template
WHERE volume_ml > 0
UNION ALL
SELECT
    'Backup guardado en tabla',
    'product_template_volume_backup_v260'
ORDER BY 1;

\echo ''
\echo '====================================================================='
\echo '✅ MIGRACIÓN COMPLETADA'
\echo '====================================================================='
\echo ''
\echo 'NOTAS:'
\echo '1. La tabla de backup se mantendrá hasta confirmar que todo funciona'
\echo '2. Para eliminar el backup: DROP TABLE product_template_volume_backup_v260;'
\echo '3. Verificar logs de Odoo tras reiniciar el servicio'
\echo '4. Probar sincronización con Nesto'
\echo ''
