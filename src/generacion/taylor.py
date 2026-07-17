import pandas as pd
from pathlib import Path
from src.utils.excepciones import ColumnasFaltantes,ErrorExportandoArchivo
import datetime

def build_taylor(df_calculado:pd.DataFrame) -> tuple:
    """Construye el DataFrame de cargue a Taylor consolidado por cédula y separa
    los asociados retirados en un DataFrame aparte.

    Agrupa el gasto por cédula usando drop_duplicates sobre TOTAL_GASTO_CEDULA_CORTE,
    asigna los campos fijos requeridos por Taylor, valida la estructura final y excluye
    de Taylor a los asociados cuyo ESTADO ASOCIADO indique retiro, exclusión o expulsión.

    Args:
        df_calculado (pd.DataFrame): DataFrame con los gastos calculados. Debe contener
            las columnas 'CEDULA', 'TOTAL_GASTO_CEDULA_CORTE' y 'ESTADO_ASOCIADO'.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: Tupla (taylor_final, retirados).
            - taylor_final: Asociados NO retirados, con las 7 columnas del formato Taylor
              (CEDULA, NUMERO CUOTA, VALOR, FECHA CARGUE, CODIGO CONCEPTO, CODIGO SISTEMA, CARGUE).
            - retirados: Asociados retirados/excluidos/expulsados, con las mismas 7 columnas.

    Raises:
        ColumnasFaltantes: Si alguna de las 8 columnas requeridas (incluyendo ESTADO ASOCIADO)
            no está presente tras la construcción del archivo.
    """
    # --- Se agrupa por cedula --- #
    print(f"Creando Archivo Salida Taylor...")
    taylor = (
        df_calculado
        .drop_duplicates(subset=['CEDULA'],
                         ignore_index=True
                         )
        .loc[lambda df: df['VALOR_GASTO_CALCULADO'] > 0, 
             ['CEDULA','TOTAL_GASTO_CEDULA_CORTE','ESTADO_ASOCIADO']
            ]
        .rename(columns={'TOTAL_GASTO_CEDULA_CORTE':'VALOR'})
    )
    print(f"Archivo taylor: {len(taylor)} registros unicos")
    
    # --- Se asignan columnas necesarias ---
    taylor = (taylor
              .assign(
                  NUMERO_CUOTA = 1,
                  FECHA_CARGUE = datetime.datetime.now().strftime("%d/%m/%Y"),
                  CODIGO_CONCEPTO = 'CXCCRED',
                  CODIGO_SISTEMA = 12,
                  CARGUE = 'N'
                    )
              )

    # --- Orden final columnas --- #
    taylor.columns = taylor.columns.str.replace("_"," ") # Se reemplazan guiones por espacios en blanco(Asi viene el REQ)
    
    orden = ['CEDULA', 'NUMERO CUOTA',
             'VALOR', 'FECHA CARGUE',
             'CODIGO CONCEPTO', 'CODIGO SISTEMA',
             'CARGUE', 'ESTADO ASOCIADO']
    
    # --- Validaciones --- #
    col_faltantes = [c for 
                     c in orden 
                     if c not in 
                     taylor.columns
                     ]
    
    if col_faltantes:
        raise ColumnasFaltantes(f"Faltan Columnas en Taylor: {col_faltantes}")
    
    col_adicionales = [c for 
                       c in 
                       taylor.columns if 
                       c not in orden
                       ]
    
    if col_adicionales:
        print(f"Hay columnas adicionales en Taylor: {col_adicionales}")
        ## --- Se eliminan las columnas adicionales --- ##
        print(f"Se eliminan columnas adicionales...")
        taylor.drop(columns=col_adicionales, 
                    inplace=True
                    )
    
    # --- Se crean los 2 DataFrames --- #
    
    palabras_retirados = [
        'Retirado', 
        'Expulsión', 
        'Excluido', 
        'Retiro', 
    ]
    
    patron = '|'.join(palabras_retirados)
    
    ## --- Mask Retirados --- #
    
    mask_retirados = (
        taylor['ESTADO ASOCIADO']
        .str.contains(
            patron, 
            regex=True, 
            na=False
        )
    )
    
    ## --- Split 2 DataFrames --- ##
    
    taylor_final = (
        taylor.loc[~mask_retirados]
    )
    
    retirados = (
        taylor.loc[mask_retirados]
    )
    
    # --- Orden columnas --- #
    taylor_final = taylor_final[orden].drop(
        columns='ESTADO ASOCIADO'
    )

    retirados = retirados[orden].drop(
        columns='ESTADO ASOCIADO'
    )

    return taylor_final,retirados

