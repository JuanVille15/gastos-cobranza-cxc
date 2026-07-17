from pathlib import Path
from src.conexion.gcc_client import ejecutar_query
from src.utils.excepciones import TipoNoCompatible

def extraer_cartera(fecha_proceso:str, 
                    periodo:str,
                    tipos:dict) -> None:
    """
    Extrae la cartera de clientes vencida y la guarda en un archivo parquet.

    Args:
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.
        periodo (str): Periodo en el que dejara la informacion extraida.

    Side Effects:
    Escribe un archivo parquet en data/raw/{periodo}/cartera_{fecha_proceso}.parquet
    
    Raises:
        FileNotFoundError: Si el archivo de consulta SQL no se encuentra.
        GCCConexionError: Si no se puede establecer la conexión.
        
    """
    query_path = Path("sql/cartera_vencida.sql")
    
    if not query_path.exists():
        raise FileNotFoundError(f"Query file not found: {query_path}")
    
    df_cartera = ejecutar_query(query_path)
    
    ## -- Se aseguran tipos de datos --
    try:
        
        for c in df_cartera.columns:
            if c == 'CORTE':
                df_cartera[c] = df_cartera[c].astype(int).astype(tipos[c])
            else:
                df_cartera[c] = df_cartera[c].astype(tipos[c])
            
    except Exception as e:
        raise TipoNoCompatible(f"El tipo de dato no es compatible: {e}")

    # Guardar el DataFrame en un parquet -- imprimiendo el proceso
    output_path = Path(f"data/raw/{periodo}")
    if output_path.exists():
        print(f"El directorio {output_path} ya existe. Continuando con la extracción...")
    else:
        print(f"Creando directorio: {output_path}")
        output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Guardando cartera en: {output_path}")
    df_cartera.to_parquet(f"{output_path}/cartera_{fecha_proceso}.parquet", 
                          index=False, 
                          engine='pyarrow')
    print(rf"Cartera raw correctamente cargada: {output_path}\cartera_{fecha_proceso}.parquet")