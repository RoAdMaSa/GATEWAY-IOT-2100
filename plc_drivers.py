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
        try:
            if nodo['protocol'] == "S7":
                client = snap7.client.Client()
                client.connect(nodo['ip'], int(nodo['rack']), int(nodo['slot']))
                self.connections[name] = client
                return client.get_connected()
            else:
                # auto_open=True ayuda, pero manejaremos el reintento manual para mayor control
                client = ModbusClient(host=nodo['ip'], port=502, auto_open=True, timeout=2)
                self.connections[name] = client
                return client.open() 
        except:
            return False

    def read_tag(self, nodo_name, protocol, tag):
        client = self.connections.get(nodo_name)
        if not client: return "No Config"

        try:
            dtype = tag.get('type', 'Int')
            offset = int(tag['offset'])

            if protocol == "S7":
                if not client.get_connected():
                    self._attempt_connect(self.node_configs[nodo_name])
                
                size_map = {"Real": 4, "Int": 2, "Bool": 1, "DInt": 4}
                raw = client.db_read(int(tag['db']), offset, size_map[dtype])
                if dtype == "Real": return round(get_real(raw, 0), 2)
                if dtype == "Int": return get_int(raw, 0)
                if dtype == "Bool": return get_bool(raw, 0, 0)
                return get_dint(raw, 0)
            
            else: # MODBUS TCP
                # Verificamos la propiedad is_open (sin paréntesis)
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

                # Si la lectura falla, cerramos para forzar reconexión en el siguiente ciclo
                if regs is None:
                    client.close()
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
        for c in self.connections.values():
            try:
                c.disconnect() if hasattr(c, 'disconnect') else c.close()
            except: pass
        self.connections = {}