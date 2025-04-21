from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("", views.home, name="dashboard-home"),
    path("schedule/", views.generate_schedule_view, name="schedule"),
    path("study-plans/", views.study_plans_view, name="study_plans"),
    path("subjects/", views.subjects_view, name="subjects"),
    path("teachers/", views.teachers_view, name="teachers"),
    path("classes/", views.classes_view, name="classes"),
    path("holidays/", views.holidays_view, name="holidays"),
]
