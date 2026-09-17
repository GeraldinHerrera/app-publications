from django.contrib import admin
from .models import SocialAccount, PostContent, PostTask

admin.site.register(SocialAccount)
admin.site.register(PostContent)
admin.site.register(PostTask)
# Register your models here.
