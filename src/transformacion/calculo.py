import pandas as pd
import numpy as np
from pathlib import Path
import datetime
import json

def _read_tramos_json(path_tramos:str) -> dict:
    """Lee el archivo JSON de configuración de tramos de mora.

    Args:
        path_tramos (str): Ruta al archivo JSON de tramos, ej. 'config/tramos_mora.json'.

    Returns:
        dict: Contenido completo del JSON con la clave 'tramos' y sus atributos.

    Raises:
        FileNotFoundError: Si el archivo no existe en la ruta indicada.
    """
    if not Path(path_tramos).exists():
        raise FileNotFoundError(f"Archivo de tramos no encontrado: {path_tramos}")
    
    with open(path_tramos, 'r') as f:
        tramos_mora = json.load(f)
    
    return tramos_mora


def build_tramos(df_cartera:pd.DataFrame) -> pd.DataFrame:
    """Asigna el tramo de mora a cada registro del DataFrame según config/tramos_mora.json.

    Lee los rangos de días definidos en el JSON y crea la columna 'TRAMO_MORA'
    usando asignación condicional con df.loc.

    Args:
        df_cartera (pd.DataFrame): DataFrame de elegibles con la columna 'DIAS_MORA'.

    Returns:
        pd.DataFrame: El mismo DataFrame con la columna 'TRAMO_MORA' añadida.

    Raises:
        FileNotFoundError: Si config/tramos_mora.json no existe.
    """
    #-- Lee el .json de tramos --
    
    tramos_mora:dict = _read_tramos_json('config/tramos_mora.json')
    
    
    # --- Extraemos la logica de los tramos del .json ---
    
    dicc_tramos = {}
    
    for tramo in tramos_mora.get('tramos', []):
        nombre_tramo = tramo.get('codigo')
        dias_min = tramo.get('dias_min')
        dias_max = tramo.get('dias_max')
        
        if nombre_tramo is None or dias_min is None:
            print(f"Tramo incompleto en el JSON: {tramo}")
            continue
        
        dicc_tramos[nombre_tramo] = [dias_min, dias_max]

    # --- Asignamos los tramos al DataFrame ---
    
    dicc_tramos["TRAMO_GT150"][1] = float('inf')  # Reemplazamos el valor de dias_max para el tramo mayor a 150 días
    
    for nombre_tramo, [dias_min, dias_max] in dicc_tramos.items():
        df_cartera.loc[
            (df_cartera['DIAS_MORA'] >= dias_min) & (df_cartera['DIAS_MORA'] <= dias_max),
            'TRAMO_MORA'
        ] = nombre_tramo

    return df_cartera

def calcular_gastos(df_cartera:pd.DataFrame) -> pd.DataFrame:
    
    """Calcula el gasto de cobranza teórico por crédito según el tramo de mora asignado.

    Usa el porcentaje parametrizado en config/tramos_mora.json para calcular:
        - PORCENTAJE_GASTO: porcentaje del tramo correspondiente.
        - VALOR_GASTO_CALCULADO_PROYECTADO: VALOR_VENCIDO * PORCENTAJE_GASTO (redondeado
          hacia abajo). Es el gasto bruto sin descontar lo ya facturado; se conserva
          en el detallado como columna de auditoría.

    El descuento de VALOR_FACTURADO_CXCRED y el cálculo final de VALOR_GASTO_CALCULADO
    se realizan en distribuir_facturado(), luego de distribuir el facturado por
    participación de crédito.

    Args:
        df_cartera (pd.DataFrame): DataFrame con las columnas 'TRAMO_MORA' y 'VALOR_VENCIDO'.
            Requiere que build_tramos() haya sido ejecutado previamente.

    Returns:
        pd.DataFrame: El mismo DataFrame con las columnas 'PORCENTAJE_GASTO' y
            'VALOR_GASTO_CALCULADO_PROYECTADO' añadidas.

    Raises:
        FileNotFoundError: Si config/tramos_mora.json no existe.
    """
    #-- Lee el .json de tramos --
    
    tramos_mora:dict = _read_tramos_json('config/tramos_mora.json')
    
    # --- Extraemos la logica de los tramos del .json ---
    
    dicc_tramos = {}
    
    for tramo in tramos_mora.get('tramos', []):
        nombre_tramo = tramo.get('codigo')
        porcentaje = tramo.get('porcentaje')
        
        if nombre_tramo is None or porcentaje is None:
            print(f"Tramo incompleto en el JSON: {tramo}")
            continue
        
        dicc_tramos[nombre_tramo] = porcentaje
    
    # --- Calculamos los gastos de cobranza ---
    for nombre_tramo, porcentaje in dicc_tramos.items():
        df_cartera.loc[df_cartera['TRAMO_MORA'] == nombre_tramo, 
                       'PORCENTAJE_GASTO'] = porcentaje
        df_cartera.loc[df_cartera['TRAMO_MORA'] == nombre_tramo, 
                       'VALOR_GASTO_CALCULADO_PROYECTADO'] = np.floor(df_cartera['VALOR_VENCIDO'] 
                                                           * porcentaje) # -- Se redondea hacia abajo el valor del gasto calculado para evitar decimales

    
    return df_cartera

