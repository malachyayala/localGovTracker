# localNewsTracker/models.py

from django.db import models
from django.db.models import F # Import F for incrementing view_count

class Committee(models.Model):
    state_code = models.CharField(max_length=2, db_index=True) # e.g., 'AK', 'TX'
    chamber = models.CharField(max_length=50, db_index=True) # e.g., 'House', 'Senate'
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500, null=True, blank=True)
    bills_count = models.IntegerField(null=True, blank=True)
    rss_url = models.URLField(max_length=500, null=True, blank=True)

    class Meta:
        unique_together = ('state_code', 'chamber', 'name') # Ensure uniqueness within a state/chamber

    def __str__(self):
        return f"{self.state_code} {self.chamber} - {self.name}"

class Sponsor(models.Model):
    state_code = models.CharField(max_length=2, db_index=True)
    chamber = models.CharField(max_length=50, db_index=True, null=True, blank=True) # Some sponsors (like Rules Committee) might not have a chamber
    name = models.CharField(max_length=255)
    party = models.CharField(max_length=50, null=True, blank=True) # e.g., 'R', 'D', 'I' or full names
    url = models.URLField(max_length=500, null=True, blank=True)
    bills_count = models.IntegerField(null=True, blank=True)
    rss_url = models.URLField(max_length=500, null=True, blank=True)

    class Meta:
        unique_together = ('state_code', 'name') # Name should be unique within a state

    def __str__(self):
        return f"{self.name} ({self.state_code})"

class Bill(models.Model):
    state_code = models.CharField(max_length=2, db_index=True)
    bill_number = models.CharField(max_length=50, db_index=True)
    session_year = models.IntegerField(db_index=True, null=True, blank=True)
    bill_url = models.URLField(max_length=500, null=True, blank=True)
    summary = models.TextField(null=True, blank=True) # Original summary from CSV
    text_url = models.URLField(max_length=500, null=True, blank=True)
    full_text = models.TextField(null=True, blank=True)

    # Fields primarily from ak_active_bills.csv
    last_action = models.CharField(max_length=255, null=True, blank=True)
    last_action_date = models.DateField(null=True, blank=True)
    last_action_url = models.URLField(max_length=500, null=True, blank=True)

    # --- NEW FIELD ---
    ai_summary = models.TextField(null=True, blank=True) # Field for AI generated summary
    # --- END NEW FIELD ---

    # Flags to track source/status
    is_monitored = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_viewed_source = models.BooleanField(default=False)

    # View Tracking
    view_count = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        unique_together = ('state_code', 'bill_number', 'session_year')
        ordering = ['-view_count', '-last_action_date']

    def __str__(self):
        return f"{self.state_code} {self.bill_number} ({self.session_year or 'N/A'})"