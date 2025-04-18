from ortools.sat.python import cp_model
from schedule.models import SchoolClass, Subject, SubjectHours, Lesson, Room, Holiday
from users.models import Teacher
from django.db import transaction
import datetime

DAYS = 5  # Пн–Пт
LESSONS_PER_SHIFT = {
    "1": list(range(1, 8)),  # первая смена: уроки 1–7
    "2": list(range(8, 14)),  # вторая смена: уроки 8–13
}

DIFFICULTY_WEIGHTS = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
}


def generate_schedule():
    model = cp_model.CpModel()

    subjects = list(Subject.objects.all())
    subject_index = {s.id: i for i, s in enumerate(subjects)}
    index_to_subject = {i: s for s, i in subject_index.items()}

    classes = list(SchoolClass.objects.select_related("grade", "study_plan").all())
    teachers = list(Teacher.objects.prefetch_related("subjects").all())
    subject_teachers = {
        subj.id: [t for t in teachers if subj in t.subjects.all()] for subj in subjects
    }

    rooms = {
        s.id: Room.objects.filter(name__icontains=s.name).first() for s in subjects
    }

    # Получаем выходные (будние даты, выпадающие на праздники)
    holiday_weekdays = set()
    for h in Holiday.objects.all():
        if h.date.weekday() < 5:
            holiday_weekdays.add(h.date.weekday())

    schedule_vars = {}

    for cls in classes:
        available_slots = LESSONS_PER_SHIFT[cls.shift]
        schedule_vars[cls.id] = {}
        for day in range(DAYS):
            if day in holiday_weekdays:
                continue
            for lesson in available_slots:
                schedule_vars[cls.id][(day, lesson)] = model.NewIntVar(
                    0, len(subjects) - 1, f"class{cls.id}_d{day}_l{lesson}"
                )

    # Ограничение: недельная нагрузка по предметам
    for cls in classes:
        hours_dict = {
            p.subject.id: p.hours_per_week
            for p in SubjectHours.objects.filter(school_class=cls)
        }
        for subj_id, hours in hours_dict.items():
            slots = []
            for (day, lesson), var in schedule_vars[cls.id].items():
                if day in holiday_weekdays:
                    continue
                slots.append(var == subject_index[subj_id])
            model.Add(sum(slots) == hours)

    # Ограничение: максимум 2 сложных предмета в день
    for cls in classes:
        hard_ids = [
            s.id for s in subjects if DIFFICULTY_WEIGHTS.get(s.difficulty, 2) == 3
        ]
        hard_indexes = [subject_index[sid] for sid in hard_ids]
        for day in range(DAYS):
            if day in holiday_weekdays:
                continue
            count = []
            for lesson in LESSONS_PER_SHIFT[cls.shift]:
                if (day, lesson) in schedule_vars[cls.id]:
                    for idx in hard_indexes:
                        count.append(schedule_vars[cls.id][(day, lesson)] == idx)
            # model.Add(sum(count) <= 2)

    # Ограничение: учитель не может вести два урока одновременно
    for day in range(DAYS):
        if day in holiday_weekdays:
            continue
        for lesson in range(1, 14):
            for subj in subjects:
                subj_idx = subject_index[subj.id]
                teacher_count = len(subject_teachers[subj.id])
                if teacher_count == 0:
                    print(
                        f"⚠️ Предмет {subj.name} не имеет ни одного учителя! Пропускаем."
                    )
                    continue
                class_slots = []
                for cls in classes:
                    if (day, lesson) in schedule_vars[cls.id]:
                        class_slots.append(
                            schedule_vars[cls.id][(day, lesson)] == subj_idx
                        )
                if class_slots:
                    model.Add(sum(class_slots) <= teacher_count)

    print("Количество классов:", len(classes))
    print("Количество предметов:", len(subjects))
    for cls in classes:
        print(f"\n=== Класс {cls.grade.number}{cls.letter} ===")
        subject_hours = SubjectHours.objects.filter(school_class=cls)
        for sh in subject_hours:
            print(
                f" - {sh.subject.name} ({sh.subject.difficulty}): {sh.hours_per_week} ч"
            )

    print("\n=== Учителя по предметам ===")
    for subj in subjects:
        teachers = subject_teachers[subj.id]
        print(f"{subj.name}: {len(teachers)} учителей")

    print("\n=== Проверка нагрузки учителей ===")
    for subj in subjects:
        teachers_for_subj = subject_teachers[subj.id]
        if not teachers_for_subj:
            print(f"❌ Нет учителей для предмета: {subj.name}")
        else:
            print(
                f"{subj.name}: {len(teachers_for_subj)} уч. — {[f'{t.last_name} ({t.work_time})' for t in teachers_for_subj]}"
            )

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.INFEASIBLE:
        print("Невозможно составить расписание")
        print("Диагностика:")
        print(solver.ResponseStats())

    if status != cp_model.FEASIBLE:
        raise Exception("Невозможно составить расписание")

    with transaction.atomic():
        Lesson.objects.all().delete()

        for cls in classes:
            for (day, lesson), var in schedule_vars[cls.id].items():
                subj_idx = solver.Value(var)
                subject = subjects[subj_idx]
                teachers_for_subj = subject_teachers[subject.id]
                teacher = teachers_for_subj[0] if teachers_for_subj else None
                room = rooms.get(subject.id)

                if teacher:
                    Lesson.objects.create(
                        school_class=cls,
                        subject=subject,
                        teacher=teacher,
                        weekday=day + 1,
                        lesson_number=lesson,
                        room=room,
                    )
