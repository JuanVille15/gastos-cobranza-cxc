import pandas as pd
from pathlib import Path
import json

def read_raw(periodo:str, fecha_proceso:str) -> pd.DataFrame:
    """
    Lee el archivo parquet de cartera vencida y devuelve un DataFrame.

    Args:
        periodo (str): Periodo en el que se encuentra la información.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.

    Returns:
        pd.DataFrame: DataFrame con la cartera vencida.
    
    Raises:
        FileNotFoundError: Si el archivo parquet no se encuentra.
    """
    file_path = f"data/raw/{periodo}/cartera_{fecha_proceso}.parquet"
    
    try:
        df_cartera = pd.read_parquet(file_path, engine='pyarrow')
        print(f"Archivo leído correctamente: {file_path}")
        return df_cartera
    except FileNotFoundError:
        print(f"Archivo no encontrado: {file_path}")
        raise

def extraer_tipos() -> dict:
    
    """Lee el archivo de tipos de datos desde config/data_types.json.

    Returns:
        dict: Diccionario con los tipos de datos esperados para las columnas
        de la cartera raw, extraído de la clave 'raw_data' del JSON.

    Raises:
        FileNotFoundError: Si config/data_types.json no existe en la ruta esperada.
    """
    ## -- Ruta de data_types.json
    
    path_types = 'config/data_types.json'
    
    if not Path(path_types).exists():
        raise FileNotFoundError(f"No se encontró archivo de tipos en: {path_types}")
    
    ## -- Se lee el .json --
    
    with open(Path(path_types), "r", encoding="utf-8") as f:
        tipos = dict(json.load(f)).get("raw_data", {})

    return tipos

def print_step(mensaje: str) -> None:
    ancho = 50
    print(f"\n{'=' * ancho}")
    print(f"  {mensaje}")
    print(f"{'=' * ancho}")
