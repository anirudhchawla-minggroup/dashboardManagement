# sepa_app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('upload_new_pdf_sepa_creation/', views.upload_new_pdf_sepa_creation, name='upload_new_pdf_sepa_creation'),
    path('generate_sepa_xml/', views.generate_sepa_xml, name='generate_sepa_xml')
]
