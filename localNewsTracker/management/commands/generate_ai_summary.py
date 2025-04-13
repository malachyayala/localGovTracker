# localNewsTracker/management/commands/generate_bill_summaries.py

import time
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q # For complex lookups
from localNewsTracker.models import Bill
from localNewsTracker.ai_utils import generate_summary # Import our new function
import logging

# Configure logging specific to this command if needed, or rely on root config
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates AI summaries for bills that do not have one.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of bills to process (for testing).',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing AI summaries.',
        )
        parser.add_argument(
            '--state',
            type=str,
            default=None,
            help='Process bills only for a specific state code (e.g., AK).',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.5, # Default delay of 1.5 seconds between API calls
            help='Delay in seconds between processing each bill to avoid rate limits.'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        overwrite = options['overwrite']
        state_filter = options['state']
        delay = options['delay']

        if delay < 0.5:
            self.stdout.write(self.style.WARNING("Delay is very short, be mindful of API rate limits."))

        # Build the initial queryset
        bills_to_process = Bill.objects.all()

        # Filter based on options
        if state_filter:
            bills_to_process = bills_to_process.filter(state_code=state_filter.upper())

        if overwrite:
            # Process all bills with full_text (optionally limited by state)
             bills_to_process = bills_to_process.filter(
                 Q(full_text__isnull=False) & ~Q(full_text__exact='') # Ensure full_text exists and is not empty
             )
             self.stdout.write(self.style.WARNING("Overwriting existing summaries."))
        else:
            # Process only bills with full_text but no ai_summary
             bills_to_process = bills_to_process.filter(
                 (Q(ai_summary__isnull=True) | Q(ai_summary__exact='')) & # ai_summary is null or empty
                 Q(full_text__isnull=False) & ~Q(full_text__exact='')      # AND full_text exists
             )
             self.stdout.write("Processing bills without existing summaries.")

        # Apply limit if specified
        if limit is not None:
            bills_to_process = bills_to_process[:limit]

        total_bills = bills_to_process.count()
        if total_bills == 0:
            self.stdout.write(self.style.SUCCESS("No bills found matching the criteria to process."))
            return

        self.stdout.write(f"Found {total_bills} bills to process.")

        processed_count = 0
        success_count = 0
        error_count = 0

        for bill in bills_to_process:
            processed_count += 1
            self.stdout.write(f"Processing bill {processed_count}/{total_bills}: {bill.state_code} {bill.bill_number} ({bill.session_year})...")

            if not bill.full_text:
                self.stdout.write(self.style.WARNING(f"  Skipping - No full text available for {bill.bill_number}."))
                continue

            try:
                summary_text = generate_summary(bill.full_text)

                if summary_text:
                    bill.ai_summary = summary_text
                    bill.save()
                    self.stdout.write(self.style.SUCCESS("  Successfully generated and saved summary."))
                    success_count += 1
                else:
                    self.stdout.write(self.style.WARNING("  Failed to generate summary (API returned None or empty, or text too short)."))
                    error_count += 1

            except Exception as e:
                if "429" in str(e):  # Rate limit error
                    retry_delay = 25  # Default retry delay from API response
                    self.stdout.write(self.style.WARNING(f"  Rate limit hit. Waiting {retry_delay} seconds before next request..."))
                    time.sleep(retry_delay)
                    try:
                        # Retry once after rate limit cooldown
                        summary_text = generate_summary(bill.full_text)
                        if summary_text:
                            bill.ai_summary = summary_text
                            bill.save()
                            self.stdout.write(self.style.SUCCESS("  Successfully generated and saved summary on retry."))
                            success_count += 1
                            continue
                    except Exception as retry_e:
                        logger.error(f"Retry also failed for bill {bill.id}: {retry_e}", exc_info=True)
                
                logger.error(f"Unhandled exception processing bill {bill.id}: {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f"  An unexpected error occurred: {e}"))
                error_count += 1

            # Add longer delay to respect API rate limits
            if total_bills > 1 and processed_count < total_bills:  # Don't sleep after the last one
                sleep_time = 10  # 10 second delay between calls
                self.stdout.write(f"  Waiting {sleep_time} seconds before next request...")
                time.sleep(sleep_time)

        self.stdout.write(self.style.SUCCESS(f"\nFinished processing."))
        self.stdout.write(f"  Successfully generated summaries for: {success_count} bills.")
        self.stdout.write(f"  Failed or skipped summary generation for: {error_count} bills.")