from django.contrib import admin
from .models import GradeLevel, SchoolClass, Subject, Room, SubjectHours, Lesson


@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ("number",)
    ordering = ("number",)


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("__str__", "grade", "letter", "shift")
    list_filter = ("shift", "grade")
    search_fields = ("letter",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "subject_area")
    search_fields = ("name",)
    list_filter = ("subject_area",)


@admin.register(SubjectHours)
class SubjectHoursAdmin(admin.ModelAdmin):
    list_display = ("school_class", "subject", "hours_per_week")
    list_filter = ("school_class__grade", "subject")
    search_fields = ("school_class__letter",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "school_class",
        "subject",
        "teacher",
        "weekday",
        "lesson_number",
        "room",
    )
    list_filter = ("weekday", "school_class", "subject", "teacher")
    search_fields = ("school_class__letter", "subject__name", "teacher__full_name")
    ordering = ("school_class", "weekday", "lesson_number")
