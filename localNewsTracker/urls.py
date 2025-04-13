# localNewsTracker/urls.py

from django.urls import path
from . import views # Import views from the current app ('localNewsTracker')

urlpatterns = [
    # Map the root URL of the app ('') to the search_zip view
    path('', views.search_zip, name='search_zip'),
]