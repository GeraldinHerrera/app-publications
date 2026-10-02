from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('create/', views.create_publication, name='create_publication'),
    path('createpost/', views.create_post, name='create_post'),
    path('ai-assistant/', views.ai_assistant_view, name='ai_assistant'),
]