def calcular_participacion(df_cartera:pd.DataFrame) -> pd.DataFrame:

    """Calcula la participación de cada crédito dentro del gasto proyectado total de su cédula.

    Agrupa por CEDULA para obtener el gasto bruto total del corte (TOTAL_GASTO_CEDULA_CORTE_PROYECTADO)
    y determina qué proporción de ese total representa cada crédito individual. Esta
    participación se usa en distribuir_facturado() para prorratear el VALOR_FACTURADO_CXCRED
    (que viene a nivel de cédula) entre los créditos de esa cédula.

    Args:
        df_cartera (pd.DataFrame): DataFrame con las columnas 'CEDULA' y
            'VALOR_GASTO_CALCULADO_PROYECTADO'. Requiere que calcular_gastos() haya
            sido ejecutado previamente.

    Returns:
        pd.DataFrame: El mismo DataFrame con las columnas 'TOTAL_GASTO_CEDULA_CORTE_PROYECTADO'
            y 'PARTICIPACION_CREDITO' (redondeada a 2 decimales) añadidas.
    """

    # -- Se calcula el total de gastos por cedula --- #
        
    df_cartera['TOTAL_GASTO_CEDULA_CORTE_PROYECTADO'] = (df_cartera
                                                .groupby('CEDULA')['VALOR_GASTO_CALCULADO_PROYECTADO']
                                                .transform('sum'))
    
    # --- Se calcula la participación de cada crédito en el gasto total por cedula ---
    
    df_cartera['PARTICIPACION_CREDITO'] = (df_cartera['VALOR_GASTO_CALCULADO_PROYECTADO'] / 
                                           df_cartera['TOTAL_GASTO_CEDULA_CORTE_PROYECTADO']).astype(float).round(2) # -- Se redondea a 2 decimales la participación para facilitar su interpretación
    
    return df_cartera

