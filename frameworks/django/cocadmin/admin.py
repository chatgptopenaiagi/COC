from django.contrib import admin
from .models import OperationalNote, DeploymentProfile
@admin.register(OperationalNote)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("task_id", "author", "created_at")
    readonly_fields = ("created_at",)
@admin.register(DeploymentProfile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "broker_url", "enabled")
admin.site.site_header = "COC Administration"
admin.site.site_title = "COC"
