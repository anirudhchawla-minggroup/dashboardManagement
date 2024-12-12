import ast
from datetime import date, datetime
import imaplib
import logging
import os
import time
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from access_gmail import fetch_filtered_emails
from invoice.models import CompanyDetails, InvoiceManagementLog, NewPdfFilesLog, NoCompanyPdfFilesLog
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.utils.dateparse import parse_date

logger = logging.getLogger(__name__)

# Gmail credentials from environment variables
USERNAME = os.getenv("GMAIL_USERNAME")
PASSWORD = os.getenv("GMAIL_PASSWORD")
# Create your views here.
def login(request):
    print("request")
    print(request)
    return render(request, 'users/login.html')

@login_required
def dashboard(request):
    username = request.session.get('username')
    print("username")
    print(username)
    logger.info(f"User: {username} is authenticated")
    return render(request, 'dashboard/dashboard.html', 
                  {'username': username}
                  )

@csrf_exempt
def fetch_pdfs(request):
    # Configure logging
    if request.method == 'POST':
        try:
            # Parse the data sent in the request body
            data = json.loads(request.body)
            print(data)
            selectedOptionsList = data.get("selectedOptionsList")
            from_date = data.get('from_date')
            to_date = data.get('to_date')
            user_name = data.get('user_name')
            # Convert string dates to actual date objects
            since_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            before_date = datetime.strptime(to_date, '%Y-%m-%d').date()
            today = date.today()

            # Check if the from_date or to_date is in the future
            if since_date >= today or before_date >= today:
                return JsonResponse({'status': 'error', 'message': 'You cannot fetch data of current/future date'})
            overlapping_folders = []  # List to collect folders with overlapping logs
            for options in selectedOptionsList:
                keyword = options["value"]
                folder = options["text"]
                
                overlapping_logs = InvoiceManagementLog.objects.filter(
                    company_details__company_short_form=folder, is_active=True
                ).filter(
                    email_date__lte=before_date,  # Log's from_date is before or equal to the given end date
                    email_date__gte=since_date      # Log's to_date is after or equal to the given start date
                )

                if overlapping_logs.exists():
                    overlapping_folders.append(folder)  # Add folder to the list if overlapping logs exist
            print("user_name")
            print(user_name)
            # After the loop, check if there are any overlapping folders
            if overlapping_folders:
                # Convert the list of folders to a comma-separated string
                folder_list_str = ", ".join(overlapping_folders)
                return JsonResponse({'status': 'error', 'message': f'This date range has already been fetched for the following companies: {folder_list_str}. View logs for more information.'})

            # Connect to Gmail's IMAP server
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            print("Connected to IMAP server")
            logger.info(USERNAME)
            logger.info(PASSWORD)
            # Log in to your account
            # Check if either the username or password is missing
            if USERNAME is None or PASSWORD is None:
                logger.info("GMAIL_USERNAME or GMAIL_PASSWORD is not set in the environment variables.")

            # Proceed with the login if both are available
            try:
                mail.login(USERNAME, PASSWORD)
                logger.info("Logged in successfully")
            except Exception as e:
                logger.info(f"Failed to login: {e}")
            print("Logged in successfully")
                # Call your function with the extracted parameters
            total_pdfs = 0
            message = fetch_filtered_emails(mail,selectedOptionsList, since_date, before_date, total_pdfs,user_name)
            # Logout from the server
            if message == "Process done successfully, please check logs":
                mail.logout()
            # Return the formatted messages wrapped in an unordered list
            return JsonResponse({'message': message, 'status' : "success"})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def fetch_logs(request):
    print("svvs")
    log_entries = []
    selected_date = request.GET.get('date')  # Get the date parameter if provided
    print("selected_date")
    print(selected_date)
    company_list = None
    unmatched_pdfs = None
    # Apply the date filter directly in InvoiceManagementLog if a date is provided
    # Filter the logs directly based on selected date from NewPdfFilesLog, if date is provided
    if selected_date:
        all_companies = CompanyDetails.objects.values_list('company_short_form', flat=True)
        # Fetch companies that have logs for the selected date in InvoiceManagementLog
        companies_with_logs = InvoiceManagementLog.objects.filter(
            is_active=True,
            email_date=selected_date  # Filter by the selected email_date in the InvoiceManagementLog
        ).values_list('company_details__company_short_form', flat=True).distinct()

        # Find companies that don't have logs for the selected date
        company_list = list(set(all_companies) - set(companies_with_logs))
        # Get unmatched PDFs from NoCompanyPdfFilesLog for that date and is_active=True
        unmatched_pdfs = NoCompanyPdfFilesLog.objects.filter(
            email_date=selected_date,
            is_active=True
        )
        print("unmatched_pdfs")
        print(unmatched_pdfs)
        # Use prefetch_related to optimize fetching related NewPdfFilesLog entries
        active_logs = InvoiceManagementLog.objects.filter(
            is_active=True,
            pdf_files__email_date=selected_date
        ).distinct().prefetch_related('pdf_files')
    else:
        # Fetch all active logs if no date filter is applied
        active_logs = InvoiceManagementLog.objects.filter(is_active=True).prefetch_related('pdf_files')

    # Iterate over each active log
    for log in active_logs:
        # Get related PDF list and email dates from NewPdfFilesLog, filtered by date if provided
        pdf_logs = NewPdfFilesLog.objects.filter(invoice_log_id=log.id)

        if selected_date:
            pdf_logs = pdf_logs.filter(email_date=selected_date)

        pdf_logs = pdf_logs.values('pdf_filename', 'email_date')

        # Group PDFs by email_date
        email_date_dict = {}
        for pdf in pdf_logs:
            email_date = pdf['email_date']
            if email_date not in email_date_dict:
                email_date_dict[email_date] = []
            email_date_dict[email_date].append(pdf['pdf_filename'])

        # Construct log entries based on email_date (show even if no PDFs)
        if email_date_dict:
            for email_date, pdf_list in email_date_dict.items():
                log_entries.append({
                    'folder': log.company_details.company_short_form,  # Company folder name
                    'total_pdfs': log.total_pdfs,
                    'pdfs_of_this_company': len(pdf_list),  # Number of PDFs for this email date
                    'user_name': log.username_of_person_logged_in,  # User name who logged in
                    'pdf_list': pdf_list,  # List of PDF filenames for this email_date
                    'email_date': log.email_date
                })

    total_pdfs = 0
    if selected_date:
    # Calculate total PDFs
        if len(log_entries) > 0:
            total_pdfs = sum(entry['pdfs_of_this_company'] for entry in log_entries)
            max_total_pdfs = max(entry['total_pdfs'] for entry in log_entries)
            print("max_total_pdfs")
            print(max_total_pdfs)
            # Update each log entry to have the maximum total_pdfs value
            for entry in log_entries:
                entry['total_pdfs'] = max_total_pdfs
    print("log_entries")
    print(unmatched_pdfs)

    # Render the HTML template with the log entries
    rendered_html = render_to_string('invoice/invoice_logs_table.html', {
        'log_entries': log_entries,
        'selected_date': selected_date,
        'company_list': company_list if company_list is not None else None,  # Pass company_list as None if no date selected
        'unmatched_pdfs': unmatched_pdfs if unmatched_pdfs is not None else None,
        })

    return JsonResponse({'log_entries': rendered_html, 'total_pdfs': total_pdfs})

class CustomLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('dashboard')  # Redirect app users to dashboard after logout

def get_company_data(request):
    # Query the CompanyDetails model to get all companies
    companies = CompanyDetails.objects.filter(is_active=True, is_delete=False).values('company_keyword', 'company_short_form')
    
    # Convert data to the required format for the MultiSelect dropdown
    data = [
        {'value': company['company_keyword'], 'text': company['company_short_form']}
        for company in companies
    ]
    
    return JsonResponse({'data': data})
