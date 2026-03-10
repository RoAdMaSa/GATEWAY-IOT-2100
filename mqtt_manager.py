import logging
from mqtt_spb_wrapper import MqttSpbEntityDevice

class MqttSparkplugManager:
    def __init__(self, config):
        self.config = config
        self.group_id = self.config.get('group_id', 'SMI_PLASTICS')
        self.edge_node_id = self.config.get('node_id', 'Gateway_L32')
        self.broker = self.config.get('broker', 'localhost')
        self.port = int(self.config.get('port', 1883))

        # Atrapamos credenciales (si están vacías, asume que no hay autenticación)
        self.user = self.config.get('user', '')
        self.password = self.config.get('pass', '')
        
        # Aquí guardaremos los objetos Sparkplug de cada PLC
        self.devices = {} 

    def connect(self):
        # La conexión se hará dinámicamente cuando lleguen los datos del PLC
        print("MQTT Sparkplug B: Inicializado. Esperando datos...")

    def disconnect(self):
        for dev in self.devices.values():
            dev.disconnect()

    def publish_ddata(self, payload):
        for nodo in payload['nodos']:
            device_id = nodo['nombre'].replace(" ", "_").upper()
            
            # 1. ¿Es la primera vez que leemos este PLC? 
            # Si es así, creamos la entidad y enviamos su "Certificado de Nacimiento" (DBIRTH)
            if device_id not in self.devices:
                try:
                    # Estructura obligatoria: Group ID -> Edge Node ID -> Device ID
                    dev = MqttSpbEntityDevice(self.group_id, self.edge_node_id, device_id)
                    
                    # Sparkplug EXIGE declarar las variables y sus tipos en el nacimiento
                    for tag in nodo['tags']:
                        dev.data.set_value(tag['tag'], 0) # Inicializamos en 0
                     # --- AQUÍ PASAMOS LAS CREDENCIALES AL BROKER ---
                    # Si el usuario o pass están vacíos, pasamos None para evitar errores de autenticación
                    usr = self.user if self.user != "" else None
                    pwd = self.password if self.password != "" else None
                    
                    dev.connect(self.broker, self.port, usr, pwd)
                    
                    self.devices[device_id] = dev
                    
                    logging.info(f"[OK MQTT] Dispositivo Sparkplug B creado y conectado: {device_id}")
                except Exception as e:
                    logging.error(f"[ERROR MQTT] Fallo al crear dispositivo {device_id}: {e}")
                    continue

            dev = self.devices[device_id]
            
            if not dev.is_connected():
                continue

            # 2. Preparamos los datos vivos (DDATA)
            has_data = False
            for tag in nodo['tags']:
                val = tag['valor']
                # Filtramos errores de lectura del PLC para no mandar basura a la nube
                if isinstance(val, str) and val in ["Error", "Err", "Reconnecting..."]:
                    continue
                
                # Actualizamos el valor en la memoria del wrapper
                dev.data.set_value(tag['tag'], val)
                has_data = True
            
            # 3. Disparamos el paquete comprimido a la nube
            if has_data:
                dev.publish_data()