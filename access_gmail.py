import base64
from email.utils import parsedate_to_datetime
import imaplib
import email
from email.header import decode_header
import os
from datetime import datetime as dt
import datetime
import logging
import time
import zipfile
import pytz
from call_google_app_script import call_google_apps_script
import re
import pdfplumber
import io
from invoice.models import CompanyDetails, InvoiceManagementLog, NewPdfFilesLog, NoCompanyPdfFilesLog

GOOGLE_DRIVE_BASE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_BASE_FOLDER_ID")

# Directory to save PDF attachments
SAVE_DIR = "downloaded_pdfs"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename='logs.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def create_save_directory():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"Created directory: {SAVE_DIR}")
    else:
        print(f"Directory already exists: {SAVE_DIR}")

def get_previous_month_date_range():
    today = datetime.date.today()
    first_day_of_current_month = today.replace(day=1)
    
    # Subtract one day to get a date in the previous month
    last_day_previous_month_temp = first_day_of_current_month - datetime.timedelta(days=1)
    
    # Set the first day of the previous month
    first_day_previous_month = last_day_previous_month_temp.replace(day=1)
    
    # Set the last day of the range to be 2 days after the first day of the previous month
    # For a 2-day range: first_day and first_day + 1 day
    last_day_previous_month = first_day_previous_month + datetime.timedelta(days=1)
    
    return last_day_previous_month, last_day_previous_month

def search_emails(mail, since_date, before_date):
    # Format dates as DD-MMM-YYYY (e.g., 01-Sep-2024)
    since_str = since_date.strftime("%d-%b-%Y")
    before_str = (before_date + datetime.timedelta(days=1)).strftime("%d-%b-%Y")  # IMAP BEFORE is exclusive

    # Search criteria
    search_criteria = f'(SINCE "{since_str}" BEFORE "{before_str}")'
    try:
        result, data = mail.search(None, search_criteria)
        if result != "OK":
            logger.error(f"Failed to search emails with criteria: {search_criteria}")
            return []
        email_ids = data[0].split()
        print(f"Found {len(email_ids)} emails from {since_str} to {before_str}")
        return email_ids
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP search error: {e}")
        return []


def fetch_emails(mail, email_ids, current_mailbox, batch_size=20):
    """
    Fetch emails in batches to optimize performance.

    Args:
        mail (imaplib.IMAP4_SSL): Authenticated IMAP connection.
        email_ids (list): List of email IDs to fetch.
        current_mailbox (str): Name of the current mailbox.
        batch_size (int): Number of emails to fetch per batch.

    Returns:
        list: List of tuples (email_id, email.message.Message).
    """
    emails = []
    total_emails = len(email_ids)
    
    for i in range(0, total_emails, batch_size):
        batch_ids = email_ids[i:i + batch_size]
        # Create a comma-separated string of email IDs
        batch_str = ','.join([eid.decode() if isinstance(eid, bytes) else str(eid) for eid in batch_ids])
        
        try:
            print(f"Fetching batch: {batch_str}")
            res, msg_data = mail.fetch(batch_str, "(RFC822)")
            if res != "OK":
                logger.error(f"ERROR fetching messages {batch_str} in mailbox {current_mailbox}")
                continue
            
            email_idx = 0  # Index to track the corresponding batch_id
            for response in msg_data:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    email_id = batch_ids[email_idx]  # Get the corresponding email ID from batch_ids
                    emails.append((email_id, msg))  # Append the tuple (email_id, message)
                    email_idx += 1  # Increment only when a valid email is processed
        
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP fetch error for messages {batch_str} in mailbox {current_mailbox}: {e}")
        except Exception as ex:
            logger.error(f"Unexpected error fetching messages {batch_str} in mailbox {current_mailbox}: {ex}")
    
    return emails


