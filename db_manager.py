import sqlite3
import mysql.connector

class DatabaseManager:
    def __init__(self, config):
        self.config = config

    def save_local_sqlite(self, payload):
        """Guarda siempre en el archivo local de la Mini PC."""
        try:
            conn = sqlite3.connect('gateway_history.db')
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS historico (timestamp DATETIME, nodo TEXT, tag TEXT, valor TEXT)")
            for nodo in payload['nodos']:
                for tag in nodo['tags']:
                    cursor.execute("INSERT INTO historico (timestamp, nodo, tag, valor) VALUES (?, ?, ?, ?)",
                                 (payload['timestamp'], nodo['nombre'], tag['tag'], str(tag['valor'])))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error SQLite Local: {e}")

    def save_remote_db(self, payload):
        """Guarda en el servidor del cliente (MySQL o SQL Server)."""
        tipo = self.config.get('type', 'MySQL')
        
        if tipo == "MySQL":
            try:
                conn = mysql.connector.connect(
                    host=self.config.get('host'),
                    user=self.config.get('user'),
                    password=self.config.get('pass'),
                    database=self.config.get('db_name', 'gateway_history')
                )
                cursor = conn.cursor()
                for nodo in payload['nodos']:
                    for tag in nodo['tags']:
                        cursor.execute("INSERT INTO historico (ts, nodo, tag, val) VALUES (%s, %s, %s, %s)",
                                     (payload['timestamp'], nodo['nombre'], tag['tag'], str(tag['valor'])))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Error BD Remota: {e}")
        # Aquí puedes añadir el elif para "SQL Server" más adelante si lo necesitas