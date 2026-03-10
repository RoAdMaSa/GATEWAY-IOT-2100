import sqlite3
import mysql.connector
import pyodbc # Importante para SQL Server
import psycopg2
import logging

class DatabaseManager:
    def __init__(self, config):
        self.config = config
        # Diccionario para recordar si la BD estaba viva o muerta en el ciclo anterior
        self.last_status = {"local": True, "remote": True}
    
    def log_db_status(self, db_type, is_ok, error_msg=""):
        current = self.last_status[db_type]
        if current == is_ok: 
            self.last_status[db_type] = is_ok
            if is_ok:
                logging.info(f"[OK BD] Conexión recuperada con Base de Datos {db_type.upper()}")
                print(f"[OK BD] Conexión recuperada con {db_type.upper()}")
            else:
                logging.error(f"[ERROR BD] Fallo en Base de Datos {db_type.upper()}: {error_msg}")
                print(f"[ERROR BD] Fallo en {db_type.upper()}: {error_msg}")

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
            self.log_db_status("local", True)
        except Exception as e:
            print(f"Error SQLite Local: {e}")
            self.log_db_status("local", False, str(e))

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
                        cursor.execute("INSERT INTO historico (timestamp, nodo, tag, val) VALUES (%s, %s, %s, %s)",
                                     (payload['timestamp'], nodo['nombre'], tag['tag'], str(tag['valor'])))
                conn.commit()
                conn.close()
                self.log_db_status("local", True)
            except Exception as e:
                print(f"Error MySQL Remota: {e}")
                self.log_db_status("local", False, str(e))

        # --- NUEVA LÓGICA PARA SQL SERVER ---
        elif tipo == "SQL Server":
            try:
                # Se arma la cadena de conexión típica de SQL Server
                conn_str = (
                    r'DRIVER={ODBC Driver 17 for SQL Server};'
                    rf"SERVER={self.config.get('host')};"
                    rf"DATABASE={self.config.get('db_name', 'GATEWAY_HISTORY')};"
                    rf"UID={self.config.get('user')};"
                    rf"PWD={self.config.get('pass')}"
                )
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                
                # OJO: En SQL Server se usan los signos de interrogación (?) al igual que en SQLite
                for nodo in payload['nodos']:
                    for tag in nodo['tags']:
                        cursor.execute("INSERT INTO historico (timestamp, nodo, tag, val) VALUES (?, ?, ?, ?)",
                                     (payload['timestamp'], nodo['nombre'], tag['tag'], str(tag['valor'])))
                conn.commit()
                conn.close()
                self.log_db_status("local", True)
            except Exception as e:
                print(f"Error SQL Server Remoto: {e}")
                self.log_db_status("local", False, str(e))

        # --- LÓGICA PARA POSTGRESQL (NEON DB NUBE) ---
        elif tipo == "PostgreSQL":
            try:
                # Usamos los campos de tu interfaz visual, y forzamos el SSL y el nombre de BD
                conn = psycopg2.connect(
                    host=self.config.get('host'),
                    user=self.config.get('user'),
                    password=self.config.get('pass'),
                    database='gateway',  # <-- Nombre de tu BD en Neon
                    port=5432,
                    sslmode='require'    # <-- VITAL para que la nube (Neon/AWS) no te rechace
                )
                cursor = conn.cursor()
                
                # PostgreSQL usa %s igual que MySQL
                for nodo in payload['nodos']:
                    for tag in nodo['tags']:
                        cursor.execute("INSERT INTO historico (timestamp, nodo, tag, val) VALUES (%s, %s, %s, %s)",
                                     (payload['timestamp'], nodo['nombre'], tag['tag'], str(tag['valor'])))
                conn.commit()
                cursor.close()
                conn.close()
                self.log_db_status("local", True)
                print("Dato enviado a PostgreSQL en la nube correctamente")
            except Exception as e:
                print(f"Error PostgreSQL Remoto: {e}") 
                self.log_db_status("local", False, str(e))       