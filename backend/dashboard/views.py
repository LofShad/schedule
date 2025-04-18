from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from schedule.or_tools_scheduler import generate_schedule
from schedule.models import *
from users.models import *
from .forms import *
import datetime
from datetime import date, datetime as dt
from calendar import monthrange, month_name

CLASS_TABS = ["5", "6", "7", "8", "9", "10", "10С", "10М", "11", "11С", "11М"]


def home(request):
    return render(request, "dashboard/home.html")


def study_plans_view(request):
    active_tab = request.GET.get("tab", "5")
    study_plan, _ = StudyPlan.objects.get_or_create(name=active_tab)
    entries = StudyPlanEntry.objects.filter(study_plan=study_plan).select_related(
        "subject"
    )

    if request.method == "POST":
        if "delete" in request.POST:
            entry = get_object_or_404(StudyPlanEntry, pk=request.POST.get("delete"))
            entry.delete()
            return redirect(f"?tab={active_tab}")

        form = StudyPlanEntryForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data["subject"]
            hours = form.cleaned_data["hours_per_week"]

            existing = StudyPlanEntry.objects.filter(
                study_plan=study_plan, subject=subject
            ).first()
            if existing:
                existing.hours_per_week = hours
                existing.save()
            else:
                new_entry = form.save(commit=False)
                new_entry.study_plan = study_plan
                new_entry.save()

            return redirect(f'{reverse("study_plans")}?tab={active_tab}')
    else:
        form = StudyPlanEntryForm()

    return render(
        request,
        "dashboard/study_plans.html",
        {
            "tabs": CLASS_TABS,
            "active_tab": active_tab,
            "entries": entries,
            "form": form,
        },
    )


def subjects_view(request):
    subjects = Subject.objects.all().order_by("name")

    edit_id = request.GET.get("edit")
    delete_id = request.GET.get("delete")
    form = None

    if delete_id:
        subject = get_object_or_404(Subject, pk=delete_id)
        subject.delete()
        return redirect("subjects")

    if request.method == "POST":
        instance = (
            Subject.objects.get(pk=request.POST.get("subject_id"))
            if request.POST.get("subject_id")
            else None
        )
        form = SubjectForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return redirect("subjects")
    else:
        if edit_id:
            instance = get_object_or_404(Subject, pk=edit_id)
            form = SubjectForm(instance=instance)
        else:
            form = SubjectForm()

    return render(
        request,
        "dashboard/subjects.html",
        {
            "subjects": subjects,
            "form": form,
            "edit_mode": bool(edit_id),
            "edit_id": edit_id,
        },
    )


def teachers_view(request):
    teachers = (
        Teacher.objects.prefetch_related("subjects")
        .all()
        .order_by("last_name", "first_name")
    )
    edit_id = request.GET.get("edit")
    delete_id = request.GET.get("delete")
    instance = None
    form = None

    if delete_id:
        Teacher.objects.filter(pk=delete_id).delete()
        return redirect("teachers")

    if request.method == "POST":
        instance = (
            Teacher.objects.get(pk=request.POST.get("teacher_id"))
            if request.POST.get("teacher_id")
            else None
        )
        form = TeacherForm(request.POST, instance=instance)
        if form.is_valid():
            teacher = form.save(commit=False)

            # Захешировать пароль, если указан
            password = request.POST.get("password")
            if password:
                teacher.set_password(password)

            teacher.save()
            teacher.subjects.set(request.POST.getlist("subjects"))
            return redirect("teachers")

    else:
        if edit_id:
            instance = Teacher.objects.get(pk=edit_id)
            form = TeacherForm(instance=instance)
        else:
            form = TeacherForm()

    selected_subjects = (
        request.POST.getlist("subjects")
        if request.method == "POST"
        else ([str(s.id) for s in instance.subjects.all()] if instance else [])
    )

    return render(
        request,
        "dashboard/teachers.html",
        {
            "teachers": teachers,
            "form": form,
            "edit_mode": bool(edit_id),
            "edit_id": edit_id,
            "weekdays": WEEKDAYS,
            "lessons": LESSONS,
            "teacher": instance,
            "selected_subjects": selected_subjects,
        },
    )


def classes_view(request):
    classes = SchoolClass.objects.select_related("grade", "study_plan").order_by(
        "grade__number", "letter"
    )

    edit_id = request.GET.get("edit")
    delete_id = request.GET.get("delete")
    form = None

    if delete_id:
        get_object_or_404(SchoolClass, pk=delete_id).delete()
        return redirect("classes")

    if request.method == "POST":
        instance = (
            SchoolClass.objects.get(pk=request.POST.get("class_id"))
            if request.POST.get("class_id")
            else None
        )
        form = SchoolClassForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return redirect("classes")
    else:
        if edit_id:
            instance = get_object_or_404(SchoolClass, pk=edit_id)
            form = SchoolClassForm(instance=instance)
        else:
            form = SchoolClassForm()

    return render(
        request,
        "dashboard/classes.html",
        {
            "classes": classes,
            "form": form,
            "edit_mode": bool(edit_id),
            "edit_id": edit_id,
        },
    )


def holidays_view(request):
    current_year = date.today().year

    if request.method == "POST":
        selected_dates = request.POST.getlist("selected_dates")

        # Преобразуем строки "2025-01-01" в date-объекты
        selected_dates = [
            datetime.datetime.strptime(d, "%Y-%m-%d").date() for d in selected_dates
        ]

        # Удаляем старые даты и сохраняем новые
        Holiday.objects.exclude(date__in=selected_dates).delete()
        for d in selected_dates:
            Holiday.objects.get_or_create(date=d)

    holidays = set(Holiday.objects.values_list("date", flat=True))
    months = generate_months(current_year)

    return render(
        request,
        "dashboard/holidays.html",
        {
            "months": months,
            "holidays": holidays,
            "year": current_year,
        },
    )


def generate_months(year):
    months = []
    for month in range(1, 13):
        name = month_name[month]  # Январь, Февраль и т.д.
        num_days = monthrange(year, month)[1]
        days = [date(year, month, day) for day in range(1, num_days + 1)]
        months.append(
            {
                "name": name,
                "days": days,
                "number": month,
            }
        )
    return months


def generate_schedule_view(request):
    if request.method == "POST":
        try:
            generate_schedule()
            messages.success(request, "Расписание успешно сгенерировано!")
        except Exception as e:
            messages.error(request, f"Ошибка при генерации: {str(e)}")
        return redirect("generate_schedule")

    # Показываем текущее расписание
    all_lessons = Lesson.objects.select_related(
        "school_class", "subject", "teacher", "room"
    ).order_by(
        "school_class__grade__number",
        "school_class__letter",
        "weekday",
        "lesson_number",
    )

    grouped = {}
    max_lessons = {}
    shift_map = {}

    for lesson in all_lessons:
        key = str(lesson.school_class)
        grouped.setdefault(key, []).append(lesson)

        if key not in max_lessons or lesson.lesson_number > max_lessons[key]:
            max_lessons[key] = lesson.lesson_number

        shift_map[key] = lesson.school_class.shift  # '1' или '2'

    return render(
        request,
        "dashboard/generate_schedule.html",
        {"grouped": grouped, "max_lessons": max_lessons, "shift_map": shift_map},
    )
