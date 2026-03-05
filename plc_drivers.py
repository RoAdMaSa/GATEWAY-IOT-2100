import snap7
from pyModbusTCP.client import ModbusClient
from snap7.util import *
import struct

class CommunicationEngine:
    def __init__(self):
        self.connections = {}
        self.node_configs = {}

    def connect_all(self, nodos):
        self.node_configs = {n['name']: n for n in nodos}
        results = {}
        for nodo in nodos:
            results[nodo['name']] = self._attempt_connect(nodo)
        return results

    def _attempt_connect(self, nodo):
        name = nodo['name']
        
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
                return True
            else:
                client = ModbusClient(host=nodo['ip'], port=502, auto_open=True, timeout=2)
                if client.open():
                    self.connections[name] = client
                    return True
                return False
        except:
            return False

    def read_tag(self, nodo_name, protocol, tag):
        client = self.connections.get(nodo_name)
        
        # Si el cliente es None (porque está desconectado), reintentamos conectar
        if not client:
            self._attempt_connect(self.node_configs.get(nodo_name, {}))
            return "Reconnecting..."

        try:
            dtype = tag.get('type', 'Int')
            offset = int(tag['offset'])

            if protocol == "S7":
                size_map = {"Real": 4, "Int": 2, "Bool": 1, "DInt": 4, "Time": 4}
                try:
                    # Intentamos leer la memoria del PLC
                    raw = client.db_read(int(tag['db']), offset, size_map[dtype])
                except Exception as e:
                    # Si falla (ej. se quitó el cable), el socket se rompió.
                    # Forzamos destrucción del cliente viejo para que reinicie
                    self._attempt_connect(self.node_configs[nodo_name])
                    return "Reconnecting..."

                if dtype == "Real": return round(get_real(raw, 0), 2)
                if dtype == "Int": return get_int(raw, 0)
                if dtype == "Bool": return get_bool(raw, 0, 0)
                return get_dint(raw, 0)
            
            else: # MODBUS TCP
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
                    # Si Modbus falla, forzamos reconexión destruyendo el cliente
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