from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("api/", include("users.urls")),
    path("api/", include("schedule.urls")),
]
