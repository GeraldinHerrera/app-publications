import os
from django.db import models

class SocialAccount(models.Model):
    PLATFORMS = [
        ('instagram', 'Instagram'),
        ('tiktok', 'TikTok'),
        ('facebook', 'Facebook'),
    ]
    platform = models.CharField(max_length=20, choices=PLATFORMS)
    account_user = models.CharField(max_length=150)
    account_password = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.get_platform_display()} - {self.account_user}"


class PostContent(models.Model):
    POST_TYPES = [
        ('post', 'Post / Feed'),
        ('reel', 'Reel / Short'),
        ('story', 'Historia'),
    ]
    file = models.FileField(upload_to='publications_media/', help_text="El archivo físico en disco")
    caption = models.TextField(blank=True, null=True, help_text="Texto o hashtags base")
    post_type = models.CharField(max_length=10, choices=POST_TYPES, default='post')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def file_extension(self):
        if self.file:
            return os.path.splitext(str(self.file.name))[1].lower()
        return ''

    @property
    def is_image(self):
        ext = self.file_extension
        image_exts = ['.jpg', '.jpeg', '.jfif', '.pjpeg', '.pjp', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico', '.avif', '.heic', '.tiff']
        return ext in image_exts or ext == ''

    @property
    def is_video(self):
        video_exts = ['.mp4', '.webm', '.ogg', '.mov', '.m4v', '.mkv']
        return self.file_extension in video_exts

    @property
    def media_url(self):
        if not self.file:
            return ''
        try:
            return self.file.url
        except Exception:
            return f"/media/{self.file.name}"


    def __str__(self):
        return f"{self.post_type} - {self.id}"



class PostTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'En proceso'),
        ('completed', 'Publicado'),
        ('failed', 'Error'),
    ]
    # tasks me deja acceder a los datos de la tabla con la que tengo esa llave foranea 
    post_content = models.ForeignKey(PostContent, on_delete=models.CASCADE, related_name='tasks')
    account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name='tasks')
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.account.platform} ({self.status}) - {self.scheduled_at}"