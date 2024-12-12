import json
import os
import urllib.parse

import requests

def convert_company_data_to_gas_format(company_data):
    formatted_data = {}
    for company, data in company_data.items():
        if data['total_pdfs_of_the_company'] > 0:
            print("countbegins")
            formatted_data[company] = {
                'total_pdfs_of_the_company': data['total_pdfs_of_the_company'],
                'file_info': []
            }
            for file_info in data['file_info']:
                formatted_data[company]['file_info'].append({
                    'file_name': file_info['file_name'],
                    'content': file_info['content'],
                    'email_date': file_info['email_date'].isoformat(),  # Convert datetime to ISO string
                })
    return formatted_data

def call_google_apps_script(base_folder_id,company_data):
    # Replace with your actual Google Apps Script Web App URL
    url = f'https://script.google.com/macros/s/{os.getenv("GOOGLE_APP_SCRIPT_ID")}/exec'  # Change this to your Web App URL

    # Prepare the payload
    data = {
        'baseFolderId': base_folder_id,  # This is your baseFolderId
        'company_data': convert_company_data_to_gas_format(company_data)
    }
    #print("pdfFiles123")
    #print(data)
    #if not data['company_data']:
        # Send the POST request
    response = requests.post(url, json=data)
    #print(response)
    # Check if the request was successful
    if response.status_code == 200:
        result = response.json()
        print(f"Folder Details: {result}")
        return "success"
    else:
        print(f"Error calling Google Apps Script: {response.status_code}")
        return "failure"
    #else:
        #print("There was no need to call google app script code as no data was found")
