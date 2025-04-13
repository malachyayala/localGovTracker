# localGovTracker/urls.py (in the inner localGovTracker directory)

from django.contrib import admin
from django.urls import path, include # Add include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include the URLs from 'localNewsTracker', mapping them to the root path ''
    path('', include('localNewsTracker.urls')), # <-- Use your app name here
]