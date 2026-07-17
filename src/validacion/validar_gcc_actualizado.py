from src.conexion.gcc_client import ejecutar_query
import datetime
from src.utils import excepciones

def validar_gcc_actualizado(val_gcc:str) -> None:
    
        ultima_actualizacion = ejecutar_query(val_gcc).iloc[0,0]
        
        if datetime.datetime.strptime(str(ultima_actualizacion),"%Y-%m-%d").date() == datetime.date.today():
            print("El DW GCC está actualizado al día de hoy.")
            print("Se da inicio al proceso")
        else:
            print(f"Fecha de última actualización:{ultima_actualizacion}")
            raise excepciones.GCCNoActualizadoError("El DW GCC no está actualizado al día de hoy.")