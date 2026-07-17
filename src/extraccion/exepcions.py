import pandas as pd
from pathlib import Path
from src.conexion.gcc_client import ejecutar_query
import json

def extrac_excepcions(exp_path:str, 
                      fecha_proceso:str,
                      periodo: str) -> None:
    
    """
    Función para extraer los datos de excepciones desde un archivo EXCEL.

    Args:
        exp_path (str): Ruta compartida que contiene el archivo .xslx con los datos de excepciones.

    Returns:
        pd.DataFrame: DataFrame con los datos de excepciones.
    """
    
    # -- Se mapea el ultimo archivos .xlsx de la ruta compartida --
    
    ruta = Path(exp_path)
    ultimo_archivo = max(ruta.glob('*.xlsx'), key=lambda x: x.stat().st_mtime)
    
    ## -- Se intenta leer el archivo .xlsx y convertirlo a DataFrame --
    try:
        
        ## -- Se lee el archivo .xlsx de excepciones --
        df_excepcions = pd.read_excel(ultimo_archivo)
        
        ## -- Se crea el directorio de salida si no existe --
        ruta_salida = f"data/raw/{periodo}/excepcions"
        if not Path(ruta_salida).exists():
            print(f"Creando directorio: {ruta_salida}")
            Path(ruta_salida).mkdir(parents=True, exist_ok=True)
        else:
            print(f"Directorio ya existe: {ruta_salida}, continuando con la escritura del archivo.")
            
        ## -- Se guarda el DataFrame de excepciones en formato .csv --
        df_excepcions.to_csv(f"{ruta_salida}/excepcions_{fecha_proceso}.csv", index=False)
        print(f"Archivo de excepciones guardado correctamente: {ruta_salida}/excepcions_{fecha_proceso}.csv")
        
    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo .xlsx en la ruta: {exp_path}")
    except Exception as e:
        raise Exception(f"Ocurrió un error al procesar el archivo de excepciones: {str(e)}")
    
def extract_estados_fallecidos(query_path:str,
                               fecha_proceso:str,
                               periodo:str) -> None:
    
    ## -- Se valida la existencia del archivo de consulta --
    
    if not Path('sql/estados_fallecidos.sql').exists():
        raise FileNotFoundError(f"El archivo de consulta '{query_path}' no existe.")
    
    query = Path(query_path)
    
    ## -- Se ejecuta la consulta SQL para obtener los estados de fallecidos --
    try:
        df_fallecidos = ejecutar_query(query)
        print("Consulta ejecutada correctamente, datos de fallecidos obtenidos.")
        
        ## -- Se guarda el DataFrame de estados de fallecidos en formato .json --
        
        ### -- Se define la ruta de salida para el archivo JSON --
        ruta_salida = f"data/raw/{periodo}/excepcions/fallecidos_{fecha_proceso}.json"

        ### -- Se crea el writer --
        with open(ruta_salida, 'w') as f:
            json.dump(df_fallecidos.to_dict(orient='list'), f, indent=4)
        print(f"Archivo de estados de fallecidos guardado correctamente: {ruta_salida}")
        
    except FileNotFoundError:
        raise FileNotFoundError(f"El archivo de consulta '{query_path}' no existe.")
    except Exception as e:
        raise Exception(f"Ocurrió un error al ejecutar la consulta de estados de fallecidos: {str(e)}")
    
def extract_asignacion(asignacion_path:str,
                       fecha_proceso:str,
                       periodo:str,
                       ) -> None:

    """
    Función para extraer los datos de asignación desde el último archivo EXCEL de una ruta compartida y guardarlos en formato .csv.

    Args:
        asignacion_path (str): Ruta compartida que contiene el archivo .xlsx con los datos de asignación.
        fecha_proceso (str): Fecha de proceso utilizada para nombrar el archivo .csv de salida.
        periodo (str): Periodo utilizado para construir la ruta de salida ("data/raw/{periodo}/excepcions").

    Raises:
        FileNotFoundError: Si la ruta proporcionada no existe o no contiene ningún archivo .xlsx.
        Exception: Si ocurre un error al leer el archivo .xlsx o al guardar el archivo .csv resultante.

    Returns:
        None
    """
    ruta = Path(asignacion_path)
    
    if not ruta.exists():
        raise FileNotFoundError(f'La ruta proporcionada no existe:{asignacion_path}')
    
    # --- Se mapea el ultimo archivo ---
    
    ultimo_archivo = max(ruta.glob('*.xlsx'), key= lambda x: x.stat().st_mtime)
    
    try:
        # --- Se lee el ultimo archivo de la ruta --- #
        
        asignacion = pd.read_excel(
            ultimo_archivo, 
            engine='openpyxl', 
        )
        print(f'Asignacion leida correctamente✅')
        
        # --- Se crea el directorio de salida 
        
        ruta_salida = f"data/raw/{periodo}/excepcions"
        if not Path(ruta_salida).exists():
            print(f"Creando directorio: {ruta_salida}")
            Path(ruta_salida).mkdir(parents=True, exist_ok=True)
        else:
            print(f"Directorio ya existe: {ruta_salida}, continuando con la escritura del archivo.")
        
        # --- Se guarda el archivo de asignacion en .csv --- #
        asignacion.to_csv(
            f'{ruta_salida}/asignacion_{fecha_proceso}.csv', 
            index=False, 
        )
        print(f'Archivo asignacion guardado correctamente: {ruta_salida}/asignacion_{fecha_proceso}.csv')
    
    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró archivo .xlsx en la ruta: {asignacion_path}")
    except Exception as e:
        raise Exception(f"Ocurrió un error al procesar el archivo de asignacion: {str(e)}") from e