def decode_mime_words(s):
    decoded_fragments = decode_header(s)
    
    decoded_string = ''
    
    for fragment, encoding in decoded_fragments:
        try:
            if isinstance(fragment, bytes):
                # Handle unknown encoding by trying latin1 as fallback
                if encoding in [None, 'unknown-8bit']:
                    decoded_string += fragment.decode('latin1', errors='replace')
                else:
                    decoded_string += fragment.decode(encoding, errors='replace')
            else:
                decoded_string += fragment
        except Exception as e:
            print(f"Error decoding fragment {fragment}: {e}")
            decoded_string += ''  # Add empty string in case of failure to decode

    return decoded_string

# Function to extract email content, handle PDF filenames, and PDFs inside ZIP files
def extract_email_content(msg):
    print("inside_extract_email_content")
    subject = decode_mime_words(msg.get("Subject", ""))
    print(subject)
    #from_email = decode_mime_words(msg.get("From", ""))
    # Initialize body and attachment list
    body = ""
    pdf_files = []  # To store PDF filenames and their bytes
    # Check if the message is multipart
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # If the part is an attachment
            # Check if the part is an attachment or has a filename
            if part.get_filename() or "attachment" in content_disposition or content_type.startswith("application/"):
                filename = part.get_filename()
                print("inside_found_pdf")
                if filename and filename.lower().endswith('.pdf'):
                    try:
                        excluded_keywords = ["extended", "notitle", "manager"]
                        if any(keyword in filename.lower() for keyword in excluded_keywords):
                            print(f"Skipping PDF Filename: {filename} (matches excluded keyword)")
                            continue
                        pdf_bytes = part.get_payload(decode=True)  # Get the PDF bytes
                        pdf_files.append({'filename': filename, 'pdf_bytes': pdf_bytes})
                        print(f"PDF Filename: {filename}")
                    except Exception as e:
                        print(f"Error decoding PDF attachment {filename}: {e}")
                    continue

                # Check if it's a ZIP file
                elif filename and filename.lower().endswith('.zip'):
                    print(f"Found ZIP attachment: {filename}")
                    # Process ZIP file
                    try:
                        zip_bytes = part.get_payload(decode=True)
                        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
                        for file_info in zip_file.infolist():
                            # Check if the ZIP contains PDFs
                            if file_info.filename.lower().endswith('.pdf'):
                                with zip_file.open(file_info) as pdf_file:
                                    excluded_keywords = ["extended", "notitle", "manager"]
                                    if any(keyword in file_info.filename.lower() for keyword in excluded_keywords):
                                        print(f"Skipping PDF Filename: {file_info.filename} (matches excluded keyword)")
                                        continue
                                    pdf_bytes = pdf_file.read()  # Read the PDF bytes from the ZIP
                                    pdf_files.append({'filename': file_info.filename, 'pdf_bytes': pdf_bytes})
                                    print(f"PDF found in ZIP: {file_info.filename}")
                    except zipfile.BadZipFile as e:
                        print(f"Error processing ZIP file {filename}: {e}")
                    except Exception as e:
                        print(f"Error decoding ZIP attachment {filename}: {e}")
                    continue

            # Process text parts of the email
            if content_type == "text/plain":
                print("inside_found_text_plain")
                try:
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except Exception as e:
                    print(f"Error decoding text/plain part: {e}")
                    pass
            elif content_type == "text/html":
                print("inside_found_text_html")
                try:
                    html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    text = re.sub('<[^<]+?>', '', html_content)  # Strip HTML tags
                    body += text
                except Exception as e:
                    print(f"Error decoding text/html part: {e}")
                    pass
    else:
        # If it's a single part email (not multipart)
        content_type = msg.get_content_type()
        if content_type == "text/plain" or content_type == "text/html":
            try:
                body += msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"Error decoding single-part message: {e}")
                pass
