from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LessonViewSet, SchoolClassViewSet

router = DefaultRouter()
router.register(r"lessons", LessonViewSet, basename="lessons")
router.register(r"classes", SchoolClassViewSet, basename="classes")

urlpatterns = [
    path("", include(router.urls)),
]
