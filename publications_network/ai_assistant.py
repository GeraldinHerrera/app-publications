import os
from dotenv import load_dotenv
from google import genai
from .models import SocialAccount, PostContent, PostTask

load_dotenv()

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
"""
    return summary

def generate_ai_response(user_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ Error: No se ha configurado la clave del api en el archivo .env."

    db_context = get_database_summary()

    system_instruction = (
        "Eres un Asistente Virtual experto en Redes Sociales, Marketing Digital y Análisis de Datos "
        "para la plataforma 'Publications'.\n\n"
        f"{db_context}\n\n"
        "INSTRUCCIONES DE RESPUESTA:\n"
        "1. Si el usuario pregunta sobre los datos, cantidad de posts, publicaciones o cuentas del proyecto, "
        "responde usando la información real proporcionada en los DATOS ACTUALES DE LA BASE DE DATOS de arriba.\n"
        "2. Si el usuario pregunta sobre tendencias de redes sociales (ej. Reels en tendencia, canciones virales de Instagram, "
        "hashtags, mejores horas para publicar), dale sugerencias creativas, estructuradas y profesionales.\n"
        "3. Mantén un tono amable, profesional, claro y responde formateando la respuesta en Markdown."
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
            return f"⚠️ Error al conectar con la API de Google Gemini: {e}"
