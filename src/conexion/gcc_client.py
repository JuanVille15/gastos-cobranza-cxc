"""
Módulo de conexión al Data Warehouse GCC.

Provee las funciones necesarias para establecer conexión
y ejecutar queries SQL contra el DW GCC via ODBC.
La cadena de conexión se lee desde la variable de entorno GCC_CON.
"""
import os
import pandas as pd
import pyodbc
from pathlib import Path
from src.utils.excepciones import GCCConexionError

def _get_conexion():
    """
    Establece y retorna una conexión activa al DW GCC.

    La conexión se configura usando la variable de entorno GCC_CON.

    Returns:
        pyodbc.Connection: Objeto de conexión activo.

    Raises:
        GCCConexionError: Si no se puede establecer la conexión.
    """
    try: 
        con = pyodbc.connect(os.getenv('GCC_CON'))
        return con
    except Exception as e:
        raise GCCConexionError(f"Error al conectar a la base GCC: {e}")
    
def ejecutar_query(query:str|Path) -> pd.DataFrame:
    """
    Lee un archivo .sql y lo ejecuta contra el DW GCC.

    Args:
        query (str) | Path: Ruta al archivo .sql que se desea ejecutar.

    Returns:
        pd.DataFrame: Resultado de la consulta como DataFrame.

    Raises:
        FileNotFoundError: Si el archivo .sql no existe en la ruta indicada.
        GCCConexionError: Si falla la conexión al ejecutar la consulta.
    """
    if not Path(query).exists():
        raise FileNotFoundError(f"El archivo de consulta '{query}' no existe.")
    
    with open(query, 'r',encoding='utf-8') as file:
            sql_query = file.read()
            
    con = _get_conexion()
    
    try:
        df = pd.read_sql_query(sql_query, con) #type: ignore
    finally:
        con.close()
    
    return df