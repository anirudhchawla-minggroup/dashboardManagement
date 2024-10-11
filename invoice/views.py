from datetime import date, datetime
import logging
import os
import time
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.template.loader import render_to_string

from access_gmail import fetch_filtered_emails

# Create your views here.
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def fetch_pdfs(request):
    # Configure logging
    log_file_path = 'invoice/fetch_pdfs_logs.log'
    logging.basicConfig(
        level=logging.INFO,
        filename=log_file_path,
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger()

    if request.method == 'POST':
        try:
            # Parse the data sent in the request body
            data = json.loads(request.body)
            print(data)
            keyword = data.get('keyword')
            folder = data.get('folder')
            from_date = data.get('from_date')
            to_date = data.get('to_date')

            # Convert string dates to actual date objects
            since_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            before_date = datetime.strptime(to_date, '%Y-%m-%d').date()
            today = date.today()

            # Check if the from_date or to_date is in the future
            if since_date > today or before_date > today:
                return JsonResponse({'status': 'error', 'message': 'You cannot fetch data of future date'})

            # Check if the log file contains entries for the same company and date range
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as log_file:
                    for line in log_file:
                        try:
                            # Parse the log entry (Timestamp - INFO - Company, From Date, To Date)
                            _, _, details = line.strip().split(" - ", 2)
                            log_company, log_from_date, log_to_date = details.split(', ')

                            # Convert log dates to date objects
                            log_from_date_obj = datetime.strptime(log_from_date, '%Y-%m-%d').date()
                            log_to_date_obj = datetime.strptime(log_to_date, '%Y-%m-%d').date()

                            # Check if the date ranges overlap or are equal
                            if log_company == folder and (
                                (since_date >= log_from_date_obj and before_date <= log_to_date_obj) or
                                (before_date >= log_from_date_obj and before_date <= log_to_date_obj) or
                                (since_date >= log_from_date_obj and since_date <= log_to_date_obj)
                            ):
                                return JsonResponse({'status': 'error', 'message': f'This date range has already been fetched for {keyword}. View logs for more information.'})
                        except ValueError:
                            continue  # Skip improperly formatted lines

            # Call your function with the extracted parameters
            time.sleep(2)
            message = fetch_filtered_emails(keyword,folder, since_date, before_date)
            logger.info(f"{folder}, {from_date}, {to_date}")
            return JsonResponse({'message': message})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def fetch_logs(request):
    log_entries = []
    log_file_path = 'invoice/fetch_pdfs_logs.log'

    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            for line in f:
                try:
                    timestamp, level, details = line.strip().split(" - ", 2)
                    folder, from_date, to_date = details.split(', ')
                    log_entries.append({
                        'timestamp': timestamp,
                        'folder': folder,
                        'from_date': from_date,
                        'to_date': to_date
                    })
                except ValueError:
                    continue  # Skip improperly formatted lines
    log_entries.reverse()
    rendered_html = render_to_string('invoice_logs_table.html', {'log_entries': log_entries})
    return JsonResponse({'log_entries': rendered_html})