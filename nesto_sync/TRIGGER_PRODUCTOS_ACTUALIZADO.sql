-- ================================================
-- TRIGGER ACTUALIZADO: Productos (v2.5.0)
-- ================================================
-- Este trigger detecta cambios en productos y los registra
-- para sincronización con Odoo
--
-- IMPORTANTE: Incluye TODOS los campos sincronizados:
-- - Nombre, PrecioProfesional (PVP), Estado, RoturaStockProveedor
-- - CodBarras (CodigoBarras)
-- - Tamaño (Tamanno), UnidadMedida
-- - Grupo, Subgrupo, Familia
-- - UrlFoto
-- - Ficticio
-- ================================================

ALTER TRIGGER [dbo].[tr_Productos_Sync_Update]
ON [dbo].[Productos]
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- Solo procesar si NO es el usuario del sistema RDS2016$
    -- (evitar bucles de sincronización cuando Odoo escribe a Nesto)
    IF (SYSTEM_USER != 'NUEVAVISION\RDS2016$')
    BEGIN
        -- Verificar si algún campo ha cambiado
        -- Comparamos inserted (valores nuevos) vs deleted (valores viejos)
        IF EXISTS (
            SELECT 1
            FROM inserted i
            JOIN deleted d ON i.Empresa = d.Empresa AND i.Número = d.Número
            WHERE
                -- ========================================
                -- CAMPOS DE TEXTO (con trim para ignorar espacios)
                -- ========================================
                ISNULL(LTRIM(RTRIM(i.Nombre)), '') <> ISNULL(LTRIM(RTRIM(d.Nombre)), '') OR
                ISNULL(LTRIM(RTRIM(i.CodBarras)), '') <> ISNULL(LTRIM(RTRIM(d.CodBarras)), '') OR
                ISNULL(LTRIM(RTRIM(i.Grupo)), '') <> ISNULL(LTRIM(RTRIM(d.Grupo)), '') OR
                ISNULL(LTRIM(RTRIM(i.Subgrupo)), '') <> ISNULL(LTRIM(RTRIM(d.Subgrupo)), '') OR
                ISNULL(LTRIM(RTRIM(i.Familia)), '') <> ISNULL(LTRIM(RTRIM(d.Familia)), '') OR
                ISNULL(LTRIM(RTRIM(i.UnidadMedida)), '') <> ISNULL(LTRIM(RTRIM(d.UnidadMedida)), '') OR
                ISNULL(LTRIM(RTRIM(i.UrlFoto)), '') <> ISNULL(LTRIM(RTRIM(d.UrlFoto)), '') OR

                -- ========================================
                -- CAMPOS NUMÉRICOS
                -- ========================================
                ISNULL(i.PVP, 0) <> ISNULL(d.PVP, 0) OR
                ISNULL(i.Estado, 0) <> ISNULL(d.Estado, 0) OR
                ISNULL(i.RoturaStockProveedor, 0) <> ISNULL(d.RoturaStockProveedor, 0) OR
                ISNULL(i.Tamaño, 0) <> ISNULL(d.Tamaño, 0) OR

                -- ========================================
                -- CAMPOS BOOLEANOS/BIT
                -- ========================================
                ISNULL(i.Ficticio, 0) <> ISNULL(d.Ficticio, 0) OR

                -- ========================================
                -- DETECCIÓN EXPLÍCITA DE CAMBIOS NULL ↔ VALOR
                -- (necesario porque ISNULL puede ocultar cambios)
                -- ========================================

                -- Campos de texto
                (i.Nombre IS NULL AND d.Nombre IS NOT NULL) OR
                (i.Nombre IS NOT NULL AND d.Nombre IS NULL) OR

                (i.CodBarras IS NULL AND d.CodBarras IS NOT NULL) OR
                (i.CodBarras IS NOT NULL AND d.CodBarras IS NULL) OR

                (i.Grupo IS NULL AND d.Grupo IS NOT NULL) OR
                (i.Grupo IS NOT NULL AND d.Grupo IS NULL) OR

                (i.Subgrupo IS NULL AND d.Subgrupo IS NOT NULL) OR
                (i.Subgrupo IS NOT NULL AND d.Subgrupo IS NULL) OR

                (i.Familia IS NULL AND d.Familia IS NOT NULL) OR
                (i.Familia IS NOT NULL AND d.Familia IS NULL) OR

                (i.UnidadMedida IS NULL AND d.UnidadMedida IS NOT NULL) OR
                (i.UnidadMedida IS NOT NULL AND d.UnidadMedida IS NULL) OR

                (i.UrlFoto IS NULL AND d.UrlFoto IS NOT NULL) OR
                (i.UrlFoto IS NOT NULL AND d.UrlFoto IS NULL) OR

                -- Campos numéricos
                (i.PVP IS NULL AND d.PVP IS NOT NULL) OR
                (i.PVP IS NOT NULL AND d.PVP IS NULL) OR

                (i.Estado IS NULL AND d.Estado IS NOT NULL) OR
                (i.Estado IS NOT NULL AND d.Estado IS NULL) OR

                (i.RoturaStockProveedor IS NULL AND d.RoturaStockProveedor IS NOT NULL) OR
                (i.RoturaStockProveedor IS NOT NULL AND d.RoturaStockProveedor IS NULL) OR

                (i.Tamaño IS NULL AND d.Tamaño IS NOT NULL) OR
                (i.Tamaño IS NOT NULL AND d.Tamaño IS NULL) OR

                -- Campos booleanos
                (i.Ficticio IS NULL AND d.Ficticio IS NOT NULL) OR
                (i.Ficticio IS NOT NULL AND d.Ficticio IS NULL)
        )
        BEGIN
            -- Si hay cambios, insertar en la tabla de sincronización
            INSERT INTO Nesto_sync (Tabla, ModificadoId)
            SELECT 'Productos', i.Número
            FROM inserted i
            WHERE i.Empresa = '1'
            GROUP BY i.Número;

            -- Log opcional (descomentar para debugging)
            -- PRINT 'Trigger Productos: Cambios detectados para ' + CAST(@@ROWCOUNT AS VARCHAR) + ' productos';
        END
    END
END
GO

-- ================================================
-- VERIFICACIÓN DEL TRIGGER
-- ================================================
-- Para verificar que el trigger está activo:
-- SELECT name, is_disabled FROM sys.triggers WHERE name = 'tr_Productos_Sync_Update';
--
-- Para ver el código del trigger:
-- EXEC sp_helptext 'tr_Productos_Sync_Update';
-- ================================================

-- ================================================
-- NOTAS DE VERSIÓN
-- ================================================
-- v2.5.0 (2025-11-17):
--   - Añadidos campos nuevos: Grupo, Subgrupo, Familia
--   - Añadidos campos nuevos: Tamaño, UnidadMedida
--   - Añadidos campos nuevos: UrlFoto
--   - Añadido campo: Ficticio
--   - Total campos sincronizados: 12 campos
--
-- v2.4.x:
--   - Campos básicos: Nombre, PVP, Estado, RoturaStockProveedor, CodBarras
--   - Total campos sincronizados: 5 campos
-- ================================================