# After processing the body (text/plain or text/html)
    body = body.replace(" ", "").replace("\n", "").replace("\r", "")  # Remove all spaces, newlines, and carriage returns
    body_list = list(body)  # Convert the cleaned body into a list of individual characters or words

    # If you want the body as a list of words split by any remaining non-whitespace characters:
    body_list = body.split()  # Splits the text by any whitespace into a list of words
    return body_list, pdf_files


def extract_text_from_attachment_using_pdfplumber_and_ocr(pdf_bytes,filename):
    extracted_lines_for_amount = set()
    
    # Load the PDF bytes into an in-memory file-like object
    try:
        with io.BytesIO(pdf_bytes) as pdf_io:
            with pdfplumber.open(pdf_io) as pdf:
                total_pages = len(pdf.pages)
                print(f"Opened PDF with {total_pages} pages.")
                for page_number, page in enumerate(pdf.pages, start=1):
                    try:
                        #if page_number == 3:
                            #break
                        print(f"Processing page {page_number} with pdfplumber...")
                        # First try extracting text using pdfplumber
                        text = page.extract_text()
                        if text:
                            print(f"Text found on page {page_number} using pdfplumber.")
                            lines = text.lower().splitlines()
                            cleaned_lines = (line.replace(" ", "") for line in lines)  # Use generator for memory efficiency
                            extracted_lines_for_amount.update(cleaned_lines)
                        """else:
                        print(f"No text found on page {page_number}, switching to OCR...")
                        # If no text found, use OCR
                        start_time = time.time()
                        image = page.to_image(resolution=300).original.convert("RGB")
                        # Preprocess the image to improve OCR quality
                        preprocessed_image = preprocess_image(image)
                        # Perform OCR on the preprocessed image
                        ocr_text = pytesseract.image_to_string(preprocessed_image)
                        lines = ocr_text.lower().replace(" ", "").split('\n')
                        extracted_lines_for_amount.extend(lines)
                        end_time = time.time()
                        total_time = end_time - start_time
                        print(f"OCR completed for page {page_number} in {total_time:.2f} seconds.")"""
                    except Exception as e:
                        print(f"Error processing page {page_number}: {e}")
    except Exception as e:
        print(f"Error opening PDF: {e}")
    return sorted(extracted_lines_for_amount)

def find_matching_folder(pdf_text, keyword, folder,body,filename):
    print("filenameinsidematchingfolder")
    print(filename)
    keyword = str(keyword).replace(" ","").lower()
    # Convert folder and pdf_text to lowercase for consistent comparison
    folder_lower = folder.lower()
    pdf_text_lower = [word.lower() for word in pdf_text]
    # Initial keyword check: stop once keyword is found
    is_keyword_in_pdf = any(keyword in word for word in pdf_text_lower)
    print("is_keyword_in_pdf")
    print(is_keyword_in_pdf)
    print(keyword)
    # New check: if folder is "M2" and "Jannowitzbrücke" is found near the keyword
    if "m2" in folder_lower and is_keyword_in_pdf:
        keyword_index = next((i for i, word in enumerate(pdf_text_lower) if keyword in word), -1)
        # Check if "Jannowitzbrücke" is right after or in the same position
        if keyword_index != -1 and keyword_index + 1 < len(pdf_text_lower) and ("jannowitzbrücke" in pdf_text_lower[keyword_index + 1] or "jannowitzbrücke" in pdf_text_lower[keyword_index]):
            print(f"Skipping folder {folder} due to 'Jannowitzbrücke' following keyword.")
            return None  # Skip folder M2 if "Jannowitzbrücke" follows keyword
    # Only proceed with the special logic if "BB Ming I" and keyword is in PDF
    if "bbmingi" in keyword:
        # First, check if folder contains "AR" or "SSC"
        is_ar = "ar" in folder_lower
        is_ssc = "ssc" in folder_lower

        if is_ar or is_ssc:
            # Now check for the additional conditions more efficiently using set lookups
            if any("aroma" in word for word in pdf_text_lower) and is_ar:
                return folder  # Return folder if "aroma" is found and folder has "AR"
            elif any("10625berlin" in word for word in pdf_text_lower) and is_ar and (is_keyword_in_pdf or any("bbming|" in word for word in pdf_text_lower)):
                return folder  # Return folder if "10625Berlin" is found and folder has "AR"
            elif any("de40100900002948531014" in word for word in pdf_text_lower) and is_ar:
                return folder  # Return folder if "DE401009 00002948531014" is found and folder has "AR"
            elif not any("aroma" in word for word in pdf_text_lower) and is_keyword_in_pdf:
                print("insideout")
                print("aroma" not in pdf_text_lower)
                return "SSC"  # If "aroma" is not found, return "SSC"


    if body is not None and "ar" in folder_lower:
        body = str(body[0]).lower()
        print("body12345")
        if "aroma" in body:
            print("finallyes")
            return folder
        
    # General case: keyword is in PDF, and folder doesn't contain "SSC" or "AR"
    if is_keyword_in_pdf and not ("ssc" in folder_lower or "ar" in folder_lower):
        print("cameinside")
        return folder
    
    if "hf" in folder_lower:
        if any("10769berlin" in word for word in pdf_text_lower):
            return folder
    
    # If no conditions match, return None
    return None


