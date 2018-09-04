"""balloon URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from forecast import views as forecast_views
from core import views as core_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('forecast/list/<str:grib_model>/', forecast_views.list_files, name='list'),
    path('ground_altitude/<str:grib_model>/', forecast_views.altitude, name='ground_altitude'),
    path('trajectory/', core_views.trajectory, name='trajectory'),
    path('column/', core_views.column, name='column')
]
