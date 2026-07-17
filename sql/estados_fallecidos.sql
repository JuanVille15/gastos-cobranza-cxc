SELECT 
    ESTM_CODIGO AS "Codigo_Estado",
    ESTM_NOMBRE AS "Nombre_Estado"
FROM GCC_ESTADOS_MULTIACTIVA
WHERE
    ESTM_NOMBRE LIKE ('Fallecido%')
    OR ESTM_NOMBRE LIKE ('%Fallecimiento');