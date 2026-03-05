import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import datetime #
import sqlite3
import requests
import time
import datetime
from config_manager import save_settings, load_settings
from plc_drivers import CommunicationEngine
from db_manager import DatabaseManager

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Industrial Gateway IoT 2100 ")
        self.root.geometry("1150x850")
        
        self.config = load_settings()
        self.engine = CommunicationEngine()
        # Inicializamos con la config guardada o valores base
        self.db_manager = DatabaseManager(self.config.get('db_config', {}))
        
        self.running = False
        self.last_db_save = 0
        
        self.setup_ui()

    def setup_ui(self):
        # --- 1. CONFIGURACIÓN DE ALMACENAMIENTO Y CLOUD ---
        frame_db = ttk.LabelFrame(self.root, text="1. Configuración de Almacenamiento & Cloud", padding=10)
        frame_db.pack(fill="x", padx=10, pady=5)

        # Fila 0: Checkboxes y Credenciales Remotas
        self.en_local = tk.BooleanVar(value=self.config.get('en_local', True))
        ttk.Checkbutton(frame_db, text="Guardar Local (SQLite)", variable=self.en_local).grid(row=0, column=0, padx=5, sticky="w")

        self.en_remote = tk.BooleanVar(value=self.config.get('en_remote', False))
        ttk.Checkbutton(frame_db, text="Activar BD Remota:", variable=self.en_remote).grid(row=0, column=1, padx=5, sticky="w")

        self.db_type = ttk.Combobox(frame_db, values=["MySQL", "SQL Server"], width=8)
        self.db_type.set(self.config.get('db_config', {}).get('type', 'MySQL'))
        self.db_type.grid(row=0, column=2, padx=2)

        ttk.Label(frame_db, text="Host:").grid(row=0, column=3, padx=2)
        self.db_host = ttk.Entry(frame_db, width=12)
        self.db_host.insert(0, self.config.get('db_config', {}).get('host', 'localhost'))
        self.db_host.grid(row=0, column=4, padx=2)

        ttk.Label(frame_db, text="User:").grid(row=0, column=5, padx=2)
        self.db_user = ttk.Entry(frame_db, width=8)
        self.db_user.insert(0, self.config.get('db_config', {}).get('user', ''))
        self.db_user.grid(row=0, column=6, padx=2)

        ttk.Label(frame_db, text="Pass:").grid(row=0, column=7, padx=2)
        self.db_pass = ttk.Entry(frame_db, show="*", width=8)
        self.db_pass.insert(0, self.config.get('db_config', {}).get('pass', ''))
        self.db_pass.grid(row=0, column=8, padx=2)

        ttk.Label(frame_db, text="Intervalo (s):").grid(row=0, column=9, padx=2)
        self.db_int = ttk.Entry(frame_db, width=4)
        self.db_int.insert(0, self.config.get('db_config', {}).get('intervalo', 5))
        self.db_int.grid(row=0, column=10, padx=5)

        # Fila 1: Cloud y Nomenclatura (Planta / Línea)
        ttk.Label(frame_db, text="URL Cloud:").grid(row=1, column=0, sticky="e", pady=10)
        self.cloud_url = ttk.Entry(frame_db, width=35)
        self.cloud_url.insert(0, self.config.get('cloud_url', 'https://server-py-8ijq.onrender.com/v1/telemetria'))
        self.cloud_url.grid(row=1, column=1, columnspan=3, sticky="we", padx=5)

        ttk.Label(frame_db, text="Planta:").grid(row=1, column=4, sticky="e")
        self.plant_id = ttk.Entry(frame_db, width=6)
        self.plant_id.insert(0, self.config.get('plant_id', 'SMI'))
        self.plant_id.grid(row=1, column=5, padx=2)

        ttk.Label(frame_db, text="Línea:").grid(row=1, column=6, sticky="e")
        self.line_id = ttk.Entry(frame_db, width=6)
        self.line_id.insert(0, self.config.get('line_id', 'L32'))
        self.line_id.grid(row=1, column=7, padx=2)

        ttk.Button(frame_db, text="Guardar Todo", command=self.update_db_settings).grid(row=1, column=10, padx=10)

        # --- 2. CONFIGURACIÓN DE DISPOSITIVO (NODO) ---
        frame_node = ttk.LabelFrame(self.root, text="2. Agregar Dispositivo (Nodo)", padding=10)
        frame_node.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_node, text="Nombre:").grid(row=0, column=0)
        self.node_name = ttk.Entry(frame_node, width=12); self.node_name.grid(row=0, column=1, padx=5)
        
        ttk.Label(frame_node, text="IP:").grid(row=0, column=2)
        self.node_ip = ttk.Entry(frame_node, width=12); self.node_ip.grid(row=0, column=3, padx=5)

        ttk.Label(frame_node, text="Protocolo:").grid(row=0, column=4)
        self.node_proto = ttk.Combobox(frame_node, values=["S7", "Modbus"], width=8); self.node_proto.set("S7"); self.node_proto.grid(row=0, column=5, padx=5)

        self.lbl_rs = ttk.Label(frame_node, text="R/S:")
        self.lbl_rs.grid(row=0, column=6)
        self.node_rack = ttk.Entry(frame_node, width=2); self.node_rack.insert(0,"0"); self.node_rack.grid(row=0, column=7)
        self.node_slot = ttk.Entry(frame_node, width=2); self.node_slot.insert(0,"1"); self.node_slot.grid(row=0, column=8, padx=2)

        ttk.Button(frame_node, text="Añadir Nodo", command=self.add_node).grid(row=0, column=9, padx=10)

        # --- 3. CONFIGURACIÓN DE VARIABLES (TAGS) ---
        frame_tag = ttk.LabelFrame(self.root, text="3. Configurar Variables por Nodo", padding=10)
        frame_tag.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_tag, text="Seleccionar Nodo:").grid(row=0, column=0)
        self.cb_sel_node = ttk.Combobox(frame_tag, values=[n['name'] for n in self.config.get('nodos', [])], width=15)
        self.cb_sel_node.grid(row=0, column=1, padx=5)

        ttk.Label(frame_tag, text="Función:").grid(row=0, column=2)
        self.tag_func = ttk.Combobox(frame_tag, values=["Coils (0X)", "Discrete Inputs (1X)", "Input Registers (3X)", "Holding Registers (4X)"], width=20)
        self.tag_func.set("Holding Registers (4X)"); self.tag_func.grid(row=0, column=3, padx=5)

        ttk.Label(frame_tag, text="Tag:").grid(row=1, column=0)
        self.tag_name = ttk.Entry(frame_tag, width=12); self.tag_name.grid(row=1, column=1, padx=5)
        
        ttk.Label(frame_tag, text="DB/Reg:").grid(row=1, column=2)
        self.tag_db = ttk.Entry(frame_tag, width=4); self.tag_db.grid(row=1, column=3)
        self.tag_off = ttk.Entry(frame_tag, width=4); self.tag_off.grid(row=1, column=4, padx=2)

        ttk.Label(frame_tag, text="Tipo:").grid(row=1, column=5)
        self.tag_type = ttk.Combobox(frame_tag, values=["Real", "Int", "Bool", "DInt", "Time"], width=6); self.tag_type.set("Int"); self.tag_type.grid(row=1, column=6, padx=5)

        ttk.Button(frame_tag, text="Añadir Variable", command=self.add_tag).grid(row=1, column=7, padx=10)

        # Botones de Edición
        ttk.Button(frame_tag, text="Cargar Edición", command=self.load_tag).grid(row=1, column=8, padx=5)
        ttk.Button(frame_tag, text="Actualizar", command=self.update_tag).grid(row=1, column=9, padx=5)
        ttk.Button(frame_tag, text="Eliminar", command=self.delete_tag).grid(row=1, column=10, padx=5)

        # --- MONITOR ---
        self.btn_main = ttk.Button(self.root, text="INICIAR MONITOR MULTI-NODO", command=self.toggle_all)
        self.btn_main.pack(pady=10)

        self.tree = ttk.Treeview(self.root, columns=("nodo", "tag", "addr", "type", "val"), show="headings")
        for col in ["nodo", "tag", "addr", "type", "val"]: self.tree.heading(col, text=col.capitalize())
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.load_tree_data()

    def update_db_settings(self):
        # Guardamos el estado de las casillas check
        self.config['en_local'] = self.en_local.get()
        self.config['en_remote'] = self.en_remote.get()
        
        self.config['db_config'] = {
            "type": self.db_type.get(),
            "host": self.db_host.get(),
            "user": self.db_user.get(),
            "pass": self.db_pass.get(),
            "db_name": "gateway_history",
            "intervalo": int(self.db_int.get())
        }
        # --- AQUÍ GUARDAMOS EL ID DE PLANTA Y LA URL ---
        self.config['cloud_url'] = self.cloud_url.get()
        self.config['plant_id'] = self.plant_id.get().upper().strip()
        self.config['line_id'] = self.line_id.get().upper().strip()
        
        save_settings(self.config)
        self.db_manager = DatabaseManager(self.config['db_config'])
        messagebox.showinfo("OK", "Configuración de Base de Datos y Cloud guardada")
    def add_node(self):
        node = {"name": self.node_name.get(), "ip": self.node_ip.get(), "protocol": self.node_proto.get(), 
                "rack": self.node_rack.get(), "slot": self.node_slot.get(), "tags": []}
        self.config['nodos'].append(node)
        save_settings(self.config)
        self.cb_sel_node.config(values=[n['name'] for n in self.config['nodos']])
        messagebox.showinfo("OK", f"Nodo {node['name']} añadido")

    def format_time_ms(self, ms_val):
        """Convierte un valor de milisegundos a formato HH:MM:SS"""
        try:
            ms_int = int(ms_val)
            segundos = ms_int // 1000
            minutos, segundos = divmod(segundos, 60)
            horas, minutos = divmod(minutos, 60)
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
        
        except (ValueError, TypeError):
            return "00:00:00"

    def add_tag(self):
        node_target = self.cb_sel_node.get()
        for n in self.config['nodos']:
            if n['name'] == node_target:
                tag = {"name": self.tag_name.get(), "func": self.tag_func.get(), 
                       "db": self.tag_db.get(), "offset": self.tag_off.get(), "type": self.tag_type.get()}
                n['tags'].append(tag)
                save_settings(self.config)
                self.load_tree_data()
                return
    
    def load_tag(self):
        # 1. Verificamos que el usuario haya seleccionado algo en la tabla
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona una variable de la tabla inferior para editar.")
            return
        
        # 2. Obtenemos los datos de la fila seleccionada
        item = self.tree.item(selected[0])
        nodo_nombre = item['values'][0]
        tag_nombre = item['values'][1]
        
        # 3. Buscamos esos datos en nuestra configuración y llenamos las casillas
        for n in self.config['nodos']:
            if n['name'] == nodo_nombre:
                for t in n['tags']:
                    if t['name'] == tag_nombre:
                        self.cb_sel_node.set(n['name'])
                        self.tag_func.set(t.get('func', 'Holding Registers (4X)'))
                        
                        self.tag_name.delete(0, tk.END)
                        self.tag_name.insert(0, t['name'])
                        
                        self.tag_db.delete(0, tk.END)
                        self.tag_db.insert(0, t.get('db', ''))
                        
                        self.tag_off.delete(0, tk.END)
                        self.tag_off.insert(0, t['offset'])
                        
                        self.tag_type.set(t['type'])
                        
                        # Guardamos una referencia oculta para saber a quién estamos editando
                        self.editing_node = nodo_nombre
                        self.editing_tag = tag_nombre
                        return

    def update_tag(self):
        # Verificamos si primero cargaron una variable
        if hasattr(self, 'editing_tag') and hasattr(self, 'editing_node'):
            for n in self.config['nodos']:
                if n['name'] == self.editing_node:
                    for t in n['tags']:
                        if t['name'] == self.editing_tag:
                            # Reemplazamos los datos viejos con los nuevos de las casillas
                            t['name'] = self.tag_name.get()
                            t['func'] = self.tag_func.get()
                            t['db'] = self.tag_db.get()
                            t['offset'] = self.tag_off.get()
                            t['type'] = self.tag_type.get()
                            
                            save_settings(self.config)
                            self.load_tree_data()
                            messagebox.showinfo("OK", "Variable actualizada correctamente.")
                            
                            # Limpiamos la referencia
                            del self.editing_node
                            del self.editing_tag
                            return
        else:
            messagebox.showwarning("Aviso", "Primero selecciona una variable en la tabla y presiona 'Cargar Edición'.")

    def delete_tag(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona una variable de la tabla para eliminar.")
            return
        
        # Pedimos confirmación para evitar borrados accidentales
        if not messagebox.askyesno("Confirmar", "¿Seguro que deseas eliminar esta variable?"):
            return

        item = self.tree.item(selected[0])
        nodo_nombre = item['values'][0]
        tag_nombre = item['values'][1]
        
        for n in self.config['nodos']:
            if n['name'] == nodo_nombre:
                # Reconstruimos la lista omitiendo la variable que queremos borrar
                n['tags'] = [t for t in n['tags'] if t['name'] != tag_nombre]
                break
                
        save_settings(self.config)
        self.load_tree_data()
        messagebox.showinfo("OK", "Variable eliminada.")

    def send_to_cloud(self, payload):
        url = "https://server-py-8ijq.onrender.com/v1/telemetria"
        try:
            # Timeout de 5s para no bloquear el monitoreo de los PLC
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                print("Nube: Datos enviados con éxito")
        except Exception as e:
            print(f"Nube: Error de conexión {e}")
    
    def load_tree_data(self):
        self.tree.delete(*self.tree.get_children())
        for n in self.config.get('nodos', []):
            for t in n.get('tags', []):
                iid = f"{n['name']}_{t['name']}"
                addr = f"DB{t['db']}.{t['offset']}" if n['protocol'] == "S7" else f"R {t['offset']}"
                self.tree.insert("", "end", iid=iid, values=(n['name'], t['name'], addr, t['type'], "---"))

    def toggle_all(self):
        if not self.running:
            self.engine.connect_all(self.config['nodos'])
            self.running = True
            self.btn_main.config(text="DETENER MONITOR")
            threading.Thread(target=self.main_loop, daemon=True).start()
        else:
            self.running = False
            self.engine.disconnect_all()
            self.btn_main.config(text="INICIAR MONITOR")

    def main_loop(self):
        while self.running:
            payload = {"timestamp": datetime.datetime.now().isoformat(), "nodos": []}

            # --- 1. OBTENER EL ID DE LA PLANTA ---
            planta = self.config.get('plant_id', 'SMI').upper()
            linea = self.config.get('line_id', 'L01').upper()

            for n in self.config['nodos']:
                nodo_data = {"nombre": n['name'], "tags": []}

                # --- 2. LIMPIAR EL NOMBRE DEL NODO (Espacios a guiones) ---
                nodo_limpio = n['name'].replace(" ", "_").upper()

                for t in n['tags']:
                    val = self.engine.read_tag(n['name'], n['protocol'], t)

                    if t.get('type') == 'Time':
                        val = self.format_time_ms(val)
                        
                    self.root.after(0, lambda i=f"{n['name']}_{t['name']}", v=val: self.tree.set(i, "val", v))
                    # --- 3. CREAR EL TAG FORMATEADO (Ej: SMI_SOPLADO_PRESION) ---
                    var_limpia = t['name'].replace(" ", "_").upper()
                    tag_formateado = f"{planta}_{linea}_{nodo_limpio}_{var_limpia}"
                    
                    # Lo guardamos en el JSON
                    nodo_data["tags"].append({"tag": tag_formateado, "valor": val})
                payload["nodos"].append(nodo_data)
            
            # Guardado según intervalo configurado
            curr = time.time()
            if curr - self.last_db_save >= int(self.config['db_config'].get('intervalo', 5)):
                # 1. ¿Marcó guardar en la Mini PC?
                if self.config.get('en_local', True):
                    threading.Thread(target=self.db_manager.save_local_sqlite, args=(payload,), daemon=True).start()
                
                # 2. ¿Marcó activar Base de Datos Remota (MySQL)?
                if self.config.get('en_remote', False):
                    threading.Thread(target=self.db_manager.save_remote_db, args=(payload,), daemon=True).start()
                
                # 3. ¿Escribió una URL para la Nube? (Si está vacío, no envía el POST)
                url_actual = self.config.get('cloud_url', '')
                if url_actual != "":
                    threading.Thread(target=self.send_to_cloud, args=(payload,), daemon=True).start()
                
                self.last_db_save = curr
            time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk(); app = MainApp(root); root.mainloop()