def distribuir_facturado(df_cartera:pd.DataFrame) -> pd.DataFrame:

    """Distribuye el valor facturado por cédula entre sus créditos y calcula el gasto real a cargar.

    El VALOR_FACTURADO_CXCRED viene a nivel de cédula desde la cartera; esta función
    lo prorratea a nivel de crédito usando la PARTICIPACION_CREDITO calculada en
    calcular_participacion(). Con el facturado distribuido calcula:
        - VALOR_GASTO_CALCULADO: si el proyectado - facturado distribuido < 0, queda en 0;
          de lo contrario, es la diferencia (gasto neto real a cobrar por crédito).
        - TOTAL_GASTO_CEDULA_CORTE: suma de VALOR_GASTO_CALCULADO por cédula (el total
          real a cargar en Taylor).

    La columna auxiliar TOTAL_GASTO_CEDULA_CORTE_PROYECTADO se descarta al retornar,
    ya que solo fue necesaria para calcular PARTICIPACION_CREDITO.

    Args:
        df_cartera (pd.DataFrame): DataFrame con las columnas 'VALOR_FACTURADO_CXCRED',
            'PARTICIPACION_CREDITO' y 'VALOR_GASTO_CALCULADO_PROYECTADO'. Requiere que
            calcular_participacion() haya sido ejecutado previamente.

    Returns:
        pd.DataFrame: El mismo DataFrame con 'VALOR_FACTURADO_CXCRED' actualizado a nivel
            de crédito, y las columnas 'VALOR_GASTO_CALCULADO' y 'TOTAL_GASTO_CEDULA_CORTE'
            añadidas. Se elimina 'TOTAL_GASTO_CEDULA_CORTE_PROYECTADO'.
    """

    # --- Se distribuye el gasto x fila segun la participacion x credito --- #
    
    df_cartera['VALOR_FACTURADO_CXCRED'] = (
        (
            df_cartera['VALOR_FACTURADO_CXCRED'] * 
            df_cartera['PARTICIPACION_CREDITO']
        )
    ).round(0).astype(int)
    
    # --- Se genera el calculo gasto real mes // Se tiene en cuenta lo que tiene facturado anteriormente --- #
    
    df_cartera['VALOR_GASTO_CALCULADO'] = np.where(
        (
            (df_cartera['VALOR_GASTO_CALCULADO_PROYECTADO'] -
            df_cartera['VALOR_FACTURADO_CXCRED']) < 0
        ),
        0,
        (
            (df_cartera['VALOR_GASTO_CALCULADO_PROYECTADO'] -
            df_cartera['VALOR_FACTURADO_CXCRED'])
        )
    ).round(0).astype(int)
    
    # --- Se genera columna TOTAL_GASTO_CEDULA_CORTE --- #
    
    df_cartera['TOTAL_GASTO_CEDULA_CORTE'] = (
        df_cartera.groupby('CEDULA')['VALOR_GASTO_CALCULADO']
        .transform('sum')
    )
    
    df_cartera['TOTAL_GASTO_CEDULA_TAYLOR'] = (
        df_cartera
        .groupby('CEDULA')[['VALOR_GASTO_CALCULADO', 'VALOR_FACTURADO_CXCRED']]
        .transform('sum')
        .sum(axis=1)
    )
    
    return df_cartera.drop(
        columns='TOTAL_GASTO_CEDULA_CORTE_PROYECTADO'
    )


def build_hist_detallado(df_cartera:pd.DataFrame,
                          fecha_proceso:str,
                          periodo:str,
                          schedule_result:dict) -> pd.DataFrame:
    
    """Prepara el DataFrame de salida con las columnas requeridas para el histórico detallado.

    Agrega las columnas de contexto temporal (PERIODO, FECHA_PROCESO, FECHA_CORTE) y
    selecciona únicamente las columnas definidas para el archivo de salida.
    Para el corte 30, PERIODO se desplaza al mes siguiente por convención contable.

    Args:
        df_cartera (pd.DataFrame): DataFrame con los gastos y participación ya calculados.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.
        periodo (str): Período del corte en formato 'YYYY-MM', ej. '2026-05'.
        schedule_result (dict): Resultado de schedule_task(). Se usa para extraer
            el código de corte y la fecha de caída.

    Returns:
        pd.DataFrame: DataFrame con las columnas mínimas del histórico detallado
            según el requerimiento.
    """
    # -- Se generan columnas adicionales para el archivo de salida --
    
    ## -- Condicional para corte 30 --
    
    fecha_corte = schedule_result["tasks_to_run"][0]["fecha_proceso"]

    df_cartera['PERIODO'] = periodo.replace("-", "")
        
    ## -- Se formatean las fechas de proceso y corte para el archivo de salida --

    df_cartera['FECHA_PROCESO'] = ((datetime.datetime
                                   .strptime(fecha_proceso, "%Y-%m-%d")
                                   .strftime("%Y-%m-%d"))
                                   
    )
    
    df_cartera['FECHA_CORTE'] = (
                                (datetime.datetime
                                 .strptime(fecha_corte, "%Y-%m-%d")
                                 .strftime("%Y-%m-%d"))
    )
    
    ## -- Se seleccionan las columnas para el archivo de salida --
    
    col_salida = [
        'PERIODO', 'FECHA_CORTE','FECHA_PROCESO',
        'CORTE','CEDULA','NOMBRE_ASOCIADO','NUMERO_CREDITO',
        'TIPO_CREDITO','DIAS_MORA','TRAMO_MORA','PORCENTAJE_GASTO',
        'VALOR_VENCIDO','VALOR_GASTO_CALCULADO_PROYECTADO',
        'VALOR_GASTO_CALCULADO','VALOR_FACTURADO_CXCRED',
        'TOTAL_GASTO_CEDULA_CORTE','TOTAL_GASTO_CEDULA_TAYLOR', 
        'PARTICIPACION_CREDITO', 'ESTADO_CREDITO', 'ESTADO_ASOCIADO'
    ]
    
    df_cartera.rename(columns={"ESTM_NOMBRE":"ESTADO_ASOCIADO"}, 
                      inplace=True
                      )

    return df_cartera[col_salida]

