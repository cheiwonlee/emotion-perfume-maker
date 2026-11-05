from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/sensor/", permanent=False)),
    path("sensor/", include("sensor.urls")),
    path("admin/", admin.site.urls),
]
