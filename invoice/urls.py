# sepa_app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('fetch-pdfs/', views.fetch_pdfs, name='fetch_pdfs'),
    path('fetch_logs/', views.fetch_logs, name='fetch_logs'),  # New route for fetching logs
    path('get-company-data/', views.get_company_data, name='get_company_data'),
]
