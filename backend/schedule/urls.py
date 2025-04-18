from django.urls import path
from .views import *

urlpatterns = [
    path("teacher/<int:teacher_id>/", TeacherScheduleView.as_view()),
    path("class/<int:class_id>/", ClassScheduleView.as_view()),
    path("classes/", SchoolClassListView.as_view()),
]
