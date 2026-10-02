import os
import requests
from dotenv import load_dotenv
from google import genai
from .models import SocialAccount, PostContent, PostTask

load_dotenv()

API_ALERTS_NOTIFICATIONS_URL = os.getenv(
    "API_ALERTS_NOTIFICATIONS_URL",
    "https://api-publicationalerts-production-c1cf.up.railway.app/api/notifications/"
)

def get_alerts_summary() -> str:
    """Consulta la API de Alertas en Railway para obtener las publicaciones notificadas/enviadas."""
    try:
        response = requests.get(API_ALERTS_NOTIFICATIONS_URL, timeout=4)
        if response.status_code == 200:
            notifications = response.json()
            total_notifications = len(notifications)
            sent_count = sum(1 for n in notifications if n.get('status') == 'SENT')
            failed_count = sum(1 for n in notifications if n.get('status') == 'FAILED')

            recent_details = []
            for n in notifications[:5]:
                task_id = n.get('post_task_id', 'N/A')
                recipient = n.get('recipient', 'N/A')
                status = n.get('status', 'N/A')
                event = n.get('event_type', 'N/A')
                sent_at = str(n.get('sent_at', ''))[:16].replace('T', ' ')
                msg = str(n.get('message', '')).replace('\n', ' ')
                if len(msg) > 60:
                    msg = msg[:60] + "..."
                recent_details.append(
                    f"- Notificación #{n.get('id')} [Tarea #{task_id}] | Estado: {status} | "
                    f"Evento: {event} | Destinatario: {recipient} | Fecha: {sent_at} | Msj: \"{msg}\""
                )

            recent_str = "\n  ".join(recent_details) if recent_details else "No hay alertas registradas aún."

            return f"""
            DATOS EN TIEMPO REAL DE ALERTAS Y NOTIFICACIONES (API Railway: {API_ALERTS_NOTIFICATIONS_URL}):
            - Total de Notificaciones Registradas: {total_notifications}
            - Enviadas con Éxito (SENT): {sent_count}
            - Fallidas (FAILED): {failed_count}
            - Últimas Notificaciones/Alertas de Publicaciones:
            {recent_str}
            """
        else:
            return f"\nDATOS DE ALERTAS (API Railway {API_ALERTS_NOTIFICATIONS_URL}): Respuesta HTTP {response.status_code}\n"
    except Exception as e:
        return f"\nDATOS DE ALERTAS (API Railway {API_ALERTS_NOTIFICATIONS_URL}): No se pudo conectar ({e})\n"

def get_database_summary() -> str:
    total_accounts = SocialAccount.objects.count()
    total_posts = PostContent.objects.count()
    total_tasks = PostTask.objects.count()

    accounts = SocialAccount.objects.all()
    account_details = [f"- {acc.get_platform_display()}: @{acc.account_user}" for acc in accounts]
    account_str = "\n".join(account_details) if account_details else "No hay cuentas sociales registradas aún."

    completed_tasks = PostTask.objects.filter(status='completed').count()
    pending_tasks = PostTask.objects.filter(status='pending').count()
    processing_tasks = PostTask.objects.filter(status='processing').count()
    failed_tasks = PostTask.objects.filter(status='failed').count()

    recent_tasks = PostTask.objects.select_related('post_content', 'account').order_by('-scheduled_at')[:5]
    recent_details = []
    for t in recent_tasks:
        recent_details.append(
            f"- Tarea #{t.id} [{t.account.get_platform_display()} - @{t.account.account_user}] "
            f"Tipo: {t.post_content.get_post_type_display()} | Estado: {t.get_status_display()} | "
            f"Texto: \"{t.post_content.caption}\""
        )
    recent_str = "\n".join(recent_details) if recent_details else "No hay publicaciones agendadas."

    alerts_summary = get_alerts_summary()

    summary = f"""
    DATOS ACTUALES DE LA BASE DE DATOS DEL PROYECTO ('Publications Network'):
    - Total de Cuentas de Redes Sociales: {total_accounts}
    Cuentas registradas:
    {account_str}

    - Total de Contenidos Creados: {total_posts}
    - Total de Tareas de Publicación (PostTask): {total_tasks}
    - Publicadas / Completadas: {completed_tasks}
    - Pendientes: {pending_tasks}
    - En Proceso: {processing_tasks}
    - Con Error: {failed_tasks}

    - Publicaciones Recientes (Últimas 5):
    {recent_str}

    {alerts_summary}
    """
    return summary

def generate_ai_response(user_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return " Error: No se ha configurado la clave del api en el archivo .env."

    db_context = get_database_summary()

    system_instruction = (
        "Eres un Asistente Virtual experto en Redes Sociales, Marketing Digital, Análisis de Datos y Alertas "
        "para la plataforma 'Publications'.\n\n"
        "Restricción estricta: Limítate exclusivamente a estos temas. Si te preguntan "
        "sobre cualquier asunto ajeno a redes sociales, marketing digital o tendencias, "
        "indica con amabilidad y brevedad que tu área de soporte se enfoca únicamente en esas áreas.\n\n"
        f"{db_context}\n\n"
        "INSTRUCCIONES DE RESPUESTA:\n"
        "1. Si el usuario pregunta sobre datos locales, cantidad de posts, publicaciones o cuentas del proyecto, "
        "responde usando la información real proporcionada en los DATOS ACTUALES DE LA BASE DE DATOS.\n"
        "2. Si el usuario pregunta sobre **alertas**, **notificaciones**, **publicaciones ya enviadas** o el **estado de las alertas**, "
        "consulta y responde usando los datos entregados  de  DATOS EN TIEMPO REAL DE ALERTAS Y NOTIFICACIONES"
        "la cual contiene el listado de las publicaciones ya notificadas y enviadas.\n"
        "3. Si el usuario pregunta sobre tendencias de redes sociales (ej. Reels en tendencia, canciones virales, hashtags, mejores horas), "
        "dale sugerencias creativas, estructuradas y profesionales.\n"
        "4. Mantén un tono amable, profesional, claro y responde formateando la respuesta en Markdown."
    )

    client = genai.Client(api_key=api_key)
    full_prompt = f"{system_instruction}\n\nPREGUNTA DEL USUARIO:\n{user_prompt}"

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=full_prompt
        )
        return response.text
    except Exception:
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            return f"Error al conectar con la API de Google Gemini: {e}"

