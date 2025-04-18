from django.urls import path
from .views import FCMSubscribeView

urlpatterns = [
    path("subscribe/", FCMSubscribeView.as_view()),
]
