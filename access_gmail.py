import base64
import imaplib
import email
from email.header import decode_header
import os
import datetime
import logging
import time
from call_google_app_script import call_google_apps_script
from dotenv import load_dotenv
import re
import pdfplumber
import io

# Load environment variables from .env file
load_dotenv()

# Gmail credentials from environment variables
USERNAME = os.getenv("GMAIL_USERNAME")
PASSWORD = os.getenv("GMAIL_PASSWORD")
GOOGLE_DRIVE_BASE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_BASE_FOLDER_ID")

# Directory to save PDF attachments
SAVE_DIR = "downloaded_pdfs"

# Define folder mapping based on keywords in the PDF content
KEYWORD_FOLDER_MAPPING = [
    {"keywords": ["ming investment consulting"], "folder": "MIC"},
    {"keywords": ["ktv bar"], "folder": "KTV"},
    {"keywords": ["han factory"], "folder": "HF"},
    {"keywords": ["wolfstreet management"], "folder": "WSM"},
    {"keywords": ["ming dynastie gmbh"], "folder": "M2"},
    {"keywords": ["ming dynastie jannowitzbrücke"], "folder": "M1"},
    {"keywords": ["han bbq"], "folder": "H1"},
    {"keywords": ["bb ming I GmbH"], "folder": "AR"},
    {"keywords": ["coffee hanjan"], "folder": "HJ"}
]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename='invoice/fetch_pdfs_logs.log',
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
        list: List of email.message.Message objects.
    """
    emails = []
    total_emails = len(email_ids)
    
    for i in range(0, total_emails, batch_size):
        batch_ids = email_ids[i:i + batch_size]
        # Create a space-separated string of email IDs
        batch_str = ','.join([eid.decode() if isinstance(eid, bytes) else str(eid) for eid in batch_ids])
        
        try:
            res, msg_data = mail.fetch(batch_str, "(RFC822)")
            if res != "OK":
                logger.error(f"ERROR fetching messages {batch_str} in mailbox {current_mailbox}")
                continue
            
            for response in msg_data:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    emails.append(msg)
        
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP fetch error for messages {batch_str} in mailbox {current_mailbox}: {e}")
        except Exception as ex:
            logger.error(f"Unexpected error fetching messages {batch_str} in mailbox {current_mailbox}: {ex}")
    
    return emails

def decode_mime_words(s):
    decoded_fragments = decode_header(s)
    
    decoded_string = ''
    
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            decoded_string += fragment.decode(encoding if encoding else 'utf-8')
        else:
            decoded_string += fragment

    return decoded_string

def extract_email_content(msg):
    subject = decode_mime_words(msg.get("Subject", ""))
    from_email = decode_mime_words(msg.get("From", ""))

    # Initialize body
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain":
                try:
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
            elif content_type == "text/html":
                try:
                    html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    text = re.sub('<[^<]+?>', '', html_content)
                    body += text
                except:
                    pass
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain" or content_type == "text/html":
            try:
                body += msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass

    return subject, from_email, body

def extract_text_from_attachment_using_pdfplumber(pdf_bytes):
    extracted_lines_for_amount = []
    
    # Load the PDF bytes into an in-memory file-like object
    with io.BytesIO(pdf_bytes) as pdf_io:
        with pdfplumber.open(pdf_io) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):  # Start page numbering at 1
                text = page.extract_text()
                if text:
                    lines = text.lower().replace(" ","").split('\n')
                    for line in lines:
                        extracted_lines_for_amount.append(line)  # Append the line text
                    break
    return extracted_lines_for_amount

def find_matching_folder(pdf_text,keyword,folder):
    for word in pdf_text:
        if str(keyword).replace(" ","").lower() in word:
            return folder
    return None

def file_already_exists(filename):
    """Check if the file already exists in the downloaded_pdfs directory or any subdirectories."""
    for root, dirs, files in os.walk(SAVE_DIR):
        if filename in files:
            return True
    return False

def save_pdf_attachments(msg, current_mailbox, keyword, folder, pdf_files):
    # Extract the date from the email
    email_date_str = msg.get('Date')
    try:
        email_date = email.utils.parsedate_to_datetime(email_date_str)
        # Format the date in a readable format (e.g., YYYY-MM-DD)
        formatted_date = email_date.strftime("%Y-%m-%d")
    except Exception as e:
        logger.error(f"Error parsing date for email: {e}")
        formatted_date = "Unknown"  # Use "Unknown" if date parsing fails

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition"))
        if part.get_content_maintype() == 'multipart':
            continue
        if 'attachment' in content_disposition and part.get_filename().lower().endswith('.pdf'):
            filename = part.get_filename()
            filename = decode_mime_words(filename)
            filename = os.path.basename(filename)
            pdf_bytes = part.get_payload(decode=True)
            if not pdf_bytes:
                logger.error(f"Failed to decode PDF attachment {filename} from mailbox {current_mailbox}")
                return
            # Extract text from PDF
            start_time = time.time()
            pdf_text = extract_text_from_attachment_using_pdfplumber(pdf_bytes)
            end_time = time.time()
            total_time = end_time - start_time
            print(f"Total time to process pdf_text: {total_time:.2f} seconds")
            start_time = time.time()
            # Find matching folder based on PDF content
            folder_name = find_matching_folder(pdf_text, keyword, folder)
            end_time = time.time()
            total_time = end_time - start_time
            # Save the PDF to the target folder
            if folder_name:
                print(f"Total time to process folder_name: {total_time:.2f} seconds")
                encoded_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                pdf_files.append({
                    'name': filename,
                    'content': encoded_pdf,
                    'email_date': formatted_date  # Append the email date here
                })
    return pdf_files

def fetch_filtered_emails(keyword,folder, since_date, before_date):
    #create_save_directory()
    #since_date, before_date = get_previous_month_date_range()
    print(f"Fetching emails from {since_date} to {before_date}")

    try:
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

        # Select the "All Mail" mailbox to encompass all emails across labels
        mailbox = '"[Gmail]/All Mail"'
        typ, data = mail.select(mailbox, readonly=True)
        if typ != 'OK':
            logger.error(f"Failed to select mailbox: {mailbox}")
            mail.logout()
            return f"Failed to select mailbox: {mailbox}"
        print(f"Selected mailbox: {mailbox}")

        # Search for emails in the date range within the "All Mail" mailbox
        email_ids = search_emails(mail, since_date, before_date)

        if not email_ids:
            print("No emails found in the specified date range.")
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

        # Filter emails based on keywords in subject or body
        pdf_files = []
        for msg in emails:
            save_pdf_attachments(msg, mailbox,keyword,folder,pdf_files)
        print("pdf_files")
        call_google_apps_script(os.getenv("GOOGLE_DRIVE_BASE_FOLDER_ID"),folder,pdf_files)
        # Logout from the server
        mail.logout()
        print("Logged out successfully")
        return 'PDFs fetched and processed successfully.'

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error: {e}")
    except Exception as ex:
        logger.error(f"An error occurred: {ex}")


