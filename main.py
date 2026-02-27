import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import sqlite3  # Base de datos local incluida en Python
import requests
from config_manager import save_settings, load_settings
from plc_drivers import CommunicationEngine

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Industrial Multi-Node Gateway - Rommel Adrian")
        self.root.geometry("1050x750")
        
        self.config = load_settings()
        self.engine = CommunicationEngine()
        self.running = False
        
        # Inicializamos la base de datos SQL antes de cargar la UI
        self.init_db()
        self.setup_ui()

    def init_db(self):
        """Inicializa el archivo de base de datos y la tabla de histórico."""
        try:
            conn = sqlite3.connect('gateway_history.db')
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS historico 
                              (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                               nodo TEXT, tag TEXT, valor TEXT)''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error inicializando SQL: {e}")

    def save_to_sql(self, nodo, tag, valor):
        """Guarda una lectura individual en la base de datos."""
        # No guardamos estados de error o reconexión para no ensuciar el histórico
        if valor in ["Error", "Reconnecting...", "No Conn", "Err", "Err Read"]:
            return
            
        try:
            conn = sqlite3.connect('gateway_history.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO historico (nodo, tag, valor) VALUES (?, ?, ?)", 
                           (nodo, tag, str(valor)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error al insertar en SQL: {e}")

    def setup_ui(self):
        # --- 1. CONFIGURACIÓN DE NODO ---
        frame_node = ttk.LabelFrame(self.root, text="1. Configurar Dispositivo (Nodo)", padding=10)
        frame_node.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_node, text="Nombre:").grid(row=0, column=0)
        self.node_name = ttk.Entry(frame_node, width=12); self.node_name.grid(row=0, column=1, padx=5)
        
        ttk.Label(frame_node, text="IP:").grid(row=0, column=2)
        self.node_ip = ttk.Entry(frame_node, width=12); self.node_ip.grid(row=0, column=3, padx=5)

        ttk.Label(frame_node, text="Protocolo:").grid(row=0, column=4)
        self.node_proto = ttk.Combobox(frame_node, values=["S7", "Modbus"], width=8)
        self.node_proto.set("S7"); self.node_proto.grid(row=0, column=5, padx=5)
        self.node_proto.bind("<<ComboboxSelected>>", self.toggle_node_fields)

        self.lbl_rs = ttk.Label(frame_node, text="R/S:")
        self.lbl_rs.grid(row=0, column=6)
        self.node_rack = ttk.Entry(frame_node, width=2); self.node_rack.insert(0,"0"); self.node_rack.grid(row=0, column=7)
        self.node_slot = ttk.Entry(frame_node, width=2); self.node_slot.insert(0,"1"); self.node_slot.grid(row=0, column=8, padx=2)

        ttk.Button(frame_node, text="Añadir Nodo", command=self.add_node).grid(row=0, column=9, padx=10)

        # --- 2. CONFIGURACIÓN DE VARIABLES ---
        frame_tag = ttk.LabelFrame(self.root, text="2. Configurar Variables (Tags)", padding=10)
        frame_tag.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_tag, text="Nodo:").grid(row=0, column=0)
        self.cb_sel_node = ttk.Combobox(frame_tag, values=[n['name'] for n in self.config.get('nodos', [])], width=12)
        self.cb_sel_node.grid(row=0, column=1, padx=5)
        self.cb_sel_node.bind("<<ComboboxSelected>>", self.toggle_tag_fields)

        ttk.Label(frame_tag, text="Función:").grid(row=0, column=2)
        self.tag_func = ttk.Combobox(frame_tag, values=[
            "Coils (0X)", 
            "Discrete Inputs (1X)", 
            "Input Registers (3X)", 
            "Holding Registers (4X)"
        ], width=20)
        self.tag_func.set("Holding Registers (4X)")
        self.tag_func.grid(row=0, column=3, padx=5)

        ttk.Label(frame_tag, text="Nombre:").grid(row=1, column=0)
        self.tag_name = ttk.Entry(frame_tag, width=12); self.tag_name.grid(row=1, column=1, padx=5)
        
        self.lbl_db = ttk.Label(frame_tag, text="DB:"); self.lbl_db.grid(row=1, column=2)
        self.tag_db = ttk.Entry(frame_tag, width=4); self.tag_db.grid(row=1, column=3)
        
        self.lbl_off = ttk.Label(frame_tag, text="Offset/Reg:"); self.lbl_off.grid(row=1, column=4)
        self.tag_off = ttk.Entry(frame_tag, width=4); self.tag_off.grid(row=1, column=5)

        ttk.Label(frame_tag, text="Tipo:").grid(row=1, column=6)
        self.tag_type = ttk.Combobox(frame_tag, values=["Real", "Int", "Bool", "DInt"], width=6)
        self.tag_type.set("Int"); self.tag_type.grid(row=1, column=7, padx=5)

        ttk.Button(frame_tag, text="Añadir Variable", command=self.add_tag).grid(row=1, column=8, padx=5)

        # --- MONITOR ---
        self.btn_main = ttk.Button(self.root, text="INICIAR MONITOR MULTI-NODO", command=self.toggle_all)
        self.btn_main.pack(pady=10)

        self.tree = ttk.Treeview(self.root, columns=("nodo", "tag", "addr", "type", "val"), show="headings")
        self.tree.heading("nodo", text="Nodo"); self.tree.heading("tag", text="Variable")
        self.tree.heading("addr", text="Dirección"); self.tree.heading("type", text="Tipo"); self.tree.heading("val", text="Valor")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.load_tree_data()

    def send_to_cloud(self, data_json):
        """Envía el paquete de datos al servidor del cliente."""
        # IP de la PC donde corre el script de FastAPI
        url = "http://127.0.0.1:8000/v1/telemetria" 
        headers = {'Content-Type': 'application/json'}
        
        try:
            # Enviamos el JSON. El timeout es vital para que no se quede colgado
            response = requests.post(url, json=data_json, headers=headers, timeout=2)
            if response.status_code == 200:
                print("Nube: Datos enviados correctamente")
            else:
                print(f"Nube: Error del servidor {response.status_code}")
        except Exception as e:
            print(f"Nube: Error de conexión: {e}")

    def toggle_node_fields(self, event=None):
        state = "normal" if self.node_proto.get() == "S7" else "disabled"
        self.node_rack.config(state=state); self.node_slot.config(state=state)

    def toggle_tag_fields(self, event=None):
        node_name = self.cb_sel_node.get()
        node = next((n for n in self.config['nodos'] if n['name'] == node_name), None)
        if node:
            if node['protocol'] == "Modbus":
                self.tag_db.config(state="disabled")
                self.tag_func.config(state="normal")
            else:
                self.tag_db.config(state="normal")
                self.tag_func.config(state="disabled")

    def add_node(self):
        node = {
            "name": self.node_name.get(), "ip": self.node_ip.get(),
            "protocol": self.node_proto.get(), "rack": self.node_rack.get(),
            "slot": self.node_slot.get(), "tags": []
        }
        self.config['nodos'].append(node)
        save_settings(self.config)
        self.cb_sel_node.config(values=[n['name'] for n in self.config['nodos']])
        messagebox.showinfo("OK", f"Dispositivo {node['name']} añadido")

    def add_tag(self):
        node_target = self.cb_sel_node.get()
        for n in self.config['nodos']:
            if n['name'] == node_target:
                tag = {
                    "name": self.tag_name.get(),
                    "func": self.tag_func.get(),
                    "db": self.tag_db.get() if n['protocol'] == "S7" else "0",
                    "offset": self.tag_off.get(),
                    "type": self.tag_type.get()
                }
                n['tags'].append(tag)
                save_settings(self.config)
                self.load_tree_data()
                return

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
            self.btn_main.config(text="DETENER MONITOR (SQL ACTIVO)")
            threading.Thread(target=self.main_loop, daemon=True).start()
        else:
            self.running = False
            self.engine.disconnect_all()
            self.btn_main.config(text="INICIAR MONITOR MULTI-NODO")

    def main_loop(self):
        self.init_db()
        while self.running:
            # Preparamos el paquete JSON (Payload)
            payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "nodos": []
            }

            for n in self.config['nodos']:
                nodo_data = {"nombre": n['name'], "tags": []}
                for t in n['tags']:
                    # Leer valor real del PLC o Modbus
                    val = self.engine.read_tag(n['name'], n['protocol'], t)
                    
                    # 1. Actualizar la tabla visual
                    iid = f"{n['name']}_{t['name']}"
                    self.root.after(0, lambda i=iid, v=val: self.tree.set(i, "val", v))
                    
                    # 2. Guardar en tu SQL local (Respaldo/Backup)
                    self.save_to_sql(n['name'], t['name'], val)
                    
                    # 3. Meter datos al paquete para la nube
                    nodo_data["tags"].append({"tag": t['name'], "valor": val})
                
                payload["nodos"].append(nodo_data)
            
            # --- EL PASO CLAVE ---
            # Lanzamos el envío en un hilo separado para que el ciclo siga sin esperar
            threading.Thread(target=self.send_to_cloud, args=(payload,), daemon=True).start()
            
            time.sleep(1) # Pausa de 1 segundo antes de la siguiente lectura

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()