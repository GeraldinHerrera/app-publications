import os
import requests
API_ALERTS_URL = os.getenv("API_ALERTS_URL", "http://localhost:8001/api/notifications/")

def send_alert_notification(post_task_id: int, event_type: str, channel_type: str, recipient: str, message: str) -> bool:

    payload = {
        "post_task_id": post_task_id,
        "event_type": event_type,     
        "channel_type": channel_type,  
        "recipient": recipient,
        "message": message
    }
    
    try:
        response = requests.post(API_ALERTS_URL, json=payload, timeout=4)
        if response.status_code in (200, 201):
            print(f"[SUCCESS] Alerta enviada con exito a la API externa para la tarea #{post_task_id}")
            return True
        else:
            print(f"[WARNING] Error de API Externa: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[WARNING] No se pudo conectar con la API de Alertas ({API_ALERTS_URL}): {e}")
        return False
