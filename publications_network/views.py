from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from .models import PostTask, PostContent, SocialAccount
from .services import send_alert_notification
from .ai_assistant import generate_ai_response

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