def exportar_detallado(df_cartera:pd.DataFrame,
                       fecha_proceso:str,
                       periodo:str) -> pd.DataFrame:

    """Exporta el histórico detallado del corte a parquet en data/calculado/{periodo}/.

    El período recibido ya debe estar ajustado al mes correcto antes de llamar
    esta función.

    Args:
        df_cartera (pd.DataFrame): DataFrame con el histórico detallado preparado.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'. Se usa en el nombre del archivo.
        periodo (str): Período efectivo en formato 'YYYY-MM', ej. '2026-06'.

    Returns:
        pd.DataFrame: El mismo DataFrame recibido, sin modificaciones.
    """
    ## --- Se crea el directorio
    
    ruta_salida = Path(f"data/calculado/{periodo}")
    
    if not ruta_salida.exists():
        print(f"Creando directorio: {ruta_salida}...")
        ruta_salida.mkdir(parents=True, exist_ok=True)
    else:
        print(f"Directorio: {ruta_salida} ya existe...")

    ## --- Se exporta df_cartera ---
    print(f"Exportando data calculada...")
    df_cartera.to_parquet(f"{ruta_salida}/calculado_{fecha_proceso}.parquet",
                          index=False,
                          engine="pyarrow")
    print(f"Data calculada exportada correctamente: {ruta_salida}")

    return df_cartera

def run_calculos(periodo: str,
             fecha_proceso: str,
             schedule_result: dict,
             df_elegibles: pd.DataFrame) -> pd.DataFrame:

    """Orquesta el pipeline completo de cálculo de gastos de cobranza para un corte.

    Ejecuta en orden:
        1. build_tramos: asigna tramo de mora a cada crédito.
        2. calcular_gastos: calcula VALOR_GASTO_CALCULADO_PROYECTADO por tramo.
        3. calcular_participacion: calcula la participación de cada crédito en el
           total proyectado de su cédula.
        4. distribuir_facturado: prorratea el facturado por cédula entre créditos
           y calcula VALOR_GASTO_CALCULADO y TOTAL_GASTO_CEDULA_CORTE reales.
        5. build_hist_detallado: agrega columnas temporales y selecciona col_salida.
        6. exportar_detallado: persiste el resultado en data/calculado/{periodo}/.

    Args:
        periodo (str): Período efectivo en formato 'YYYY-MM', ej. '2026-06'.
        fecha_proceso (str): Fecha del proceso en formato 'YYYY-MM-DD'.
        schedule_result (dict): Resultado de schedule_task(). Se usa para extraer
            el código de corte y la fecha de caída.
        df_elegibles (pd.DataFrame): DataFrame de asociados elegibles filtrados.

    Returns:
        pd.DataFrame: DataFrame del histórico detallado exportado, con todas las
            columnas de auditoría y resultado.

    Raises:
        FileNotFoundError: Si config/tramos_mora.json no existe.
    """

    # --- Se crean los tramos de cobranza --- #
    df = build_tramos(df_elegibles)

    # --- Se calcula el gasto proyectado por tramo --- #
    df = calcular_gastos(df)

    # --- Se calcula la participacion del gasto proyectado por credito --- #
    df = calcular_participacion(df)

    # --- Se distribuye el facturado y se calcula el gasto real --- #
    df = distribuir_facturado(df)

    # --- Se crea estructura del historico --- #
    df = build_hist_detallado(df, fecha_proceso, periodo, schedule_result)

    # --- Se persiste el detallado del corte --- #
    exportar_detallado(df, fecha_proceso, periodo)

    return df