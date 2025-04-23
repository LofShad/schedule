from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import TeacherViewSet, MeView

router = DefaultRouter()
router.register(r"teachers", TeacherViewSet, basename="teacher")

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view({'get': 'list'}), name="me"),
    path("", include(router.urls)),
]
