import logging
import ssl
import json # <-- NUEVO
import paho.mqtt.client as mqtt_client
from mqtt_spb_wrapper import MqttSpbEntityDevice

# --- MONKEY PATCH DE SEGURIDAD ---
original_connect = mqtt_client.Client.connect

def secure_connect(self, *args, **kwargs):
    port = kwargs.get('port', args[1] if len(args) > 1 else 1883)
    if port == 8883:
        try:
            self.tls_set(cert_reqs=ssl.CERT_NONE)
            self.tls_insecure_set(True)
        except Exception:
            pass 
    return original_connect(self, *args, **kwargs)

mqtt_client.Client.connect = secure_connect
# ---------------------------------

class MqttSparkplugManager:
    def __init__(self, config):
        self.config = config
        self.group_id = self.config.get('group_id', 'SMI')
        self.edge_node_id = self.config.get('node_id', 'Linea32')
        self.broker = self.config.get('broker', 'localhost')
        self.port = int(self.config.get('port', 8883))
        
        self.user = self.config.get('user', '')
        self.password = self.config.get('pass', '')
        self.client_id = self.config.get('client_id', 'gateway_smi') 
        
        self.devices = {} 
        
        # --- NUEVO: CLIENTE PARA TIEMPO REAL (JSON) ---
        # Le añadimos "_RT" al Client ID para que EMQX no lo confunda con el de Sparkplug
        self.rt_client = mqtt_client.Client(self.client_id + "_RT")
        if self.user:
            self.rt_client.username_pw_set(self.user, self.password)
        # ----------------------------------------------

    def connect(self):
        print("MQTT: Inicializando clientes...")
        # Conectamos el cliente de tiempo real en segundo plano
        if self.port == 8883:
            self.rt_client.tls_set(cert_reqs=ssl.CERT_NONE)
            self.rt_client.tls_insecure_set(True)
        try:
            self.rt_client.connect_async(self.broker, self.port)
            self.rt_client.loop_start()
            logging.info("[OK MQTT] Cliente JSON en tiempo real conectado.")
        except Exception as e:
            logging.error(f"[ERROR MQTT] No se pudo conectar cliente RT: {e}")

    def disconnect(self):
        self.rt_client.loop_stop()
        self.rt_client.disconnect()
        for dev in self.devices.values():
            dev.disconnect()

    def publish_realtime(self, payload):
        """ Envía los datos cada segundo en formato JSON legible para la Web """
        for nodo in payload['nodos']:
            # Tópico limpio: SMI/REALTIME/SOPLADO/L32
            device_id = nodo['nombre'].replace(" ", "_").upper()
            topic = f"{self.group_id}/REALTIME/{self.edge_node_id}/{device_id}"
            
            # Formateamos solo las variables válidas
            datos = {tag['tag']: tag['valor'] for tag in nodo['tags'] if not (isinstance(tag['valor'], str) and tag['valor'] in ["Error", "Err", "Reconnecting..."])}
            
            if datos:
                try:
                    self.rt_client.publish(topic, json.dumps(datos), qos=0)
                except Exception:
                    pass

    def publish_ddata(self, payload):
        """ Envía los datos comprimidos Sparkplug B para la Base de Datos """
        for nodo in payload['nodos']:
            device_id = nodo['nombre'].replace(" ", "_").upper()
            
            if device_id not in self.devices:
                try:
                    dev = MqttSpbEntityDevice(self.group_id, self.edge_node_id, device_id)
                    for tag in nodo['tags']:
                        val = tag['valor']
                        if isinstance(val, str) and val in ["Error", "Err", "Reconnecting..."]:
                            dev.data.set_value(tag['tag'], 0) 
                        else:
                            dev.data.set_value(tag['tag'], val) 
                        
                    usr = self.user if self.user != "" else None
                    pwd = self.password if self.password != "" else None
                    
                    dev.connect(self.broker, self.port, usr, pwd)
                    self.devices[device_id] = dev
                    print(f"MQTT: Sparkplug B conectado a {device_id}")
                except Exception:
                    continue

            dev = self.devices[device_id]
            if not dev.is_connected():
                continue

            has_data = False
            for tag in nodo['tags']:
                val = tag['valor']
                if isinstance(val, str) and val in ["Error", "Err", "Reconnecting..."]:
                    continue
                dev.data.set_value(tag['tag'], val)
                has_data = True
            
            if has_data:
                dev.publish_data()
                print("MQTT: DDATA (Sparkplug) enviado para PostgreSQL")