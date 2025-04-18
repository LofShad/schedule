from django import forms
from users.models import *
from schedule.models import *


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name", "subject_area", "difficulty"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "subject_area": forms.Select(attrs={"class": "form-control"}),
            "difficulty": forms.Select(attrs={"class": "form-control"}),
        }


class SchoolClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = ["grade", "letter", "shift", "study_plan"]
        widgets = {
            "grade": forms.Select(attrs={"class": "form-control"}),
            "letter": forms.TextInput(attrs={"class": "form-control"}),
            "shift": forms.Select(attrs={"class": "form-control"}),
            "study_plan": forms.Select(attrs={"class": "form-control"}),
        }

    def save(self, commit=True):
        school_class = super().save(commit)

        SubjectHours.objects.filter(school_class=school_class).delete()
        for entry in school_class.study_plan.entries.all():
            print(f" - {entry.subject.name}: {entry.hours_per_week}")
            SubjectHours.objects.create(
                school_class=school_class,
                subject=entry.subject,
                hours_per_week=entry.hours_per_week,
            )
        return school_class


class TeacherForm(forms.ModelForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=False,
        help_text="Оставьте пустым, чтобы не менять пароль",
    )

    class Meta:
        model = Teacher
        fields = ["username", "password", "last_name", "first_name", "middle_name"]
        widgets = {
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "middle_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance", None)
        super().__init__(*args, **kwargs)

        # Группировка предметов по предметной области
        self.subjects_by_area = {}
        for subj in Subject.objects.all().order_by("subject_area", "name"):
            area = subj.get_subject_area_display()
            self.subjects_by_area.setdefault(area, []).append(subj)

        # Запоминаем выбранные предметы
        self.selected_subjects = (
            [str(s.id) for s in instance.subjects.all()] if instance else []
        )

        # Загружаем рабочее время
        self.initial_work_time = instance.work_time if instance else {}

    def clean(self):
        cleaned_data = super().clean()

        # Обработка рабочего времени
        work_time = {}
        for day in WEEKDAYS:
            lessons = []
            for lesson in LESSONS:
                if f"wt_{day}_{lesson}" in self.data:
                    lessons.append(lesson)
            work_time[day] = lessons
        cleaned_data["work_time"] = work_time

        return cleaned_data

    def save(self, commit=True):
        teacher = super().save(commit=False)
        teacher.work_time = self.cleaned_data["work_time"]

        # Устанавливаем пароль, если был введён
        raw_password = self.cleaned_data.get("password")
        if raw_password:
            teacher.set_password(raw_password)

        if commit:
            teacher.save()
            teacher.subjects.set(self.data.getlist("subjects"))

        return teacher


class StudyPlanEntryForm(forms.ModelForm):
    class Meta:
        model = StudyPlanEntry
        fields = ["subject", "hours_per_week"]
        widgets = {
            "subject": forms.Select(attrs={"class": "form-control"}),
            "hours_per_week": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
        }
