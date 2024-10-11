import json
import os
import urllib.parse

import requests

def call_google_apps_script(base_folder_id,folder_name,pdf_files):
    # Replace with your actual Google Apps Script Web App URL
    url = f'https://script.google.com/macros/s/{os.getenv("GOOGLE_APP_SCRIPT_ID")}/exec'  # Change this to your Web App URL

    # Prepare the payload
    data = {
        'baseFolderId': base_folder_id,
        'folderName': folder_name,
        'pdfFiles': pdf_files  # List of PDFs with 'name' and 'content'
    }
    print("pdfFiles")
    print(len(pdf_files))
    # Send the POST request
    response = requests.post(url, json=data)
    print(response)
    # Check if the request was successful
    if response.status_code == 200:
        result = response.json()
        print(f"Folder Details: {result}")
        return "success"
    else:
        print(f"Error calling Google Apps Script: {response.status_code}")
        return "failure"
