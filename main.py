import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import datetime
from config_manager import save_settings, load_settings
from plc_drivers import CommunicationEngine
from db_manager import DatabaseManager

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Industrial Multi-Node Gateway")
        self.root.geometry("1050x750")
        
        self.config = load_settings()
        self.engine = CommunicationEngine()
        self.running = False
        self.db_manager = DatabaseManager(self.config['db_config'])
        self.last_db_save = 0 # Para controlar el intervalo

    def setup_ui(self):
        # --- 1. CONFIGURACIÓN DE NODO ---
        frame_db = ttk.LabelFrame(self.root, text="Configuración de Almacenamiento & Cloud", padding=10)
        frame_db.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_db, text="Tipo:").grid(row=0, column=0)
        self.db_type = ttk.Combobox(frame_db, values=["SQLite", "MySQL"], width=10)
        self.db_type.set(self.config['db_config']['type'])
        self.db_type.grid(row=0, column=1)

        ttk.Label(frame_db, text="Host:").grid(row=0, column=2)
        self.db_host = ttk.Entry(frame_db, width=15)
        self.db_host.insert(0, self.config['db_config'].get('host', 'localhost'))
        self.db_host.grid(row=0, column=3)

        ttk.Label(frame_db, text="User:").grid(row=0, column=4)
        self.db_user = ttk.Entry(frame_db, width=10)
        self.db_user.insert(0, self.config['db_config'].get('user', ''))
        self.db_user.grid(row=0, column=5)

        ttk.Label(frame_db, text="Pass:").grid(row=0, column=6)
        self.db_pass = ttk.Entry(frame_db, show="*", width=10)
        self.db_pass.insert(0, self.config['db_config'].get('pass', ''))
        self.db_pass.grid(row=0, column=7)

        ttk.Label(frame_db, text="Intervalo (s):").grid(row=0, column=8)
        self.db_int = ttk.Entry(frame_db, width=5)
        self.db_int.insert(0, self.config['db_config'].get('intervalo', 5))
        self.db_int.grid(row=0, column=9)

        ttk.Button(frame_db, text="Guardar Config DB", command=self.update_db_config).grid(row=0, column=10, padx=5)

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

    def update_db_config(self):
        self.config['db_config'] = {
            "type": self.db_type.get(),
            "host": self.db_host.get(),
            "user": self.db_user.get(),
            "pass": self.db_pass.get(),
            "db_name": "gateway_history", # o el nombre que elijas
            "intervalo": int(self.db_int.get())
        }
        save_settings(self.config)
        self.db_manager = DatabaseManager(self.config['db_config'])
        messagebox.showinfo("Éxito", "Configuración de Base de Datos actualizada.")

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
            payload = {"timestamp": datetime.datetime.now().isoformat(), "nodos": []}

            for n in self.config['nodos']:
                nodo_res = {"nombre": n['name'], "tags": []}
                for t in n['tags']:
                    val = self.engine.read_tag(n['name'], n['protocol'], t)
                    self.root.after(0, lambda i=f"{n['name']}_{t['name']}", v=val: self.tree.set(i, "val", v))
                    nodo_res["tags"].append({"tag": t['name'], "valor": val})
                payload['nodos'].append(nodo_res)

            # Control de guardado por tiempo
            current_time = time.time()
            if current_time - self.last_db_save >= self.config['db_config']['intervalo']:
                threading.Thread(target=self.db_manager.save_data, args=(payload,), daemon=True).start()
                threading.Thread(target=self.send_to_cloud, args=(payload,), daemon=True).start()
                self.last_db_save = current_time
                
            time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()