def exportar_taylor(taylor:pd.DataFrame,
                    retirados:pd.DataFrame,
                    periodo:str,
                    fecha_proceso:str,
                    cfg:dict) -> None:
    """Exporta los archivos de cargue Taylor (vigentes y retirados) a Excel en la ruta compartida del período.

    El directorio de salida se construye a partir de cfg['paths']['salida_compartida']
    y el período recibido. El período ya debe estar ajustado al mes correcto antes
    de llamar esta función. Se generan dos archivos en el mismo directorio:
    Cargue_Taylor_CXCCRED_{fecha_proceso}.xlsx y Cargue_Taylor_Retirados_CXCCRED_{fecha_proceso}.xlsx.

    Args:
        taylor (pd.DataFrame): DataFrame de asociados NO retirados, construido por build_taylor().
        retirados (pd.DataFrame): DataFrame de asociados retirados/excluidos/expulsados,
            construido por build_taylor().
        periodo (str): Período efectivo en formato 'YYYY-MM', ej. '2026-06'.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.
        cfg (dict): Configuración del proceso. Debe contener 'paths.salida_compartida'.

    Returns:
        None

    Raises:
        ErrorExportandoArchivo: Si ocurre un error al escribir alguno de los archivos Excel.
    """
    # --- path_salida --- #

    path_salida = Path(f"{cfg['paths']['salida_compartida']}/{periodo}/taylor")

    ## --- Si el path no existe, se crea el directorio --- ##

    if not path_salida.exists():
        print(f"Creando directorio: {path_salida}...")
        path_salida.mkdir(parents=True, exist_ok=True)
    else:
        print(f"Directorio: {path_salida} ya existe...")

    ## --- Se exporta base para taylor --- ##

    print(f"Exportando base taylor...")
    try:
        taylor.to_excel(f"{path_salida}/Cargue_Taylor_CXCCRED_{fecha_proceso}.xlsx",
                    index=False)
        print(f"Base de taylor exportada: Monto_Total: ${sum(taylor['VALOR']):,}")
    except Exception as e:
        raise ErrorExportandoArchivo(f"Ocurrio un error exportando taylor: {e}")

    ## --- Se exporta base de retirados --- ##

    print(f"Exportando base retirados...")
    try:
        retirados.to_excel(f"{path_salida}/Cargue_Taylor_Retirados_CXCCRED_{fecha_proceso}.xlsx",
                    index=False)
        print(f"Base de retirados exportada: Monto_Total: ${sum(retirados['VALOR']):,}")
    except Exception as e:
        raise ErrorExportandoArchivo(f"Ocurrio un error exportando retirados: {e}")

def run_taylor(df_calculado: pd.DataFrame,
               periodo: str,
               fecha_proceso: str,
               cfg: dict) -> None:
    """Orquesta la generación y exportación de los archivos de cargue a Taylor.

    Construye el archivo consolidado por cédula, separado en asociados vigentes
    y retirados, y exporta ambos a Excel en la ruta compartida del período
    correspondiente.

    Args:
        df_calculado (pd.DataFrame): DataFrame con los gastos calculados.
            Debe contener 'CEDULA', 'TOTAL_GASTO_CEDULA_CORTE' y 'ESTADO_ASOCIADO'.
        periodo (str): Período efectivo en formato 'YYYY-MM', ej. '2026-06'.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.
        cfg (dict): Configuración del proceso. Debe contener 'paths.salida_compartida'.

    Returns:
        None

    Raises:
        ColumnasFaltantes: Si el DataFrame no tiene las columnas requeridas por Taylor.
        ErrorExportandoArchivo: Si ocurre un error al escribir alguno de los archivos Excel.
    """
    taylor, retirados = build_taylor(df_calculado)
    
    exportar_taylor(taylor=taylor,
                    retirados=retirados,
                    periodo=periodo,
                    fecha_proceso=fecha_proceso,
                    cfg=cfg)