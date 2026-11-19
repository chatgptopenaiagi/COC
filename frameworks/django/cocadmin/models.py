from django.conf import settings
from django.db import models

class OperationalNote(models.Model):
    task_id = models.CharField(max_length=128)
    text = models.TextField(max_length=4000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        permissions = [("control_broker", "Can cancel and reconcile COC tasks")]
    def __str__(self): return self.task_id

class DeploymentProfile(models.Model):
    name = models.CharField(max_length=100, unique=True)
    broker_url = models.URLField()
    enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    def __str__(self): return self.name
