# sepa_app/views.py

import json
import logging
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from invoice.models import CompanyDetails
from sepa_generator_for_invoice.models import SupplierDetailsModel
from .forms import PDFUploadForm
from lxml import etree
import uuid
from datetime import datetime

def upload_new_pdf_sepa_creation(request):
    if request.method == 'POST':
        # Handle file upload and form submission here
        # ...
        pass  # Replace with your actual logic

    # Fetch all active and non-deleted suppliers
    suppliers = SupplierDetailsModel.objects.filter(is_active=True, is_delete=False).values('recipient', 'iban')
    suppliers_json = json.dumps(list(suppliers))  # Convert QuerySet to JSON
    companies = CompanyDetails.objects.filter(is_active=True, is_delete=False).values('company_short_form')
    companies_json = json.dumps(list(companies))  # Convert QuerySet to JSON
    # Render the HTML template with the log entries
    rendered_html = render_to_string('sepa_generator_for_invoice/generate_sepa_xml_files.html')
    
    return JsonResponse({'html_content': rendered_html, 'suppliers_json': suppliers_json, 'companies_json' : companies_json})

logger = logging.getLogger(__name__)

def strip_whitespace_and_newlines(element):
    # Iterate through child elements
    for elem in element.iter():
        # Strip text and tail
        if elem.text:
            elem.text = elem.text.strip().replace('\n', '').replace('\r', '')
        if elem.tail:
            elem.tail = elem.tail.strip().replace('\n', '').replace('\r', '')
    return element

def generate_sepa_xml(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transactions = data.get("transactions")
            paying_company_short_form = data.get("paying_company")
            company = CompanyDetails.objects.get(company_short_form=paying_company_short_form)
            NSMAP = {
                None: "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03",
                'xsi': "http://www.w3.org/2001/XMLSchema-instance"
            }

            try:
                # Create the root Document element with the desired namespaces
                Document = etree.Element(
                    "{urn:iso:std:iso:20022:tech:xsd:pain.001.001.03}Document",
                    nsmap=NSMAP
                )

                # Add the schemaLocation attribute
                Document.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
                            "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 pain.001.001.03.xsd")

                # Continue building your XML structure...
                print(etree.tostring(Document, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode())

            except Exception as e:
                print("An error occurred while creating the XML document:", e)
            print("transactions")
            print(transactions)
            try:
                CstmrCdtTrfInitn = etree.SubElement(Document, "CstmrCdtTrfInitn")

                # Group Header
                GrpHdr = etree.SubElement(CstmrCdtTrfInitn, "GrpHdr")
                msg_id = str(uuid.uuid4())[:8]  # This gives you '234b7a8e' for example
                etree.SubElement(GrpHdr, "MsgId").text = msg_id  # Unique Message ID
                current_datetime = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
                etree.SubElement(GrpHdr, "CreDtTm").text = current_datetime
                etree.SubElement(GrpHdr, "NbOfTxs").text = str(len(transactions))
                total_sum = sum(float(tx['InstdAmt'].replace(',', '.')) for tx in transactions)
                etree.SubElement(GrpHdr, "CtrlSum").text = f"{total_sum:.2f}"
                InitgPty = etree.SubElement(GrpHdr, "InitgPty")
                etree.SubElement(InitgPty, "Nm").text = company.company_keyword

                # Payment Information
                PmtInf = etree.SubElement(CstmrCdtTrfInitn, "PmtInf")
                etree.SubElement(PmtInf, "PmtInfId").text = msg_id  # Use same as MsgId or another unique ID
                etree.SubElement(PmtInf, "PmtMtd").text = "TRF"
                etree.SubElement(PmtInf, "BtchBookg").text = "true"
                etree.SubElement(PmtInf, "NbOfTxs").text = str(len(transactions))
                etree.SubElement(PmtInf, "CtrlSum").text = f"{total_sum:.2f}"

                PmtTpInf = etree.SubElement(PmtInf, "PmtTpInf")
                SvcLvl = etree.SubElement(PmtTpInf, "SvcLvl")
                etree.SubElement(SvcLvl, "Cd").text = "SEPA"

                execution_date = datetime.utcnow().strftime("%Y-%m-%d")
                etree.SubElement(PmtInf, "ReqdExctnDt").text = execution_date

                Dbtr = etree.SubElement(PmtInf, "Dbtr")
                etree.SubElement(Dbtr, "Nm").text = company.company_keyword

                DbtrAcct = etree.SubElement(PmtInf, "DbtrAcct")
                Id = etree.SubElement(DbtrAcct, "Id")
                etree.SubElement(Id, "IBAN").text = company.iban

                DbtrAgt = etree.SubElement(PmtInf, "DbtrAgt")
                FinInstnId = etree.SubElement(DbtrAgt, "FinInstnId")
                etree.SubElement(FinInstnId, "BIC").text = company.bic

                etree.SubElement(PmtInf, "ChrgBr").text = "SLEV"

                # Add each Credit Transfer Transaction Information
                for idx, tx in enumerate(transactions, start=1):
                    CdtTrfTxInf = etree.SubElement(PmtInf, "CdtTrfTxInf")

                    PmtId = etree.SubElement(CdtTrfTxInf, "PmtId")
                    end_to_end_id = f"{msg_id[:8]}-{str(idx).zfill(7)}LG0000"
                    etree.SubElement(PmtId, "EndToEndId").text = end_to_end_id

                    Amt = etree.SubElement(CdtTrfTxInf, "Amt")
                    InstdAmt = etree.SubElement(Amt, "InstdAmt", Ccy="EUR")
                    InstdAmt.text = tx['InstdAmt'].replace(',', '.')

                    Cdtr = etree.SubElement(CdtTrfTxInf, "Cdtr")
                    etree.SubElement(Cdtr, "Nm").text = tx['Nm']

                    CdtrAcct = etree.SubElement(CdtTrfTxInf, "CdtrAcct")
                    Id = etree.SubElement(CdtrAcct, "Id")
                    etree.SubElement(Id, "IBAN").text = tx['IBAN']

                    Purp = etree.SubElement(CdtTrfTxInf, "Purp")
                    valid_sepa_code = "SALA" # Replace with 'OTHR' if unspecified or invalid
                    etree.SubElement(Purp, "Cd").text = valid_sepa_code

                    RmtInf = etree.SubElement(CdtTrfTxInf, "RmtInf")
                    custom_purpose_text = tx.get('Purp')  # Use custom text or a default
                    etree.SubElement(RmtInf, "Ustrd").text = custom_purpose_text

                document = strip_whitespace_and_newlines(Document)
                # Generate pretty XML
                xml_bytes = etree.tostring(document, pretty_print=False, xml_declaration=True, encoding='UTF-8')
                response = HttpResponse(xml_bytes, content_type="application/xml")
                return response
                    #return JsonResponse({'message': "File downloaded successfully",'status' : "success"})
            except Exception as e:
                print(f"Error generating XML response: {e}")
                
                # Return a response-like object for errors
                return HttpResponse(
                    f"Error generating XML: {str(e)}",
                    status=500,
                    content_type="text/plain"
                )
            #return xml_bytes
        except Exception as e:
                    return JsonResponse({'error': str(e)}, status=400)


