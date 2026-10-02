import os
import requests
API_ALERTS_URL = os.getenv("API_ALERTS_URL", "http://localhost:8001/api/notifications/")
# API_ALERTS_URL = os.getenv("API_ALERTS_URL", "https://api-publicationalerts-production-c1cf.up.railway.app/api/notifications/")

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


#Microservicio Orquestador Node.js

NODE_ORCHESTRATOR_URL = os.getenv("NODE_ORCHESTRATOR_URL", "http://localhost:3000/api/posts")

def fetch_posts_from_orchestrator():
    try:
        response = requests.get(NODE_ORCHESTRATOR_URL, timeout=4)
        if response.status_code in (200, 201):
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}", "message": response.text}
    except Exception as e:
        return False, {"error": "Conexión fallida", "message": str(e)}

def create_post_in_orchestrator(caption: str, post_type: str = "post", file_path: str = "publications_media/sample.png"):
    payload = {
        "caption": caption,
        "post_type": post_type,
        "file": file_path
    }
    try:
        response = requests.post(NODE_ORCHESTRATOR_URL, json=payload, timeout=4)
        if response.status_code in (200, 201):
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}", "message": response.text}
    except Exception as e:
        return False, {"error": "Conexión fallida", "message": str(e)}

def delete_post_in_orchestrator(post_id: int):
    url = f"{NODE_ORCHESTRATOR_URL.rstrip('/')}/{post_id}"
    try:
        response = requests.delete(url, timeout=4)
        if response.status_code in (200, 204):
            return True, response.json() if response.content else {"status": "success"}
        else:
            return False, {"error": f"HTTP {response.status_code}", "message": response.text}
    except Exception as e:
        return False, {"error": "Conexión fallida", "message": str(e)}

JAVA_SERVICE_URL = os.getenv("JAVA_SERVICE_URL", "http://localhost:8080/api/posts")
DOTNET_SERVICE_URL = os.getenv("DOTNET_SERVICE_URL", "http://localhost:5000/api/posts")

def fetch_posts_from_java():
    try:
        response = requests.get(JAVA_SERVICE_URL, timeout=4)
        if response.status_code == 200:
            return True, {"fuente": "servicio_primario_java", "data": response.json()}
        else:
            return False, {"error": f"HTTP {response.status_code}", "message": response.text}
    except Exception as e:
        return False, {"error": "Conexión fallida con Java (8080)", "message": str(e)}

def fetch_posts_from_dotnet():
    try:
        response = requests.get(DOTNET_SERVICE_URL, timeout=4)
        if response.status_code == 200:
            return True, {"fuente": "servicio_secundario_dotnet", "data": response.json()}
        else:
            return False, {"error": f"HTTP {response.status_code}", "message": response.text}
    except Exception as e:
        return False, {"error": "Conexión fallida con .NET (5000)", "message": str(e)}

# ==========================================
# Funciones de Resiliencia y Conmutación (Fallback en Django)
# ==========================================

def fetch_posts_django_fallback(reason="Microservicios inactivos"):
    """
    Último nivel de resiliencia: Consulta directamente a PostgreSQL desde el ORM de Django
    cuando los microservicios de la red (Java, .NET, Node) no están disponibles.
    """
    try:
        from .models import PostContent
        posts = list(PostContent.objects.all().order_by('-id').values('id', 'caption', 'file', 'post_type', 'created_at'))
        for p in posts:
            if p.get('created_at'):
                p['created_at'] = p['created_at'].isoformat()
        return True, {
            "status": "degraded_success",
            "fuente": f"Fallback directo de Django ({reason})",
            "data": posts
        }
    except Exception as e:
        return False, {"error": "Error local en Django", "message": str(e)}

def fetch_posts_with_resilience(preferred_source='node'):
    if preferred_source == 'java':
        # 1. Probar Java
        success, res = fetch_posts_from_java()
        if success:
            return True, res
        print("[FALLBACK DJANGO] Java está caído. Conmutando a C# .NET...")
        # 2. Fallback a .NET
        success_dn, res_dn = fetch_posts_from_dotnet()
        if success_dn:
            res_dn['fuente'] = "servicio_secundario_dotnet (Fallback por caída de Java)"
            return True, res_dn
        # 3. Fallback a Node
        success_nd, res_nd = fetch_posts_from_orchestrator()
        if success_nd:
            return True, res_nd
        # 4. Fallback directo a Django ORM
        return fetch_posts_django_fallback("Caída de Java y .NET")

    elif preferred_source == 'dotnet':
        # 1. Probar .NET
        success, res = fetch_posts_from_dotnet()
        if success:
            return True, res
        print("[FALLBACK DJANGO] C# .NET está caído. Conmutando a Java...")
        # 2. Fallback a Java
        success_jv, res_jv = fetch_posts_from_java()
        if success_jv:
            res_jv['fuente'] = "servicio_primario_java (Fallback por caída de C#)"
            return True, res_jv
        # 3. Fallback a Node
        success_nd, res_nd = fetch_posts_from_orchestrator()
        if success_nd:
            return True, res_nd
        # 4. Fallback directo a Django ORM
        return fetch_posts_django_fallback("Caída de .NET y Java")

    else: # preferred_source == 'node'
        # 1. Probar Node.js Gateway (Circuit Breaker)
        success, res = fetch_posts_from_orchestrator()
        if success:
            return True, res
        print("[FALLBACK DJANGO] Node.js Gateway no dio respuesta limpia. Conmutando directo a Java...")
        # 2. Fallback directo a Java
        success_jv, res_jv = fetch_posts_from_java()
        if success_jv:
            res_jv['fuente'] = "servicio_primario_java (Fallback por caída de Node)"
            return True, res_jv
        # 3. Fallback directo a .NET
        success_dn, res_dn = fetch_posts_from_dotnet()
        if success_dn:
            res_dn['fuente'] = "servicio_secundario_dotnet (Fallback por caída de Node)"
            return True, res_dn
        # 4. Fallback directo a Django ORM
        return fetch_posts_django_fallback("Microservicios inactivos")


