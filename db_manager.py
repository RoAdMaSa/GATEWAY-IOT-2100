import sqlite3
import mysql.connector
import datetime

class DatabaseManager:
    def __init__(self, config):
        self.config = config

    def save_data(self, payload):
        db_type = self.config.get('type', 'SQLite')
        
        if db_type == "SQLite":
            self._save_sqlite(payload)
        elif db_type == "MySQL":
            self._save_mysql(payload)

    def _save_sqlite(self, payload):
        try:
            conn = sqlite3.connect(self.config.get('db_name', 'gateway.db'))
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS historico (ts TEXT, nodo TEXT, tag TEXT, val TEXT)")
            for nodo in payload['nodos']:
                for tag in nodo['tags']:
                    cursor.execute("INSERT INTO historico (ts, nodo, tag, val) VALUES (?, ?, ?, ?)",
                                 (payload['timestamp'], nodo['nombre'], tag['tag'], str(tag['valor'])))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error SQLite: {e}")

    def _save_mysql(self, payload):
        try:
            conn = mysql.connector.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['pass'],
                database=self.config['db_name']
            )
            cursor = conn.cursor()
            query = "INSERT INTO historico (ts, nodo, tag, val) VALUES (%s, %s, %s, %s)"
            for nodo in payload['nodos']:
                for tag in nodo['tags']:
                    cursor.execute(query, (payload['timestamp'], nodo['nombre'], tag['tag'], str(tag['valor'])))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error MySQL: {e}")