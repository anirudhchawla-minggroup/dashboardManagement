from django.db import models

class CompanyDetails(models.Model):
    company_keyword = models.CharField(max_length=255, unique=True)  # Enforcing uniqueness for company_keyword
    company_short_form = models.CharField(max_length=255, unique=True)  # Enforcing uniqueness for company_short_form
    iban = models.CharField(max_length=34, default="", blank=True)
    bic = models.CharField(max_length=34, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company_keyword} ({self.company_short_form})"
    
class InvoiceManagementLog(models.Model):
    email_date = models.DateField()
    company_details = models.ForeignKey(CompanyDetails, related_name='company_details', on_delete=models.CASCADE)
    total_pdfs = models.IntegerField()
    pdfs_of_the_company = models.IntegerField()
    username_of_person_logged_in = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company_details}"

class NewPdfFilesLog(models.Model):
    invoice_log = models.ForeignKey(InvoiceManagementLog, related_name='pdf_files', on_delete=models.CASCADE)
    pdf_filename = models.CharField(max_length=255)
    email_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"PDF File: {self.pdf_filename} for {self.invoice_log}"
    
class NoCompanyPdfFilesLog(models.Model):
    pdf_filename = models.CharField(max_length=255)
    email_id = models.CharField(max_length=50)
    email_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"PDF File: {self.pdf_filename} for {self.email_date}"
    