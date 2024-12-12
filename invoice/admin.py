from django.contrib import admin
from .models import CompanyDetails, InvoiceManagementLog, NewPdfFilesLog, NoCompanyPdfFilesLog

# Register your model here
@admin.register(InvoiceManagementLog)
class InvoiceManagementLogAdmin(admin.ModelAdmin):
    def company_short_form(self, obj):
        return obj.company_details.company_short_form
    list_display = ('company_short_form','email_date', 'total_pdfs', 'pdfs_of_the_company', 'username_of_person_logged_in', 'is_active', 'is_delete','created_at')
    search_fields = ('company_name', 'username_of_person_logged_into_slack')
    list_filter = ('is_active', 'is_delete', 'email_date')

@admin.register(NewPdfFilesLog)
class NewPdfFilesAddedAdmin(admin.ModelAdmin):
    list_display = ('invoice_log','pdf_filename','email_date', 'is_active', 'is_delete','created_at')

@admin.register(CompanyDetails)
class CompanyDetailsAdmin(admin.ModelAdmin):
    list_display = ('company_keyword','company_short_form','iban', 'is_active', 'is_delete','created_at')

@admin.register(NoCompanyPdfFilesLog)
class NoCompanyPdfFilesLogAdmin(admin.ModelAdmin):
    list_display = ('pdf_filename','email_id','email_date', 'is_active', 'is_delete','created_at')
