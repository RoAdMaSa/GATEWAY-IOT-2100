import requests
import threading
import logging

# --- REEMPLAZA ESTOS VALORES CON LOS DE TU FASE 1 ---
TELEGRAM_TOKEN = ""
CHAT_ID = ""

def send_telegram_alert(mensaje):
    """
    Envía un mensaje por Telegram usando un hilo secundario (Thread)
    para evitar que un lag en el chip 4G congele la lectura del PLC.
    """
    def _send():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": CHAT_ID, "text": mensaje}
            response = requests.post(url, data=data, timeout=5)
            if response.status_code != 200:
                logging.error(f"Error al enviar Telegram: {response.text}")
        except Exception as e:
            logging.error(f"Fallo de conexión al enviar Telegram: {e}")
            
    # Lanzamos la petición en segundo plano
    hilo = threading.Thread(target=_send)
    hilo.start()
