from ortools.sat.python import cp_model
from schedule.models import SchoolClass, Subject, SubjectHours, Lesson
from users.models import Teacher
from django.db import transaction
import datetime
import random

DAYS = 6  # Пн–Сб
LESSONS_PER_SHIFT = {
    "1": list(range(1, 8)),  # первая смена: уроки 1–7
    "2": list(range(8, 14)),  # уроки 8–13
}


def generate_schedule():
    model = cp_model.CpModel()

    classes = list(SchoolClass.objects.select_related("grade", "study_plan").all())
    subjects = list(Subject.objects.all())
    subject_index = {s.id: i for i, s in enumerate(subjects)}
    index_to_subject = {i: s for i, s in enumerate(subjects)}
    FAKE_SUBJECT_INDEX = len(subjects)

    teachers = list(Teacher.objects.prefetch_related("subjects").all())
    subject_teachers = {
        subj.id: [t for t in teachers if subj in t.subjects.all()] for subj in subjects
    }

    schedule_vars = {}
    teacher_assignment = {}  # (class_id, subject_id) -> teacher index
    all_teacher_lessons = {}  # (teacher_id, day, lesson) -> BoolVar

    for cls in classes:
        SubjectHours.objects.filter(school_class=cls).delete()
        Lesson.objects.filter(school_class=cls).delete()

        study_plan = cls.study_plan
        if study_plan:
            for row in study_plan.entries.all():
                SubjectHours.objects.create(
                    school_class=cls,
                    subject=row.subject,
                    hours_per_week=row.hours_per_week,
                )

        shift_key = str(cls.shift)
        available_lessons = LESSONS_PER_SHIFT[shift_key]
        available_slots = len(available_lessons) * DAYS
        total_hours = sum(
            p.hours_per_week for p in SubjectHours.objects.filter(school_class=cls)
        )
        print(
            f"Класс {cls}: нужно {total_hours} часов, доступно {available_slots} слотов"
        )

        schedule_vars[cls.id] = {}

        class_subject_ids = set(
            p.subject.id for p in SubjectHours.objects.filter(school_class=cls)
        )
        allowed_subject_indexes = sorted(
            set(subject_index[sid] for sid in class_subject_ids)
        )
        allowed_subject_indexes.append(FAKE_SUBJECT_INDEX)

        print("\n▶ Создание переменных с доменами:")
        for day in range(DAYS):
            for lesson in available_lessons:
                var = model.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(allowed_subject_indexes),
                    f"class{cls.id}_d{day}_l{lesson}",
                )
                schedule_vars[cls.id][(day, lesson)] = var
                print(f"  День {day+1}, урок {lesson} → {allowed_subject_indexes}")

        for subj_id, hours in {
            p.subject.id: p.hours_per_week
            for p in SubjectHours.objects.filter(school_class=cls)
        }.items():
            subj_idx = subject_index[subj_id]
            subject_obj = index_to_subject.get(subj_idx)
            if not subject_obj:
                print(
                    f"⚠️ Ошибка: subject index {subj_idx} не найден в index_to_subject!"
                )
                continue

            print(
                f"\n🔍 Проверка предмета '{subject_obj.name}' (index={subj_idx}) на {hours} ч/нед"
            )
            bools = []
            for (day, lesson), var in schedule_vars[cls.id].items():
                b = model.NewBoolVar(f"cls{cls.id}_subj{subj_id}_d{day}_l{lesson}")
                model.Add(var == subj_idx).OnlyEnforceIf(b)
                model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                bools.append(b)
            model.Add(sum(bools) == hours)

            available_teachers = subject_teachers.get(subj_id, [])
            if available_teachers:
                teacher_vars = []
                for teacher in available_teachers:
                    t_var = model.NewBoolVar(
                        f"assign_cls{cls.id}_subj{subj_id}_teacher{teacher.id}"
                    )
                    teacher_vars.append(t_var)
                model.AddExactlyOne(teacher_vars)
                teacher_assignment[(cls.id, subj_id)] = teacher_vars

    for cls in classes:
        for (day, lesson), var in schedule_vars[cls.id].items():
            for subj_idx, subj in index_to_subject.items():
                if subj_idx == FAKE_SUBJECT_INDEX:
                    continue
                subj_id = subj.id
                if subj_id not in subject_teachers:
                    continue
                teachers_for_subj = subject_teachers[subj_id]
                if not teachers_for_subj:
                    continue
                for t_idx, teacher in enumerate(teachers_for_subj):
                    if (cls.id, subj_id) not in teacher_assignment:
                        continue
                    assign_var = teacher_assignment[(cls.id, subj_id)][t_idx]
                    b = model.NewBoolVar(
                        f"teach_cls{cls.id}_d{day}_l{lesson}_t{teacher.id}"
                    )
                    model.Add(var == subj_idx).OnlyEnforceIf([assign_var, b])
                    model.AddImplication(b, assign_var)

                    key = (teacher.id, day, lesson)
                    if key not in all_teacher_lessons:
                        all_teacher_lessons[key] = model.NewBoolVar(
                            f"busy_t{teacher.id}_d{day}_l{lesson}"
                        )
                    model.AddImplication(b, all_teacher_lessons[key])

    for (t_id, day, lesson), bvar in all_teacher_lessons.items():
        model.Add(
            sum(
                1
                for (tid, d, l), v in all_teacher_lessons.items()
                if tid == t_id and d == day and l == lesson and v is bvar
            )
            <= 1
        )

    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.num_search_workers = 1

    class SolutionPrinter(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self.solution_count = 0

        def on_solution_callback(self):
            self.solution_count += 1

    printer = SolutionPrinter()
    status = solver.Solve(model, printer)
    print(f"Решений найдено: {printer.solution_count}")

    if status not in [cp_model.FEASIBLE, cp_model.OPTIMAL]:
        print("\n=== НЕ УДАЛОСЬ СОСТАВИТЬ РАСПИСАНИЕ ===")
        print(f"status: {status}")
        for cls in classes:
            for (day, lesson), var in schedule_vars[cls.id].items():
                print(f"  День {day + 1}, урок {lesson} → {var}")
        raise Exception("Невозможно составить расписание")

    for cls in classes:
        for (day, lesson), var in schedule_vars[cls.id].items():
            subj_idx = solver.Value(var)
            if subj_idx == FAKE_SUBJECT_INDEX:
                continue
            subject = subjects[subj_idx]
            assigned_teacher = None
            if (cls.id, subject.id) in teacher_assignment:
                teacher_vars = teacher_assignment[(cls.id, subject.id)]
                for i, t_var in enumerate(teacher_vars):
                    if solver.BooleanValue(t_var):
                        assigned_teacher = subject_teachers[subject.id][i]
                        break
            Lesson.objects.create(
                school_class=cls,
                subject=subject,
                teacher=assigned_teacher,
                weekday=day + 1,
                lesson_number=lesson,
            )
