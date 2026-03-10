import snap7
from pyModbusTCP.client import ModbusClient
from snap7.util import *
from notifier import send_telegram_alert # <-- NUEVO
import struct
import logging

class CommunicationEngine:
    def __init__(self):
        self.connections = {}
        self.node_configs = {}
        self.last_status = {} # Para recordar si el nodo estaba vivo o muerto en el ciclo anterior
    
    def log_plc_status(self, nodo_name, ip, is_ok, error_msg=""):
        current = self.last_status.get(nodo_name)
        if current != is_ok:
            self.last_status[nodo_name] = is_ok
            if is_ok:
                # Creamos el mensaje bonito de OK y lo enviamos
                msg = f"✅ *RECONEXIÓN EXITOSA*\nPLC: {nodo_name}\nIP: {ip}"
                logging.info(msg.replace('\n', ' - '))
                send_telegram_alert(msg) 
            else:
                # Creamos el mensaje bonito de ERROR y lo enviamos
                msg = f"🚨 *ALERTA DE DESCONEXIÓN*\nPLC: {nodo_name}\nIP: {ip}\nCausa: {error_msg}"
                logging.warning(msg.replace('\n', ' - '))
                send_telegram_alert(msg)

    def connect_all(self, nodos):
        self.node_configs = {n['name']: n for n in nodos}
        results = {}
        for nodo in nodos:
            results[nodo['name']] = self._attempt_connect(nodo)
        return results

    def _attempt_connect(self, nodo):
        name = nodo['name']
        ip = nodo['ip']

        # 1. DESTRUCCIÓN TOTAL DEL CLIENTE VIEJO
        # Si existe un cliente previo, lo destruimos y liberamos la memoria
        if name in self.connections and self.connections[name] is not None:
            try:
                c = self.connections[name]
                if hasattr(c, 'destroy'): # Es Siemens
                    c.disconnect()
                    c.destroy()
                else: # Es Modbus
                    c.close()
            except:
                pass
        
        # 2. MARCAMOS COMO DESCONECTADO (None)
        # Esto evita que se use un cliente roto en el futuro
        self.connections[name] = None

        # 3. INTENTAMOS CREAR UNO NUEVO
        try:
            if nodo['protocol'] == "S7":
                client = snap7.client.Client()
                # Si el cable está desconectado, fallará aquí y saltará al except
                client.connect(nodo['ip'], int(nodo['rack']), int(nodo['slot']))
                
                # Si conectó con éxito, lo guardamos
                self.connections[name] = client
                self.log_plc_status(name, ip, True) # <--- AQUÍ: CONEXIÓN EXITOSA S7
                return True
            else:
                client = ModbusClient(host=nodo['ip'], port=502, auto_open=True, timeout=2)
                if client.open():
                    self.connections[name] = client
                    self.log_plc_status(name, ip, True) # <--- AQUÍ: CONEXIÓN EXITOSA MODBUS
                    return True
                
                self.log_plc_status(name, ip, False, "Modbus rechazó la conexión") # <--- AQUÍ: FALLO MODBUS
                return False
        except:
            self.log_plc_status(name, ip, False, "Cable desconectado o equipo apagado") # <--- AQUÍ: FALLO S7 O CABLE ROTO
            return False

    def read_tag(self, nodo_name, protocol, tag):
        client = self.connections.get(nodo_name)
        ip = self.node_configs.get(nodo_name, {}).get('ip', 'Desconocida') # Obtenemos la IP para el log
        
        # Si el cliente es None, reintentamos conectar
        if not client:
            self._attempt_connect(self.node_configs.get(nodo_name, {}))
            return "Reconnecting..."

        try:
            dtype = tag.get('type', 'Int')
            offset_str = str(tag['offset']) # Lo tratamos como texto para poder buscar el punto

            if protocol == "S7":
                # --- NUEVA LÓGICA DE BITS PARA BOOLEANOS ---
                if dtype == "Bool" and '.' in offset_str:
                    # Si escriben "8.2", lo partimos a la mitad
                    partes = offset_str.split('.')
                    byte_index = int(partes[0]) # 8
                    bit_index = int(partes[1])  # 2
                else:
                    # Para Int, Real, DInt o si escriben solo "8"
                    byte_index = int(float(offset_str))
                    bit_index = 0
                
                size_map = {"Real": 4, "Int": 2, "Bool": 1, "DInt": 4, "Time": 4}
                try:
                    # Leemos la memoria usando el byte_index que calculamos
                    raw = client.db_read(int(tag['db']), byte_index, size_map[dtype])
                except Exception as e:
                    self.log_plc_status(nodo_name, ip, False, "Se perdió la conexión durante la lectura S7") # <--- AQUÍ: CAÍDA EN VIVO S7
                    self._attempt_connect(self.node_configs[nodo_name])
                    return "Reconnecting..."

                if dtype == "Real": return round(get_real(raw, 0), 2)
                if dtype == "Int": return get_int(raw, 0)
                if dtype == "Bool": return get_bool(raw, 0, bit_index) # <-- ¡AQUÍ INYECTAMOS EL BIT!
                return get_dint(raw, 0)
            
            else: # MODBUS TCP
                # Modbus no usa bits decimales, convertimos a entero normal
                offset = int(float(offset_str)) 
                
                if not client.is_open:
                    client.open()
                
                func = tag.get('func', 'Holding Registers (4X)')
                regs = None
                
                if "Coils" in func:
                    regs = client.read_coils(offset, 1)
                elif "Discrete" in func:
                    regs = client.read_discrete_inputs(offset, 1)
                elif "Input Registers" in func:
                    num = 2 if dtype in ["Real", "DInt"] else 1
                    regs = client.read_input_registers(offset, num)
                else: # Holding Registers (4X)
                    num = 2 if dtype in ["Real", "DInt"] else 1
                    regs = client.read_holding_registers(offset, num)

                if regs is None:
                    self.log_plc_status(nodo_name, ip, False, "Se perdió la conexión durante la lectura Modbus") # <--- AQUÍ: CAÍDA EN VIVO MODBUS
                    self._attempt_connect(self.node_configs[nodo_name])
                    return "Reconnecting..."
                
                return self._parse_modbus(regs, dtype)

        except Exception:
            return "Error"

    def _parse_modbus(self, regs, dtype):
        if not regs: return "Err"
        if dtype == "Int" or dtype == "Bool": return regs[0]
        if dtype == "Real" and len(regs) >= 2:
            raw = struct.pack('>HH', regs[0], regs[1])
            return round(struct.unpack('>f', raw)[0], 2)
        return regs[0]

    def disconnect_all(self):
        for name, c in self.connections.items():
            if c is not None:
                try:
                    if hasattr(c, 'destroy'):
                        c.disconnect()
                        c.destroy() 
                    else:
                        c.close()
                except: pass
        self.connections = {}