from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),  # <-- вот эта ручка
    path("teacher/login/", TeacherLoginView.as_view(), name="teacher_login"),
    path("teacher/me/", TeacherMeView.as_view(), name="teacher_me"),
    path("teachers/", TeacherListView.as_view()),
]
