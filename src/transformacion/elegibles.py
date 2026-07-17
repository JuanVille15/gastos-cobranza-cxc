import pandas as pd
from pathlib import Path
import json

## ================
## LEER DEPENDENCIAS
## ================

def read_raw(periodo:str, fecha_proceso:str) -> pd.DataFrame:
    """Lee el archivo parquet de cartera vencida para un período y fecha dados.

    Args:
        periodo (str): Subcarpeta del período, ej. '2026-05'.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.

    Returns:
        pd.DataFrame: DataFrame con la cartera vencida del período.

    Raises:
        FileNotFoundError: Si el archivo parquet no existe en la ruta esperada.
    """
    file_path = f"data/raw/{periodo}/cartera_{fecha_proceso}.parquet"
    
    try:
        df_cartera = pd.read_parquet(file_path, engine='pyarrow')
        print(f"Archivo leído correctamente: {file_path}")
        return df_cartera
    except FileNotFoundError:
        print(f"Archivo no encontrado: {file_path}")
        raise
    
def read_excepcions(periodo:str, 
                    fecha_proceso:str) -> dict:
    """Lee los archivos de excepciones (cédulas jurídicas, fallecidos y asignación) para un período.

    Args:
        periodo (str): Subcarpeta del período, ej. '2026-05'.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.

    Returns:
        dict: Diccionario con tres entradas:
            - 'cedulas_juridicos' (pd.DataFrame): Cédulas excluidas por tipo jurídico.
            - 'estados_excluidos' (pd.DataFrame): Estados de asociados fallecidos.
            - 'asignacion' (pd.DataFrame): Asignación de asociados por sub-campaña/actor.

    Raises:
        FileNotFoundError: Si el archivo CSV de cédulas, el JSON de fallecidos o el CSV de asignación no existen.
    """
    ## -- Se construye la ruta del archivo de excepciones --
    file_path = f"data/raw/{periodo}/excepcions/excepcions_{fecha_proceso}.csv"
    
    ## -- Se construye la ruta del archivo de estados exepciones --
    
    path_estados = f"data/raw/{periodo}/excepcions/fallecidos_{fecha_proceso}.json"
    
    ## -- Se construye la ruta del archivo de asignacion -- ##
    
    path_asignacion = f"data/raw/{periodo}/excepcions/asignacion_{fecha_proceso}.csv"
    
    results = {}
    
    try:
        ## -- Se lee el archivo de excepciones en formato CSV --
        df_excepcions = pd.read_csv(file_path)
        print(f"Archivo de excepciones leído correctamente: {file_path}")
        
        ## -- Se asigna el archivo en el dict de resultados --
        results['cedulas_juridicos']= df_excepcions
    
    except FileNotFoundError:
        print(f"Archivo de excepciones no encontrado: {file_path}")
        raise
    
    try:
        ## -- Se lee el .json de estados excluidos --
        with open(path_estados, "r",encoding="utf-8") as f:
            estados = json.load(f)
        
        ## -- Se genera un df con los estados --
        
        estados_df = pd.DataFrame(estados)
        
        ## -- Se asigna el archivo en el dict de resultados --
        results['estados_excluidos'] = estados_df
    
    except FileNotFoundError:
        print(f"Archivo estados excluidos no encontrado: {path_estados}")
        raise
    
    try:
        ## --- Se lee archivo de asignaciones --- ##
        asignacion = pd.read_csv(
            path_asignacion, 
            sep=',', 
            engine='pyarrow'
        )
        print(f"Archivo de asignacion leído correctamente: {path_asignacion}")

        ## --- Se asigna el archivo en el dict de resultados --- ##
        results['asignacion'] = asignacion
         
    except FileNotFoundError:
        print(f"Archivo asignación no encontrado: {path_asignacion}")
        raise

    return results

## ================
## FILTERS
## ================
    
