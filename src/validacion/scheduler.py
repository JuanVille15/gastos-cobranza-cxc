import json
from pathlib import Path
from datetime import datetime
from src.utils.excepciones import CorteNoProgramadoError

# Scheduler function to manage the scheduling of tasks
def schedule_task() -> dict:
    
    """
    Lee un archivo de configuración JSON y retorna las tareas de corte programadas para el día actual.

    Lee el archivo `config/scheduler_corte.json`, compara la fecha de ejecución
    de cada tarea con la fecha actual y filtra las que correspondan al día de hoy.

    Returns:
        dict: Diccionario con la clave `tasks_to_run`, cuyo valor es una lista
              de tareas (dict) programadas para el día actual.

    Raises:
        FileNotFoundError: Si el archivo `config/scheduler_corte.json` no existe.
        CorteNoProgramadoError: Si no hay ningún corte programado para el día de hoy.

    Example:
        >>> result = schedule_task()
        >>> result
        {"tasks_to_run": [{"codigo_corte": "CORTE001", "periodo": "2024-01", "fecha_ejecucion": "2024-01-15"}]}
    """
    # Load the schedule from a JSON file
    schedule_corte_path = Path("config/scheduler_corte.json")
    if not schedule_corte_path.exists():
        raise FileNotFoundError(f"Schedule file not found: {schedule_corte_path}")

    with open(schedule_corte_path, "r") as f:
        schedule = json.load(f)

    # Get the current time
    now = datetime.now().strftime("%Y-%m-%d")

    # Check for tasks scheduled at the current time
    tasks_to_run = []
    for task in schedule.get("cortes", []):
        if str(task["fecha_proceso"]) == now:
            tasks_to_run.append(task)
            print(f"Tarea agendada para hoy: Corte {str(task['codigo_corte'])[6:]} - Periodo: {task['periodo']}")
    
    if not tasks_to_run:
        raise CorteNoProgramadoError(f"No se encontró un corte programado para el día de hoy: {now}")
        
    return {"tasks_to_run": tasks_to_run}