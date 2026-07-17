import pandas as pd
from pathlib import Path
from src.utils.excepciones import ErrorExportandoArchivo, ColumnasFaltantes

def consolidar_detallado(periodo: str) -> pd.DataFrame:

    """Consolida todos los parquet de gastos calculados del período en un único DataFrame.

    Lee todos los archivos .parquet en data/calculado/{periodo}/, valida que cada uno
    contenga las 19 columnas del histórico detallado, descarta columnas adicionales
    si las hay, y retorna el DataFrame concatenado ordenado por CEDULA y CORTE.

    Args:
        periodo (str): Período efectivo en formato 'YYYY-MM', ej. '2026-06'.
            Debe ser el período ya ajustado (mes siguiente si corte 30).

    Returns:
        pd.DataFrame: DataFrame consolidado con todos los cortes del período,
            ordenado por CEDULA y CORTE ascendente.

    Raises:
        ColumnasFaltantes: Si algún archivo parquet no contiene las 19 columnas
            requeridas por el histórico detallado.
    """
    # --- Se leen los archivos .parquet del mes --- #

    print(f"Consolidando periodo: {periodo}...")

    # --- Se genera la ruta a consultar --- #
    ruta_consultar = Path(f"data/calculado/{periodo}")

    archivos_parquet = list(ruta_consultar.glob("*.parquet"))

    list_file = []

    columnas = [
        'PERIODO', 'FECHA_CORTE','FECHA_PROCESO',
        'CORTE','CEDULA','NOMBRE_ASOCIADO','NUMERO_CREDITO',
        'TIPO_CREDITO','DIAS_MORA','TRAMO_MORA','PORCENTAJE_GASTO',
        'VALOR_VENCIDO','VALOR_GASTO_CALCULADO_PROYECTADO',
        'VALOR_GASTO_CALCULADO','VALOR_FACTURADO_CXCRED',
        'TOTAL_GASTO_CEDULA_CORTE','TOTAL_GASTO_CEDULA_TAYLOR', 
        'PARTICIPACION_CREDITO','ESTADO_CREDITO', 'ESTADO_ASOCIADO'
    ]
    
    for file in archivos_parquet:
        print(f"Leyendo: {Path(file).name}...")
        try:
            temp_file = pd.read_parquet(file,
                                    engine="pyarrow")

            ## --- Validaciones columnas --- ##

            col_faltantes = [c for c in columnas if c not in temp_file.columns]

            if col_faltantes:
                raise ColumnasFaltantes(f"Faltan Columnas en :{Path(file).name}:: {col_faltantes}")

            col_adicionales = [c for c in temp_file.columns if c not in columnas]

            if col_adicionales:
                print(f"Se encontraron columnas adicionales en:{Path(file).name}:: {col_adicionales}")
                print("Eliminando columnas adicionales...")
                temp_file.drop(columns=col_adicionales,
                               inplace=True
                               )

            ## --- Se agrega para concatenar --- ##
            list_file.append(temp_file)
        except ColumnasFaltantes as e:
            raise e

    ## --- Se concatenan todos los archivos --- ##
    df_consolidado = (pd.concat(list_file,
                               ignore_index=True
                               )
                      .sort_values(by=['CORTE','CEDULA'],
                                   ascending=[True,True]
                                   )
                      .reset_index(drop=True)
                      )

    return df_consolidado

def exportar_detalle(df_consolidado:pd.DataFrame,
                     periodo:str,
                     cfg: dict) -> None:

    """Exporta el histórico detallado consolidado a Excel en la ruta compartida del período.

    Construye el directorio de salida a partir de cfg['paths']['salida_compartida']
    y el período recibido. El archivo se nombra: Historico_Detallado_{periodo}.xlsx.

    Args:
        df_consolidado (pd.DataFrame): DataFrame producido por consolidar_detallado().
        periodo (str): Período efectivo en formato 'YYYY-MM'. Se usa tanto para el
            directorio de salida como para el nombre del archivo.
        cfg (dict): Configuración del proceso. Debe contener 'paths.salida_compartida'.

    Returns:
        None

    Raises:
        ErrorExportandoArchivo: Si ocurre un error al escribir el archivo Excel.
    """
    # --- Se construye la ruta de salida --- #

    path_salida = Path(f"{cfg['paths']['salida_compartida']}/{periodo}/detallado")

    ## --- Si el path no existe, se crea el directorio --- ##

    if not path_salida.exists():
        print(f"Creando directorio: {path_salida}...")
        path_salida.mkdir(parents=True, exist_ok=True)
    else:
        print(f"Directorio: {path_salida} ya existe...")

    print(f"Exportando base detallada...")
    try:
        df_consolidado.to_excel(f"{path_salida}/Historico_Detallado_{periodo}.xlsx",
                                index=False)
        print(f"Base Historica Consolidada exportada: Cortes: {[f'corte: {c} -' for c in df_consolidado['CORTE'].unique().tolist()]}")
    except Exception as e:
        raise ErrorExportandoArchivo(f"Ocurrio un error exportando historico: {e}") from e

def run_detallado(periodo: str,
                  cfg: dict) -> None:
    """Orquesta la consolidación y exportación del histórico detallado del período.

    Consolida todos los parquet de gastos calculados del período en un único
    DataFrame y lo exporta a Excel en la ruta compartida.

    Args:
        periodo (str): Período efectivo en formato 'YYYY-MM', ej. '2026-06'.
            Debe ser el período ya ajustado (mes siguiente si corte 30).
        cfg (dict): Configuración del proceso. Debe contener 'paths.salida_compartida'.

    Returns:
        None

    Raises:
        ColumnasFaltantes: Si algún parquet del período no contiene las columnas
            requeridas por el histórico detallado.
        ErrorExportandoArchivo: Si ocurre un error al escribir el archivo Excel.
    """
    df_consolidado = consolidar_detallado(periodo)
    exportar_detalle(df_consolidado=df_consolidado,
                     periodo=periodo,
                     cfg=cfg)
