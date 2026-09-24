from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('create/', views.create_publication, name='create_publication'),
    path('ai-assistant/', views.ai_assistant_view, name='ai_assistant'),
]