def filter_elegibles(df_cartera:pd.DataFrame, 
                     cfg:dict,
                     schedule_result:dict,
                     excepciones:dict) -> pd.DataFrame:
    """Filtra la cartera vencida y retorna solo los asociados elegibles para cobro.

    Aplica los siguientes criterios de exclusión en orden:
        1. Solo registros del corte programado para hoy.
        2. Mínimo 30 días de mora.
        3. Estado de crédito no excluido según configuración.
        4. Cédula no registrada en las listas de excepciones (jurídicos y fallecidos).
        5. Cédula registrada en asignación para alguna de las sub-campañas configuradas.

    Args:
        df_cartera (pd.DataFrame): DataFrame con la cartera vencida completa.
        cfg (dict): Configuración del proceso. Debe contener 'params.estados_excluidos'
            y 'params.subcampannas'.
        schedule_result (dict): Resultado de schedule_task(). Debe contener 'tasks_to_run'
            con al menos un elemento con la clave 'codigo_corte'.
        excepciones (dict): Resultado de read_excepciones(). Claves esperadas:
            - 'cedulas_juridicos' (pd.DataFrame): Cédulas excluidas por tipo jurídico.
            - 'estados_excluidos' (pd.DataFrame): Estados de asociados fallecidos.
            - 'asignacion' (pd.DataFrame): Asignación de asociados por sub-campaña/actor.

    Returns:
        pd.DataFrame: Subconjunto de df_cartera con los asociados elegibles.

    Raises:
        ValueError: Si el dict de excepciones contiene claves no permitidas.
    """
    # -- Filtramos los clientes elegibles según la lógica de negocio --
    
    ## -- Se extrae el corte del asociado del resultado del scheduler --
    corte_asociado = schedule_result["tasks_to_run"][0]["codigo_corte"]
    
    if str(corte_asociado)[-2:] == '05':
        corte_asociado = '5'
    else:
        corte_asociado = str(corte_asociado)[-2:]
        
    ## -- Se extrae los estados excluidos de .yml config --
    
    estados_excluidos = cfg['params']['estados_excluidos']
        
    ## -- Se filtran los asociados que corresponden al corte del asociado --
    df_elegibles = (df_cartera[df_cartera['CORTE'] == corte_asociado]
                    .copy())
    
    ## -- Se consideran solo asociados con más de 30 días de mora --
    df_elegibles = (df_elegibles[df_elegibles['DIAS_MORA'] > 30])
    
    ## -- Se filtran los asociados cuyos creditos estan estados_excluidos --
    df_elegibles = (df_elegibles[df_elegibles['ESTADO_CREDITO']
                                 .isin(estados_excluidos) == False])
    
    ## -- Se extraen los 2 dfs de excepciones ---
    
    nombres_validos = ['cedulas_juridicos',
                       'estados_excluidos', 
                       'asignacion']
    
    for c in excepciones.keys():
        if c not in nombres_validos:
            raise ValueError(f"Excepcion no permitida:{c}"
                             f"\nLos valores validos son: {nombres_validos}")
        else:
            continue
    
    excepciones_juridicas = excepciones['cedulas_juridicos']
    df_estados_fallecidos = excepciones['estados_excluidos']
    asignacion = excepciones['asignacion']
    
    ## -- Se excluyen los asociados que se encuentran en el DataFrame de excepciones --
    
    nombre_col_cedula = excepciones_juridicas.columns[0]  # Asumimos que la primera columna contiene las cédulas
    
    df_elegibles = (df_elegibles
                    [~df_elegibles['CEDULA']
                     .astype(int)
                     .isin(excepciones_juridicas[nombre_col_cedula]
                           .astype(int))]
                    )
    
    ## -- Se excluyen estados de asociados fallecidos --

    df_elegibles = (
        df_elegibles[~df_elegibles['ESTM_NOMBRE']
                     .isin(df_estados_fallecidos['Nombre_Estado'])
                     ]
    )
    
    ## --- Se excluyen asociados que no se encuentren asignados a PROCOBAS --- #
    
    asignacion_final = (
        asignacion
        .loc[
            asignacion['ACTOR'].isin(
                cfg['params']['subcampannas']
            ), 
        ]
    )
    
    df_elegibles = (
        df_elegibles
        .loc[
            (df_elegibles['CEDULA']
             .astype(int).isin(
               asignacion_final['ASO_IDENTIFICACION']
               .astype(int)
            ))
        ]
    )
    
    return df_elegibles

## ===============
## EXPORT RESULT
## ===============

def export_elegibles(fecha_proceso:str,
                     periodo:str,
                     df_elegibles: pd.DataFrame) -> None:
    
    """Exporta el DataFrame de elegibles a parquet en la carpeta de salida del período.

    Args:
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'. Se usa en el nombre del archivo.
        periodo (str): Subcarpeta del período, ej. '2026-05'.
        df_elegibles (pd.DataFrame): DataFrame con los asociados elegibles ya filtrados.

    Returns:
        None

    Raises:
        OSError: Si no es posible crear el directorio o escribir el archivo parquet.
    """
    ## -- Se define la ruta de salida --
    
    path_salida = Path(f'data/elegibles/{periodo}')
    
    ## -- Si no existe la ruta se crean directorios --
    
    if not path_salida.exists():
        print(f"Creando directorio: {path_salida}")
        path_salida.mkdir(parents=True, exist_ok=True)
    else:
        print(f"El directorio {path_salida} ya existe...")

    print(f"Exportando base elegibles: {len(df_elegibles)} registros")
    df_elegibles.to_parquet(f"{path_salida}/elegibles_{fecha_proceso}.parquet",
                                engine="pyarrow",
                                index=False)
    print(f"Elegibles correctamente exportados")


## ================
## ORQUESTADORA
## ================

def filtrar_elegibles(periodo:str, 
                      fecha_proceso:str,
                      cfg:dict,
                      schedule_result:dict) -> pd.DataFrame:
    
    """Orquesta el proceso completo de filtrado de elegibles para un corte.

    Lee la cartera raw y las excepciones, aplica los filtros de eligibilidad
    y persiste el resultado en data/elegibles/{periodo}/.

    Args:
        periodo (str): Subcarpeta del período, ej. '2026-05'.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.
        cfg (dict): Configuración del proceso. Debe contener 'params.estados_excluidos'
            y 'params.subcampannas'.
        schedule_result (dict): Resultado de schedule_task(). Determina el corte a procesar.

    Returns:
        pd.DataFrame: DataFrame de elegibles, también persistido en parquet como respaldo.

    Raises:
        FileNotFoundError: Si los archivos de cartera o excepciones no existen.
        ValueError: Si el dict de excepciones contiene claves no permitidas.
    """
    # --- Se leen dependencias ---
    print(f"Filtrando Elegibles")
    
    df_raw = read_raw(periodo=periodo,
                      fecha_proceso=fecha_proceso)
    
    excepciones = read_excepcions(periodo=periodo,
                                  fecha_proceso=fecha_proceso)
    
    # --- Se genera los filtros para los elegbles
    
    df_elegibles = filter_elegibles(df_cartera=df_raw,
                                    cfg=cfg,
                                    schedule_result=schedule_result,
                                    excepciones=excepciones)
    print(f"Base elegibles creada: {len(df_elegibles)} registros")
    
    # --- Se exporta la base de elegibles ---
    
    export_elegibles(fecha_proceso=fecha_proceso,
                     periodo=periodo,
                     df_elegibles=df_elegibles)

    # --- Retornar el df para que main lo tenga en memoria ---
    
    return df_elegibles