def create_post_resilient(caption: str, post_type: str = "post", file_path: str = "publications_media/sample.png"):

    # 1. Probar Node.js Orquestador
    success, res = create_post_in_orchestrator(caption, post_type, file_path)
    if success:
        return True, res

    print("[FALLBACK CREAR] Node.js no pudo responder. Conmutando a Java (8080)...")
    payload = {"caption": caption, "post_type": post_type, "file": file_path}

    # 2. Fallback a Java
    try:
        r_java = requests.post(JAVA_SERVICE_URL, json=payload, timeout=4)
        if r_java.status_code in (200, 201):
            return True, {"status": "success", "fuente": "servicio_primario_java (Fallback de Django)", "data": r_java.json()}
    except Exception as e:
        print(f"[FALLBACK CREAR] Java no respondió ({e}). Conmutando a .NET (5000)...")

    # 3. Fallback a .NET
    try:
        r_dotnet = requests.post(DOTNET_SERVICE_URL, json=payload, timeout=4)
        if r_dotnet.status_code in (200, 201):
            return True, {"status": "degraded_success", "fuente": "servicio_secundario_dotnet (Fallback de Django)", "data": r_dotnet.json()}
    except Exception as e:
        print(f"[FALLBACK CREAR] C# .NET tampoco respondió ({e}). Ejecutando Fallback directo en Django ORM...")

    # 4. Fallback directo en Django ORM
    try:
        from .models import PostContent
        new_post = PostContent.objects.create(
            caption=caption,
            post_type=post_type,
            file=file_path
        )
        return True, {
            "status": "degraded_success",
            "fuente": "Fallback directo de Django (Microservicios inactivos)",
            "data": {"id": new_post.id, "caption": new_post.caption, "file": str(new_post.file), "post_type": new_post.post_type}
        }
    except Exception as ex:
        return False, {"error": "Todos los servicios caídos", "message": str(ex)}


def update_post_in_orchestrator(post_id: int, caption: str, post_type: str = "post", file_path: str = "publications_media/sample.png"):
    """
    Actualiza una publicación existente a través del Orquestador Node.js (Puerto 3000).
    """
    url = f"{NODE_ORCHESTRATOR_URL.rstrip('/')}/{post_id}"
    payload = {
        "caption": caption,
        "post_type": post_type,
        "file": file_path
    }
    try:
        response = requests.put(url, json=payload, timeout=5)
        if response.status_code in (200, 201):
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}", "message": response.text}
    except Exception as e:
        return False, {"error": "Conexión fallida", "message": str(e)}


def update_post_resilient(post_id: int, caption: str, post_type: str = "post", file_path: str = "publications_media/sample.png"):
    """
    Actualiza un post con resiliencia multi-capa (Node -> Java -> .NET -> Django ORM).
    """
    # 1. Intentar vía Node.js Orquestador
    success, res = update_post_in_orchestrator(post_id, caption, post_type, file_path)
    if success:
        return True, res

    print("[FALLBACK EDITAR] Node.js no pudo responder. Conmutando a Java (8080)...")
    url_java = f"{JAVA_SERVICE_URL.rstrip('/')}/{post_id}"
    payload = {"caption": caption, "post_type": post_type, "file": file_path}

    # 2. Fallback a Java
    try:
        r_java = requests.put(url_java, json=payload, timeout=4)
        if r_java.status_code in (200, 201):
            return True, {"status": "success", "fuente": "servicio_primario_java (Fallback de Django)", "data": r_java.json()}
    except Exception as e:
        print(f"[FALLBACK EDITAR] Java no respondió ({e}). Conmutando a .NET (5000)...")

    # 3. Fallback a .NET
    try:
        url_dotnet = f"{DOTNET_SERVICE_URL.rstrip('/')}/{post_id}"
        r_dotnet = requests.put(url_dotnet, json=payload, timeout=4)
        if r_dotnet.status_code in (200, 201):
            return True, {"status": "degraded_success", "fuente": "servicio_secundario_dotnet (Fallback de Django)", "data": r_dotnet.json()}
    except Exception as e:
        print(f"[FALLBACK EDITAR] C# .NET tampoco respondió ({e}). Ejecutando Fallback directo en Django ORM...")

    # 4. Fallback directo en Django ORM
    try:
        from .models import PostContent
        post = PostContent.objects.get(pk=post_id)
        post.caption = caption
        post.post_type = post_type
        if file_path:
            post.file = file_path
        post.save()
        return True, {
            "status": "degraded_success",
            "fuente": "Fallback directo de Django (Microservicios inactivos)",
            "data": {"id": post.id, "caption": post.caption, "file": str(post.file), "post_type": post.post_type}
        }
    except Exception as ex:
        return False, {"error": "Error editando localmente", "message": str(ex)}



