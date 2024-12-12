from django.contrib import admin

from sepa_generator_for_invoice.models import SupplierDetailsModel

@admin.register(SupplierDetailsModel)
class SupplierDetailsAdmin(admin.ModelAdmin):
    list_display = ('recipient','iban', 'is_active', 'is_delete','created_at')  
