# sepa_generator_for_invoice/management/commands/find_duplicate_ibans.py

import json
from django.core.management.base import BaseCommand
from sepa_generator_for_invoice.models import SupplierDetailsModel

class Command(BaseCommand):
    help = 'Find recipient names with duplicate IBANs and generate a JSON map.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='/Users/anirudhchawla/Downloads/dashboardManagement/sepa_generator_for_invoice/duplicate_ibans.json',
        )

    def handle(self, *args, **options):
        # Query all active and non-deleted suppliers
        suppliers = SupplierDetailsModel.objects.filter(is_active=True, is_delete=False).values('recipient', 'iban')

        # Create a dictionary mapping IBAN to list of recipients
        iban_map = {}
        for supplier in suppliers:
            iban = supplier['iban'].strip().upper()  # Normalize IBAN
            recipient = supplier['recipient'].strip()
            if iban in iban_map:
                if recipient not in iban_map[iban]:
                    iban_map[iban].append(recipient)
            else:
                iban_map[iban] = [recipient]

        # Filter IBANs with more than one recipient
        duplicate_ibans = {iban: recipients for iban, recipients in iban_map.items() if len(recipients) > 1}

        if duplicate_ibans:
            output_json = json.dumps(duplicate_ibans, indent=4, ensure_ascii=False)
            output_path = options.get('output')

            if output_path:
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(output_json)
                    self.stdout.write(self.style.SUCCESS(f"Duplicate IBANs saved to {output_path}"))
                except Exception as e:
                    self.stderr.write(f"Error writing to file {output_path}: {e}")
            else:
                self.stdout.write(output_json)
        else:
            self.stdout.write(self.style.SUCCESS("No duplicate IBANs found."))
