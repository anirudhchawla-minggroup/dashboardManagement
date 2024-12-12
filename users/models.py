from django.db import models
from django.utils.timezone import now

class UserModel(models.Model):
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)  # Determines if the user is active
    is_deleted = models.BooleanField(default=False)  # Soft delete flag
    created_at = models.DateTimeField(default=now, editable=False)  # Auto-set at creation
    updated_at = models.DateTimeField(auto_now=True)  # Auto-update on save

    def __str__(self):
        return self.username
