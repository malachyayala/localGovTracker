# localNewsTracker/management/commands/load_legislative_data.py

import csv
import os
import sys
from csv import field_size_limit
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date
from localNewsTracker.models import Committee, Sponsor, Bill
from django.db.models import F

# Define expected columns for robustness (optional but recommended)
COMMITTEE_COLS = ['Committee Name', 'URL', 'Bills Count', 'RSS URL', 'Chamber', 'State']
SPONSOR_COLS = ['Name', 'Party', 'URL', 'Bills Count', 'RSS URL', 'Chamber', 'State']
MONITORED_BILL_COLS = ['Bill Number', 'Bill URL', 'Summary', 'Text URL', 'State', 'Bill Text']
ACTIVE_BILL_COLS = ['Bill Number', 'Bill URL', 'Summary', 'Action', 'Action URL', 'Date', 'State', 'Bill Text']
VIEWED_BILL_COLS = ['Bill Number', 'Bill URL', 'Summary', 'Text URL', 'State', 'Bill Text'] # Assuming same structure as monitored

# Define the base directory where state folders are located
BASE_DATA_DIR = '/Users/mj/Desktop/Misc/VSCodeStuff/AIHackweek/legiscan_data_selenium'

class Command(BaseCommand):
    help = 'Loads legislative data for a specific state and year from a predefined directory structure.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Increase CSV field size limit
        maxInt = sys.maxsize
        while True:
            try:
                field_size_limit(maxInt)
                break
            except OverflowError:
                maxInt = int(maxInt/10)
                continue

    def add_arguments(self, parser):
        # Keep only essential arguments
        parser.add_argument('--state', type=str, required=True, help='State code (e.g., AK) to load data for.')
        parser.add_argument('--year', type=int, required=True, help='Legislative session year (e.g., 2025)')

    def handle(self, *args, **options):
        state_code = options['state'].upper()
        session_year = options['year']

        self.stdout.write(f"Attempting to load data for state: {state_code}, year: {session_year}")
        self.stdout.write(f"Base data directory: {BASE_DATA_DIR}")

        # Construct the state-specific directory path
        state_dir = os.path.join(BASE_DATA_DIR, state_code)
        if not os.path.isdir(state_dir):
             raise CommandError(f"State directory not found: {state_dir}")
        self.stdout.write(f"Looking for CSV files in: {state_dir}")

        # Construct filenames dynamically based on state code
        state_prefix = state_code.lower() # Use lowercase for filenames as per example
        committees_file = os.path.join(state_dir, f"{state_prefix}_committees.csv")
        sponsors_file = os.path.join(state_dir, f"{state_prefix}_sponsors.csv")
        monitored_file = os.path.join(state_dir, f"{state_prefix}_monitored_bills.csv")
        active_file = os.path.join(state_dir, f"{state_prefix}_active_bills.csv")
        viewed_file = os.path.join(state_dir, f"{state_prefix}_viewed_bills.csv")

        # Use atomic transaction for bulk loading
        with transaction.atomic():
            self.load_committees(committees_file, state_code)
            self.load_sponsors(sponsors_file, state_code)
            self.load_bills(monitored_file, state_code, session_year, 'monitored')
            self.load_bills(active_file, state_code, session_year, 'active')
            self.load_bills(viewed_file, state_code, session_year, 'viewed')

        self.stdout.write(self.style.SUCCESS(f'Successfully finished loading data for {state_code} ({session_year})'))

    def _read_csv(self, file_path, expected_cols=None):
        """Helper to read CSV and validate columns."""
        if not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f'File not found: {file_path}. Skipping.'))
            return None
        self.stdout.write(f"Reading file: {file_path}") # Added for confirmation
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                # Handle potential BOM (Byte Order Mark) at the start of some UTF-8 files
                content_start = infile.read(1)
                if content_start != '\ufeff':
                    infile.seek(0) # Go back to start if no BOM

                reader = csv.DictReader(infile)
                # Basic header check
                if expected_cols:
                    missing_cols = [col for col in expected_cols if col not in reader.fieldnames]
                    if missing_cols:
                        self.stdout.write(self.style.ERROR(f'Missing columns in {file_path}. Expected: {expected_cols}, Missing: {missing_cols}. Skipping.'))
                        return None
                return list(reader) # Read all rows into memory
        except Exception as e:
            raise CommandError(f'Error reading CSV file {file_path}: {e}')

    def load_committees(self, file_path, state_code):
        self.stdout.write(f"Loading committees from {file_path}...")
        data = self._read_csv(file_path, COMMITTEE_COLS)
        if data is None: return

        count = 0
        for row in data:
             # Check if state matches (optional, depends on CSV source guarantees)
             if row.get('State', '').strip().upper() != state_code:
                 self.stdout.write(self.style.WARNING(f"Skipping committee row, state mismatch: '{row.get('State')}' != '{state_code}'"))
                 continue

             # Use strip() on values read from CSV
             committee_name = row.get('Committee Name', '').strip()
             if not committee_name:
                 self.stdout.write(self.style.WARNING(f"Skipping committee row with empty name in {file_path}"))
                 continue

             chamber = row.get('Chamber', '').strip()

             Committee.objects.update_or_create(
                 state_code=state_code,
                 chamber=chamber,
                 name=committee_name,
                 defaults={
                     'url': row.get('URL', '').strip() or None,
                     'bills_count': int(row['Bills Count']) if row.get('Bills Count', '').isdigit() else None,
                     'rss_url': row.get('RSS URL', '').strip() or None,
                 }
             )
             count += 1
        self.stdout.write(self.style.SUCCESS(f'Loaded/Updated {count} committees.'))

    def load_sponsors(self, file_path, state_code):
        self.stdout.write(f"Loading sponsors from {file_path}...")
        data = self._read_csv(file_path, SPONSOR_COLS)
        if data is None: return

        count = 0
        for row in data:
             if row.get('State', '').strip().upper() != state_code:
                 self.stdout.write(self.style.WARNING(f"Skipping sponsor row, state mismatch: '{row.get('State')}' != '{state_code}'"))
                 continue

             sponsor_name = row.get('Name', '').strip()
             if not sponsor_name:
                 self.stdout.write(self.style.WARNING(f"Skipping sponsor row with empty name in {file_path}"))
                 continue

             Sponsor.objects.update_or_create(
                 state_code=state_code,
                 name=sponsor_name,
                 defaults={
                     'chamber': row.get('Chamber', '').strip() or None,
                     'party': row.get('Party', '').strip() or None,
                     'url': row.get('URL', '').strip() or None,
                     'bills_count': int(row['Bills Count']) if row.get('Bills Count', '').isdigit() else None,
                     'rss_url': row.get('RSS URL', '').strip() or None,
                 }
             )
             count += 1
        self.stdout.write(self.style.SUCCESS(f'Loaded/Updated {count} sponsors.'))


    def load_bills(self, file_path, state_code, session_year, source_type):
        self.stdout.write(f"Loading bills from {file_path} (type: {source_type})...")
        # Determine expected columns based on source type
        expected_cols = None
        if source_type == 'monitored': expected_cols = MONITORED_BILL_COLS
        elif source_type == 'active': expected_cols = ACTIVE_BILL_COLS
        elif source_type == 'viewed': expected_cols = VIEWED_BILL_COLS

        data = self._read_csv(file_path, expected_cols)
        if data is None: return

        created_count = 0
        updated_count = 0
        view_increment_count = 0

        for row in data:
             if row.get('State', '').strip().upper() != state_code:
                 self.stdout.write(self.style.WARNING(f"Skipping bill row, state mismatch: '{row.get('State')}' != '{state_code}'"))
                 continue

             bill_number = row.get('Bill Number', '').strip()
             if not bill_number:
                 self.stdout.write(self.style.WARNING(f"Skipping row, missing Bill Number in {file_path}"))
                 continue

             # Data specific to source type
             defaults = {
                 'bill_url': row.get('Bill URL', '').strip() or None,
                 'summary': row.get('Summary', '').strip() or None,
                 'text_url': row.get('Text URL', '').strip() or None,
                 # Limit full text size to prevent DB bloat - adjust limit as needed
                 'full_text': (row.get('Bill Text', '').strip()[:10000]) if row.get('Bill Text') else None,
             }

             # Add fields based on source type
             if source_type == 'active':
                 defaults['last_action'] = row.get('Action', '').strip() or None
                 action_date_str = row.get('Date', '').strip()
                 if action_date_str:
                     try:
                         # Attempt parsing common date formats
                         defaults['last_action_date'] = parse_date(action_date_str) # Handles YYYY-MM-DD first
                         if not defaults['last_action_date']: # Try other formats if needed
                             # Add more formats like '%m/%d/%Y', etc. if necessary
                             self.stdout.write(self.style.WARNING(f"Could not parse date '{action_date_str}' with default parser for bill {bill_number}. Skipping date."))
                             defaults['last_action_date'] = None
                     except ValueError:
                          self.stdout.write(self.style.WARNING(f"Error parsing date '{action_date_str}' for bill {bill_number}. Skipping date."))
                          defaults['last_action_date'] = None
                 else:
                     defaults['last_action_date'] = None
                 # defaults['last_action_url'] = row.get('Action URL', '').strip() or None # Not in provided CSV

             # Use update_or_create to handle existing bills
             try:
                 bill, created = Bill.objects.update_or_create(
                     state_code=state_code,
                     bill_number=bill_number,
                     session_year=session_year,
                     defaults=defaults
                 )

                 # Update status flags and view count based on source
                 flags_updated = False
                 view_incremented = False

                 if source_type == 'monitored' and not bill.is_monitored:
                     bill.is_monitored = True
                     flags_updated = True
                 elif source_type == 'active' and not bill.is_active:
                     bill.is_active = True
                     flags_updated = True
                 elif source_type == 'viewed':
                     if not bill.is_viewed_source:
                         bill.is_viewed_source = True # Mark it came from this source file
                         flags_updated = True
                     # Increment view count every time it appears in the viewed file
                     bill.view_count = F('view_count') + 1
                     view_incremented = True
                     view_increment_count += 1

                 if flags_updated or view_incremented:
                     bill.save() # Save changes including F() expression evaluation
                     if not created: # Only count as updated if it wasn't just created
                         updated_count += 1

                 if created:
                     created_count += 1
             except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing row for bill {bill_number}: {row}"))
                self.stdout.write(self.style.ERROR(f"  Exception: {e}"))
                # Decide whether to continue or raise CommandError based on severity
                # For now, we'll just report and continue
                continue


        self.stdout.write(self.style.SUCCESS(f'Created {created_count} new bills, updated {updated_count} bills (incremented view count {view_increment_count} times).'))