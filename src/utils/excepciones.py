class GCCConexionError(Exception):
    """No se pudo establecer conexión con el DW GCC."""
    pass

class GCCNoActualizadoError(Exception):
    """El DW GCC no está actualizado al día de hoy."""
    pass

class CorteNoProgramadoError(Exception):
    """No se encontró un corte programado para el día de hoy."""
    pass

class TipoNoCompatible(Exception):
    """El tipo de dato no es compatible"""
    pass

class ColumnasFaltantes(Exception):
    """Al DataFrame le hacen falta columnas"""
    pass

class ErrorExportandoArchivo(Exception):
    """Ocurrio un error inesperado exportando"""
    pass