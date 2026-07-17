import yaml
import os
from pathlib import Path

def load_config() -> dict:
    """
    Carga la configuración desde un archivo YAML.

    Returns:
        dict: Un diccionario con la configuración cargada.
    """
    config_path = os.path.join(Path(__file__).parents[2],'config','config.yaml')
    
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    return config