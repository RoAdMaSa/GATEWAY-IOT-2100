import json
import os

def save_settings(data, filename="settings.json"):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_settings(filename="settings.json"):
    # Si el archivo no existe o está vacío
    if not os.path.exists(filename) or os.stat(filename).st_size == 0:
        return {"nodos": [],
            "db_config": {
                "type": "SQLite",
                "host": "localhost",
                "user": "",
                "pass": "",
                "db_name": "gateway_history.db",
                "intervalo": 5  # Segundos por defecto}
            }
        }    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            # Si el archivo existe pero es de la versión vieja (no tiene 'nodos')
            if 'nodos' not in data or 'db_config' not in data:
                return {"nodos": [],
                    "db_config": {
                        "type": "SQLite",
                        "host": "localhost",
                        "user": "",
                        "pass": "",
                        "db_name": "gateway_history.db",
                        "intervalo": 5  # Segundos por defecto}
                    }
                }
            return data
    except (json.JSONDecodeError, KeyError):
        return {"nodos": [], "db_config": {}}