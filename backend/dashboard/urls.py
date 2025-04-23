from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, views_api

router = DefaultRouter()
router.register(r"subjects", views_api.SubjectViewSet)
router.register(r"teachers", views_api.TeacherViewSet)
router.register(r"study-plans", views_api.StudyPlanViewSet)
router.register(r"study-plan-entries", views_api.StudyPlanEntryViewSet)
router.register(r"classes", views_api.SchoolClassViewSet)
router.register(r"holidays", views_api.HolidayViewSet)
router.register(r"lessons", views_api.LessonViewSet)

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("", views.home, name="dashboard-home"),
    path("schedule/", views.generate_schedule_view, name="schedule"),
    path("legacy/", include([
        path("study-plans/", views.study_plans_view, name="study_plans"),
        path("subjects/", views.subjects_view, name="subjects"),
        path("teachers/", views.teachers_view, name="teachers"),
        path("classes/", views.classes_view, name="classes"),
        path("holidays/", views.holidays_view, name="holidays"),
    ])),
    path("api/", include(router.urls)),
]