def file_already_exists(filename):
    """Check if the file already exists in the downloaded_pdfs directory or any subdirectories."""
    for root, dirs, files in os.walk(SAVE_DIR):
        if filename in files:
            return True
    return False


def save_pdf_attachments(total_pdfs, keyword, folder, pdf_files, mail, email_id, total_pdfs_of_the_company,body,pdf_text,pdf_bytes,filename,formatted_date):
        folder_name = find_matching_folder(pdf_text, keyword, folder,body,filename)
        if folder_name is not None and folder_name == folder:
            total_pdfs_of_the_company += 1
            encoded_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            pdf_files.append({
                'name': filename,
                'email_date': formatted_date,
                'content' : encoded_pdf
            })
        return pdf_files, total_pdfs, total_pdfs_of_the_company

def fetch_filtered_emails(mail,selectedOptionsList, since_date, before_date,total_pdfs,user_name):
    #create_save_directory()
    #since_date, before_date = get_previous_month_date_range()
    print(f"Fetching emails from {since_date} to {before_date}")

    try:
        # Select the "All Mail" mailbox to encompass all emails across labels
        mailbox = '"[Gmail]/All Mail"'
        typ, data = mail.select(mailbox, readonly=False)
        if typ != 'OK':
            logger.error(f"Failed to select mailbox: {mailbox}")
            mail.logout()
            return f"Failed to select mailbox: {mailbox}"
        print(f"Selected mailbox: {mailbox}")
        for options in selectedOptionsList:
            keyword = options["value"]
            folder = options["text"]

            # Remove "_AR" if it exists
            if keyword.endswith('_AR'):
                options["value"] = keyword.replace('_AR', '')

            # Remove "_SSC" if it exists
            elif keyword.endswith('_SSC'):
                options["value"] = keyword.replace('_SSC', '')

            # Continue with the logic for folder and keyword
            print("Processed Keyword:", options["value"])
            print("Folder:", folder)
        print("selectedOptionsList")
        print(selectedOptionsList)
        current_date = since_date
        while current_date <= before_date:
            # Search for emails in the date range within the "All Mail" mailbox
            email_ids = search_emails(mail, current_date, current_date)
            invoice_exists = InvoiceManagementLog.objects.filter(
                email_date__gte=current_date,  # From date greater than or equal to since_date
                email_date__lte=current_date    # To date less than or equal to before_date
            ).filter(
                email_date__lte=current_date,  # Ensure from_date is within the range
                email_date__gte=current_date      # Ensure to_date is within the range
            ).exists()
            print("invoice_exists")
            print(invoice_exists)
            if invoice_exists:
                print("lengthbeforeemail")
                print(len(email_ids))
                filtered_email_ids = email_ids.copy()
                for email_id in email_ids:
                    try:
                        # Retrieve all entries that match the email_id and are active (is_active=True)
                        active_entries = NoCompanyPdfFilesLog.objects.filter(
                            email_id=email_id,
                            is_active=True,
                            email_date__gte=current_date,  # Greater than or equal to since_date
                            email_date__lte=current_date  # Less than or equal to before_date
                        )
                        # If you want to check if any records were found
                        if active_entries.exists():
                            print(f"Found {len(active_entries)} active entries for email ID {email_id}.")
                            for entry in active_entries:
                                print(f"PDF Filename: {entry.pdf_filename}, Email Date: {entry.email_date}")
                        else:
                            print(f"No active entries found for email ID {email_id}.")
                            filtered_email_ids.remove(email_id)
                    except Exception as e:
                        print(f"An error occurred while retrieving data: {e}")
                email_ids = filtered_email_ids
            print("lengthafteremail")
            print(len(email_ids))
            if not email_ids:
                mail.logout()
                return "No emails found in the specified date range."

            # Fetch emails
            start_time = time.time()
            # Find matching folder based on PDF content
            emails = fetch_emails(mail, email_ids, mailbox, batch_size=20)
            end_time = time.time()
            total_time = end_time - start_time
            print(f"Total time to process emails: {total_time:.2f} seconds")
            print(f"Fetched {len(emails)} emails in mailbox: {mailbox}")

            processed_emails = set()  # Set to track processed email IDs
            company_data = {}  # Dictionary to store data for each company
            unmatched_pdfs = []
            total_pdfs = 0
            # Loop over all emails first
            for email_id, msg in emails:
                print("email_id")
                print(email_id)
                """if not str(email_id).__contains__("14243"):
                    continue"""
                body, pdf_files = extract_email_content(msg)
                #print(f"Subject: {subject}")
                #print(f"From: {from_email}")
                print(f"From: {len(pdf_files)}")
                if len(pdf_files) == 0:
                    continue
                    #print(f"PDF Attachments: {pdf_files}")
                try:
                    # Skip the email if it has already been processed
                    if email_id in processed_emails:
                        continue
                    print("Processing email_id: ", email_id)
                    pdf_text = None  # Reset pdf_text for each email
                    # Extract the date from the email
                    try:
                        email_date = None
                        get_all_headers = msg.get_all('Received')
                        if get_all_headers:
                            # Parse the most recent 'Received' header (usually the last hop)
                            last_received_header = get_all_headers[-1]
                            print("last_received_header")
                            print(last_received_header)
                            # Extract the date portion of the 'Received' header
                            for line in last_received_header.splitlines():
                                if ';' in line:
                                    received_date_str = line.split(';')[-1].strip()
                                    email_date = parsedate_to_datetime(received_date_str)
                                    print("insideallheaders")
                                    print(email_date)
                                    local_tz = pytz.timezone('Europe/Berlin') 
                                    formatted_date = email_date.astimezone(local_tz)
                    except Exception as e:
                        logger.error(f"Error parsing date for email: {e}")
                        formatted_date = "Unknown"  # Use "Unknown" if date parsing fails
                    if formatted_date == "Unknown":
                            email_date_str = msg.get('Date')
                            print("email_date")
                            print(email_date_str)
                            email_date = email.utils.parsedate_to_datetime(email_date_str)
                            local_tz = pytz.timezone('Europe/Berlin') 
                            formatted_date = email_date.astimezone(local_tz)
                    print("emailformatted_date")
                    print(formatted_date)
                    for pdf in pdf_files:
                        pdf_matched_to_company = False
                        filenameFound = ''
                        # Process PDF attachments
                        print("filenamefinally")
                        filename = pdf['filename']
                        filename = decode_mime_words(filename)
                        filename = os.path.basename(filename)
                        print(filename)
                        filenameFound = filename
                        pdf_bytes = pdf['pdf_bytes']
                        start_time = time.time()
                        pdf_text = extract_text_from_attachment_using_pdfplumber_and_ocr(pdf_bytes,filename)
                        end_time = time.time()
                        total_time = end_time - start_time
                        if filename.__contains__("-han-kellner") and pdf_text.__contains__("Schichtbericht"):
                            break
                        print(f"Total time to process pdf_text: {total_time:.2f} seconds")
                        total_pdfs += 1
                        try:
                            active_pdf_entries = NewPdfFilesLog.objects.filter(
                                is_active=True,               # Fetch only active records
                                email_date=formatted_date,         # Matching the email_date
                                pdf_filename=filenameFound      # Matching the pdf_filename
                            )
                            # If you want to check if any records were found
                            if active_pdf_entries.exists():
                                for entry in active_pdf_entries:
                                    print(f"PDF Filename: {entry.pdf_filename}, Email Date: {entry.email_date}, Invoice Log: {entry.invoice_log}")
                                continue
                            else:
                                print("No active entries found for the given email date and filename.")
                        except Exception as e:
                            print(f"Error checking filename from newpdffileslog: {e}")
                        # Loop over each company for the current email
                        for options in selectedOptionsList:
                            keyword = options["value"]
                            folder = options["text"]
                            # Initialize data structure for this company if not already done
                            if folder not in company_data:
                                company_data[folder] = {
                                    "total_pdfs_of_the_company": 0,
                                    "file_info": [],
                                }
                            pdf_files_of_this_company = []
                            # Process the current email for the current company
                            total_pdfs_of_the_company = company_data[folder]["total_pdfs_of_the_company"]
                            # Wrap processing in try-except to catch any errors during the PDF extraction
                            try:
                                if pdf_text is not None:
                                    pdf_files_of_this_company,total_pdfs, total_pdfs_of_the_company = save_pdf_attachments(
                                        total_pdfs, keyword, folder, pdf_files_of_this_company, mail, email_id, total_pdfs_of_the_company,body,pdf_text,pdf_bytes,filenameFound,formatted_date
                                    )
                            except Exception as e:
                                print(f"Error processing email {email_id} for company {folder}: {e}")
                                continue  # Skip to the next company if there's an error
                            print(folder)
                            print("pdf_files_of_this_company")
                            print(pdf_files_of_this_company)
                            # If the email contains PDFs for this company
                            if len(pdf_files_of_this_company) > 0:
                                pdf_matched_to_company = True
                                company_data[folder]["total_pdfs_of_the_company"] = total_pdfs_of_the_company
                                for i in pdf_files_of_this_company:
                                    company_data[folder]["file_info"].append({
                                    "file_name": i["name"],
                                    "email_date": i["email_date"],
                                    "email_id": email_id,
                                    "content" : i["content"]
                                })
                                break
                        # If no PDFs were matched to any company, add them to the unmatched list
                        if not pdf_matched_to_company and total_pdfs > 0:
                                if filenameFound != '':
                                    unmatched_pdfs.append({
                                    "file_name": filenameFound,
                                    "email_date": formatted_date,
                                    "email_id": email_id,
                                })

                except Exception as e:
                    print(f"Error processing email {email_id}: {e}")

                # After processing all companies for this email, mark it as processed
                processed_emails.add(email_id)
            # After processing all companies and emails
            total_pdf_verification = sum(company["total_pdfs_of_the_company"] for company in company_data.values())

            """company_data["summary"] = {
                "total_pdfs_after_verification": total_pdf_verification,
                "total_pdfs_found": total_pdfs,
                "unmatched_pdfs": unmatched_pdfs,
                "unmatched_pdfs_length": len(unmatched_pdfs)
            }"""
            print("total_pdfs")
            #print(company_data)
            try:
                for pdf_info in unmatched_pdfs:  # Assuming unmatched_pdfs is a list of dictionaries
                    filename = pdf_info['file_name']  # Extract filename from the dictionary
                    email_date = pdf_info['email_date']  # Extract email_date from the dictionary
                    email_id = pdf_info['email_id']
                    # If email_date is a string, convert it to a datetime object
                    if isinstance(email_date, str):
                        try:
                            email_date = dt.fromisoformat(email_date)  # Assuming the string is in ISO format (like '2024-10-03T16:50:46+02:00')
                        except ValueError:
                            email_date = dt.strptime(email_date, '%Y-%m-%d %H:%M:%S%z')  # Adjust the format if necessary
                    
                    # Now you can use strftime safely
                    formatted_date = email_date.strftime('%Y-%m-%d')

                    # Now save the data
                    pdf_entry, created = NoCompanyPdfFilesLog.objects.get_or_create(
                        email_date=formatted_date,  # Ensure this is the date object
                        email_id=email_id,
                        pdf_filename=filename
                    )
                    if not created:
                        pdf_entry.save()

            except Exception as e:
                print(f"An error occurred while saving PDF entries: {e}")
            print("Logged out successfully")
            #return 'PDFs fetched and processed successfully.',total_pdfs,len(total_pdf_files),total_pdf_files
            # Now that all emails have been processed, save data to the database
            for folder, data in company_data.items():
                try:
                    fileinfo = data["file_info"]
                    pdf_files_of_this_company = data["total_pdfs_of_the_company"]
                    try:
                        company_details = CompanyDetails.objects.get(company_short_form=folder)
                    except CompanyDetails.DoesNotExist:
                        # Handle the case where the company isn't found
                        print(f"Company with short form {folder} not found")
                        company_details = None  # or handle it appropriately
                    if company_details is None:
                        continue
                    # Create a new log entry for this company
                    log_entry = InvoiceManagementLog(
                        email_date=current_date,
                        company_details=company_details,  # ForeignKey to the company
                        total_pdfs=total_pdfs,
                        pdfs_of_the_company=pdf_files_of_this_company,  # Assuming this is the count
                        username_of_person_logged_in=user_name,
                        is_active=True,
                        is_delete=False
                    )
                    log_entry.save()
                    # If there are logs, save individual filenames
                    logs = InvoiceManagementLog.objects.filter(company_details=company_details, email_date=current_date, pdfs_of_the_company__gt=0)
                    if logs.exists():
                        if len(fileinfo) > 0:
                            for info in fileinfo:
                                try:
                                    # Retrieve all matching entries as a queryset
                                    unmatched_files = NoCompanyPdfFilesLog.objects.filter(
                                        email_id=info["email_id"],
                                        pdf_filename=info["file_name"],
                                        is_active=True,
                                    )

                                    # Iterate over the queryset and mark each entry as inactive
                                    for unmatched_file in unmatched_files:
                                        unmatched_file.is_active = False
                                        unmatched_file.save()

                                    if unmatched_files.exists():
                                        print(f"Marked {len(unmatched_files)} entries as inactive for email ID {info['email_id']} and file {info['file_name']}.")
                                    else:
                                        print(f"No matching active entries found for email ID {info['email_id']} and file {info['file_name']}.")

                                except Exception as e:
                                    print(f"An error occurred: {e}")
                                pdf_entry = NewPdfFilesLog(
                                    invoice_log=log_entry,
                                    pdf_filename=info["file_name"],
                                    email_date=info["email_date"]
                                )
                                pdf_entry.save()
                except Exception as e:
                    error_message = f"<li>An error occurred while saving the log entry for {folder}: {e}</li>"
                    print(error_message)
            current_date += datetime.timedelta(days=1)
            call_google_apps_script(os.getenv("GOOGLE_DRIVE_BASE_FOLDER_ID"),company_data)
        return "Process done successfully, please check logs"
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error: {e}")
    except Exception as ex:
        logger.error(f"An error occurred: {ex}")


