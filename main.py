import sys
import datetime
from dotenv import load_dotenv
from src.utils.load_config import load_config
from src.validacion.validar_gcc_actualizado import validar_gcc_actualizado
from src.validacion.scheduler import schedule_task
from src.extraccion.cartera import extraer_cartera
from src.transformacion.elegibles import filtrar_elegibles
from src.transformacion.calculo import run_calculos
from src.generacion.taylor import run_taylor
from src.generacion.detallado import run_detallado
from src.utils.helpers import extraer_tipos,print_step
from src.extraccion.exepcions import extrac_excepcions,extract_estados_fallecidos,extract_asignacion
from src.utils import excepciones

import warnings
warnings.filterwarnings('ignore')

def main():
    
    # -- Se cargan las variables de entorno -- #
    load_dotenv()
    
    # -- Se carga la configuración desde el archivo config.yaml -- #
    cfg = load_config()
    
    try:
        print_step("[1/10] Validando actualización DW GCC...")
        validar_gcc_actualizado(val_gcc=cfg["queries"]["validacion_actualizacion"])

        print_step("[2/10] Determinando corte programado...")
        schedule_result = schedule_task()
        corte = schedule_result["tasks_to_run"][0]

        if corte["codigo_corte"][-2:] == "30":
            _dt = datetime.datetime.strptime(corte["periodo"], "%Y-%m")
            _next = _dt.replace(month=_dt.month + 1) if _dt.month < 12 else _dt.replace(year=_dt.year + 1, month=1)
            periodo_efectivo = _next.strftime("%Y-%m")
        else:
            periodo_efectivo = corte["periodo"]

        print(f"Corte: {corte['codigo_corte']} | Período: {periodo_efectivo} | Fecha: {corte['fecha_proceso']}")

        tipos = extraer_tipos()

        print_step("[3/10] Extrayendo cartera vencida...")
        extraer_cartera(fecha_proceso=corte["fecha_proceso"],
                        periodo=periodo_efectivo,
                        tipos=tipos
                        )

        print_step("[4/10] Extrayendo excepciones...")
        extrac_excepcions(exp_path=cfg["paths"]["juridicos_insolvencias"],
                          fecha_proceso=corte["fecha_proceso"],
                          periodo=periodo_efectivo
                          )
        print_step("[5/10] Extrayendo fallecidos...")
        extract_estados_fallecidos(query_path=cfg["queries"]["Fallecidos"],
                                   fecha_proceso=corte["fecha_proceso"],
                                   periodo=periodo_efectivo
                                   )
        print_step("[6/10] Extrayendo Asignacion...")
        extract_asignacion(asignacion_path=cfg["paths"]["asignacion"], 
                           fecha_proceso=corte["fecha_proceso"], 
                           periodo=periodo_efectivo
                            )

        print_step("[7/10] Filtrando elegibles...")
        df_elegibles = filtrar_elegibles(periodo=periodo_efectivo,
                                         fecha_proceso=corte["fecha_proceso"],
                                         cfg=cfg,
                                         schedule_result=schedule_result
                                         )
        
        print_step("[8/10] Calculando gastos por cobranza...")
        df_calculo = run_calculos(periodo=periodo_efectivo,
                                  fecha_proceso=corte["fecha_proceso"],
                                  schedule_result=schedule_result,
                                  df_elegibles=df_elegibles
                                  )
        
        print_step("[9/10] Proceso Salida Taylor...")
        run_taylor(df_calculado=df_calculo,
                   periodo=periodo_efectivo,
                   fecha_proceso=corte["fecha_proceso"],
                   cfg=cfg
                   )
        
        print_step("[10/10] Consolidando histórico detallado...")
        run_detallado(periodo=periodo_efectivo,
                      cfg=cfg)
        ancho = 50
        print(f"\n{'=' * ancho}")
        print(f"  PROCESO COMPLETADO EXITOSAMENTE")
        print(f"  Corte  : {corte['codigo_corte']}")
        print(f"  Período: {periodo_efectivo}")
        print(f"  Fecha  : {corte['fecha_proceso']}")
        print(f"{'=' * ancho}\n")

    except excepciones.GCCNoActualizadoError as e:
        print(f"Error de actualización: {e}")
        print("Se detiene el proceso.")
        sys.exit(1)
    except excepciones.GCCConexionError as e:
        print(f"Error de conexión: {e}")
        print("Se detiene el proceso.")
        sys.exit(1)
    except excepciones.CorteNoProgramadoError as e:
        print(f"Error de programación: {e}")
        print("Se detiene el proceso.")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Archivo no encontrado: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error de validación: {e}")
        sys.exit(1)
    except excepciones.TipoNoCompatible as e:
        print(f"Error de tipos de datos: {e}")
        sys.exit(1)
    except excepciones.ColumnasFaltantes as e:
        print(f"Error de columnas: {e}")
    except excepciones.ErrorExportandoArchivo as e:
        print(f"Error Exportando Archivo: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()