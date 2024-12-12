import json
from django.core.management.base import BaseCommand
from sepa_generator_for_invoice.models import SupplierDetailsModel

class Command(BaseCommand):
    help = 'Import supplier details from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='/Users/anirudhchawla/Downloads/dashboardManagement/sepa_generator_for_invoice/suppliers_data.json')

    def handle(self, *args, **kwargs):
        json_file = kwargs['json_file']

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stderr.write(f"File not found: {json_file}")
            return
        except json.JSONDecodeError as e:
            self.stderr.write(f"Invalid JSON file: {e}")
            return

        templates = data.get('templates', [])

        for item in templates:
            recipient = item.get('recipient')
            iban = item.get('iban')

            if recipient and iban:
                # Check if a supplier with the same recipient and IBAN already exists
                if not SupplierDetailsModel.objects.filter(recipient=recipient, iban=iban).exists():
                    try:
                        SupplierDetailsModel.objects.create(
                            recipient=recipient,
                            iban=iban,
                        )
                        self.stdout.write(self.style.SUCCESS(f"Added supplier: {recipient} with IBAN: {iban}"))
                    except Exception as e:
                        self.stderr.write(f"Error adding supplier {recipient} with IBAN {iban}: {e}")
                else:
                    self.stdout.write(self.style.WARNING(f"Supplier with recipient '{recipient}' and IBAN '{iban}' already exists."))
            else:
                self.stderr.write(f"Missing recipient or IBAN in item: {item}")