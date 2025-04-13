# localNewsTracker/views.py

from django.shortcuts import render
from .zipcodeInfo import get_location_info_from_zip
from .models import Bill # Import the Bill model

def search_zip(request):
    context = {} # Initialize context dictionary
    top_bills = [] # Initialize empty list for bills

    if request.method == 'POST':
        zipcode = request.POST.get('zipcode', '').strip()
        if zipcode:
            # Use the most comprehensive function from your script
            location_data = get_location_info_from_zip(zipcode)
            context['location_info'] = location_data
            context['submitted_zipcode'] = zipcode # Pass back the submitted zip for display

            if location_data and location_data.get('state_code'):
                state_code = location_data['state_code']
                # Query for top 5 viewed bills in this state
                # Assuming you'll load data for the relevant year later
                # For now, let's just filter by state and order by view_count
                top_bills = Bill.objects.filter(state_code=state_code).order_by('-view_count')[:5] # Get top 5
                context['state_code'] = state_code # Pass state code for display
            elif not location_data:
                 context['error_message'] = f"Could not find location information for ZIP code {zipcode}."
            else:
                 context['error_message'] = f"Location found, but no state code available for ZIP {zipcode}."

        else:
            context['error_message'] = "Please enter a ZIP code."

    context['top_bills'] = top_bills # Add bills to context

    # Render the template specific to this app
    return render(request, 'localNewsTracker/search.html', context)