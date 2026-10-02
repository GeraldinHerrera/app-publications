from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from .models import PostTask, PostContent, SocialAccount
from .services import (
    send_alert_notification,
    fetch_posts_from_orchestrator,
    fetch_posts_from_java,
    fetch_posts_from_dotnet,
    fetch_posts_with_resilience,
    create_post_in_orchestrator,
    create_post_resilient,
    update_post_in_orchestrator,
    update_post_resilient,
    delete_post_in_orchestrator
)
from .ai_assistant import generate_ai_response
import os

def format_post_dict(post_dict):
    file_path = str(post_dict.get('file', ''))
    if not file_path:
        media_url = ''
    elif file_path.startswith('http://') or file_path.startswith('https://') or file_path.startswith('/media/'):
        media_url = file_path
    else:
        media_url = f"/media/{file_path}"
    
    ext = os.path.splitext(file_path)[1].lower()
    video_exts = ['.mp4', '.webm', '.ogg', '.mov', '.m4v', '.mkv']
    image_exts = ['.jpg', '.jpeg', '.jfif', '.pjpeg', '.pjp', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico', '.avif', '.heic', '.tiff']
    
    is_video = ext in video_exts
    is_image = ext in image_exts or ext == '' or (not is_video)

    post_dict_copy = dict(post_dict)
    post_dict_copy['media_url'] = media_url
    post_dict_copy['is_video'] = is_video
    post_dict_copy['is_image'] = is_image
    return post_dict_copy

def index(request):
    history = PostTask.objects.select_related('post_content', 'account').order_by('-scheduled_at')
    return render(request, 'publications_network/index.html', {'history': history})

def post_detail(request, post_id):
    # Se usa para relaciones inversas o muchos a muchos (ManyToMany, o relaciones inversas de ForeignKey)
    # Con la sintaxis de doble guion bajo (tasks__account), Django realiza búsquedas separadas por lotes y une los resultados en memoria en Python:
    # Consulta el PostContent
    # Consulta todas las tareas (tasks) asociadas a ese post.
    # Consulta todas las cuentas (account) asociadas a esas tareas.
    post = get_object_or_404(PostContent.objects.prefetch_related('tasks__account'), pk=post_id)
    return render(request, 'publications_network/post_detail.html', {'post': post})

def create_publication(request):
  
    if request.method == 'POST':
        account_mode = request.POST.get('account_mode', 'new')
        post_mode = request.POST.get('post_mode', 'new')

        # Obtener o crear SocialAccount
        if account_mode == 'existing' and request.POST.get('existing_account_id'):
            account = get_object_or_404(SocialAccount, pk=request.POST.get('existing_account_id'))
        else:
            platform = request.POST.get('new_platform', 'instagram')
            account_user = request.POST.get('new_account_user', 'usuario_demo').strip()
            if not account_user:
                account_user = 'usuario_demo'
            account_password = request.POST.get('new_account_password', 'password123')
            account, _ = SocialAccount.objects.get_or_create(
                platform=platform,
                account_user=account_user,
                defaults={'account_password': account_password}
            )

        # Obtener o crear PostContent
        if post_mode == 'existing' and request.POST.get('existing_post_id'):
            post = get_object_or_404(PostContent, pk=request.POST.get('existing_post_id'))
        else:
            post_type = request.POST.get('new_post_type', 'post')
            caption = request.POST.get('new_caption', 'Nueva publicación desde Django').strip()
            if not caption:
                caption = 'Nueva publicación desde Django'
            uploaded_file = request.FILES.get('new_file')
            
            post = PostContent.objects.create(
                post_type=post_type,
                caption=caption,
                file=uploaded_file if uploaded_file else 'publications_media/sample.png'
            )

        # Determinar fecha y estado 
        scheduled_at_raw = request.POST.get('scheduled_at')
        if scheduled_at_raw:
            try:
                scheduled_at = timezone.datetime.fromisoformat(scheduled_at_raw)
                if timezone.is_naive(scheduled_at):
                    scheduled_at = timezone.make_aware(scheduled_at)
            except Exception: 
                scheduled_at = timezone.now()
        else:
            scheduled_at = timezone.now()

        task_status = request.POST.get('status', 'completed')


        task = PostTask.objects.create(
            post_content=post,
            account=account,
            scheduled_at=scheduled_at,
            status=task_status
        )

        recipient_email = request.POST.get('recipient_email', 'hgeraldin35@gmail.com')
        message_body = (
            f"¡Hola! Se ha registrado la tarea #{task.id} (Estado: {task.get_status_display()}) "
            f"para la red {account.get_platform_display()} (@{account.account_user}).\n\n"
            f"Publicación #{post.id} ({post.get_post_type_display()}):\n\"{post.caption}\""
        )

        event_type = "POST_PUBLISHED" if task_status == "completed" else "POST_SCHEDULED"
        api_success = send_alert_notification(
            post_task_id=task.id,
            event_type=event_type,
            channel_type="email",
            recipient=recipient_email,
            message=message_body
        )

        if api_success:
            messages.success(request, f"Tarea #{task.id} guardada (Publicacion #{post.id} <-> Cuenta @{account.account_user}) y notificacion enviada a {recipient_email}.")
        else:
            messages.warning(request, f"Tarea #{task.id} creada, pero no se pudo enviar la notificacion.")

        return redirect('index')

    accounts = SocialAccount.objects.all().order_by('-id')
    posts = PostContent.objects.all().order_by('-id')
    now_str = timezone.now().strftime("%Y-%m-%dT%H:%M")

    return render(request, 'publications_network/create_publication.html', {
        'accounts': accounts,
        'posts': posts,
        'now_str': now_str
    })

def create_post(request):
    selected_source = request.GET.get('source', 'node')

    if request.method == 'POST':
        action = request.POST.get('action', 'create_django')

        if action == 'create_microservice':
            post_type = request.POST.get('post_type', 'post')
            caption = request.POST.get('caption', '').strip() or 'Post desde Orquestador Node'
            file_name = 'publications_media/sample.png'
            if request.FILES.get('file'):
                uploaded = request.FILES.get('file')
                file_name = f"publications_media/{uploaded.name}"

            success, response = create_post_resilient(caption, post_type, file_name)
            if success:
                fuente = response.get('fuente', 'Orquestador')
                messages.success(request, f"Publicación enviada con éxito (Atendida por: {fuente}).")
            else:
                messages.error(request, f"Error enviando al Orquestador: {response.get('message')}")
            return redirect(f"/publications/createpost/?source={selected_source}")

        elif action == 'delete_microservice':
            post_id = request.POST.get('post_id')
            if post_id:
                success, response = delete_post_in_orchestrator(int(post_id))
                if success:
                    messages.success(request, f"Publicación #{post_id} eliminada mediante el Orquestador Node.")
                else:
                    messages.error(request, f"Error al eliminar: {response.get('message')}")
            return redirect(f"/publications/createpost/?source={selected_source}")

        elif action == 'delete_django':
            post_id = request.POST.get('post_id')
            if post_id:
                post_obj = PostContent.objects.filter(pk=int(post_id)).first()
                if post_obj:
                    post_obj.delete()
                    messages.success(request, f"Publicación #{post_id} eliminada localmente en Django con éxito.")
                else:
                    messages.warning(request, f"La publicación #{post_id} no fue encontrada en la base de datos de Django.")
            return redirect(f"/publications/createpost/?source={selected_source}")

        else:
            post_type = request.POST.get('post_type', 'post')
            caption = request.POST.get('caption', '').strip() or 'Nueva publicación'
            uploaded_file = request.FILES.get('file')

            post = PostContent.objects.create(
                post_type=post_type,
                caption=caption,
                file=uploaded_file if uploaded_file else 'publications_media/sample.png'
            )

            messages.success(request, f"Post #{post.id} ({post.get_post_type_display()}) creado localmente en Django con éxito.")
            return redirect(f"/publications/createpost/?source={selected_source}")

    # Consulta de publicaciones con resiliencia y conmutación automática por error
    ms_success, ms_response = fetch_posts_with_resilience(selected_source)

    # Estado reportado y fuente real
    circuit_breaker_status = "Operativo"
    circuit_breaker_fuente = "Desconocida"
    real_fuente = ""

    if ms_success and isinstance(ms_response, dict):
        circuit_breaker_status = ms_response.get('status', 'Operativo')
        circuit_breaker_fuente = ms_response.get('fuente', 'Java Primario')
        real_fuente = ms_response.get('fuente', '')
    else:
        circuit_breaker_status = "Degradado / Desconectado"
        circuit_breaker_fuente = "Ninguno"

    # Determinar el título dinámico del servicio REAL que devolvió la información
    if 'Fallback directo de Django' in real_fuente:
        active_source_title = f"Django ORM - [{real_fuente}]"
    elif 'servicio_primario_java' in real_fuente:
        if 'Fallback' in real_fuente:
            active_source_title = f"Java  - [{real_fuente}]"
        else:
            active_source_title = "Java"
    elif 'servicio_secundario_dotnet' in real_fuente:
        if 'Fallback' in real_fuente:
            active_source_title = f"C# .NET [{real_fuente}]"
        else:
            active_source_title = "C# .NET"
    elif real_fuente:
        active_source_title = real_fuente
    else:
        active_source_title = f"Solicitado: {selected_source.upper()} (Sin Respuesta)"

    microservices_posts = []
    if ms_success and isinstance(ms_response, dict):
        raw_posts = ms_response.get('data', [])
        microservices_posts = [format_post_dict(p) for p in raw_posts]

    query_info = None
    if 'source' in request.GET:
        query_info = {
            'source': selected_source,
            'real_fuente': real_fuente,
            'success': ms_success
        }

    cb_success = ms_success
    local_posts = PostContent.objects.all().order_by('-created_at')

    return render(request, 'publications_network/create_post.html', {
        'post_types': PostContent.POST_TYPES,
        'posts': local_posts,
        'microservices_posts': microservices_posts,
        'ms_success': ms_success,
        'ms_response': ms_response,
        'selected_source': selected_source,
        'active_source_title': active_source_title,
        'cb_success': cb_success,
        'circuit_breaker_status': circuit_breaker_status,
        'circuit_breaker_fuente': circuit_breaker_fuente,
        'query_info': query_info
    })

def edit_post(request, post_id):
    post = get_object_or_404(PostContent, pk=post_id)
    if request.method == 'POST':
        action = request.POST.get('action', 'edit_django')
        post_type = request.POST.get('post_type', post.post_type)
        caption = request.POST.get('caption', post.caption or '').strip()
        file_path = str(post.file.name) if post.file else 'publications_media/sample.png'

        if request.FILES.get('file'):
            uploaded = request.FILES.get('file')
            file_path = f"publications_media/{uploaded.name}"

        if action == 'edit_microservice':
            success, response = update_post_resilient(post_id, caption, post_type, file_path)
            if success:
                fuente = response.get('fuente', 'Orquestador Node.js')
                messages.success(request, f"Publicación #{post_id} actualizada con éxito vía Microservicios (Atendida por: {fuente}).")
            else:
                messages.error(request, f"Error actualizando vía Microservicios: {response.get('message')}")
            return redirect('create_post')
        else:
            post.post_type = post_type
            post.caption = caption
            if request.FILES.get('file'):
                post.file = request.FILES.get('file')
            post.save()

            messages.success(request, f"Post #{post.id} actualizado localmente en Django con éxito.")
            return redirect('create_post')

    return render(request, 'publications_network/edit_post.html', {
        'post': post,
        'post_types': PostContent.POST_TYPES
    })

def delete_post(request, post_id):
    post = get_object_or_404(PostContent, pk=post_id)
    if request.method == 'POST':
        action = request.POST.get('action', 'delete_django')
        if action == 'delete_microservice':
            success, response = delete_post_in_orchestrator(post.id)
            if success:
                messages.success(request, f"Publicación #{post.id} eliminada con éxito vía Microservicios (Orquestador Node.js).")
            else:
                messages.error(request, f"Error eliminando vía Microservicios: {response.get('message')}")
        else:
            post_id_val = post.id
            post.delete()
            messages.success(request, f"💾 Post #{post_id_val} eliminado localmente en Django con éxito.")
        return redirect('create_post')

    return render(request, 'publications_network/delete_post_confirm.html', {
        'post': post
    })

def ai_assistant_view(request):
    ai_response = None
    user_prompt = ""

    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '').strip()
        if user_prompt:
            ai_response = generate_ai_response(user_prompt)

    return render(request, 'publications_network/ai_assistant.html', {
        'user_prompt': user_prompt,
        'ai_response': ai_response
    })