from django.db import models

class SupplierDetailsModel(models.Model):
    recipient = models.CharField(max_length=255)  # Make this unique if recipients should also be unique
    iban = models.CharField(max_length=34)  # IBANs in Europe can be up to 34 characters long
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.recipient} - {self.iban}"