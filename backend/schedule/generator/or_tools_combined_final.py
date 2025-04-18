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
    teacher_assignment = {}
    all_teacher_lessons = {}
    penalty_vars = []

    for cls in classes:

        first_lesson = available_lessons[0]
        empty_first = []
        for day in range(DAYS):
            var = schedule_vars[cls.id][(day, first_lesson)]
            is_empty = model.NewBoolVar(f"empty_first_cls{cls.id}_d{day}")
            model.Add(var == FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_empty)
            model.Add(var != FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_empty.Not())
            empty_first.append(is_empty)
        excess = model.NewIntVar(0, DAYS, f"excess_empty_first_cls{cls.id}")
        model.Add(excess == sum(empty_first) - 2).OnlyEnforceIf(sum(empty_first) > 2)
        model.Add(excess == 0).OnlyEnforceIf(sum(empty_first) <= 2)
        penalty_vars.append(excess)
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

        schedule_vars[cls.id] = {}

        class_subject_ids = set(
            p.subject.id for p in SubjectHours.objects.filter(school_class=cls)
        )

        # 🔹 Мягкое ограничение: равномерное распределение нагрузки по неделе
        for subj_id in class_subject_ids:
            subj_idx = subject_index[subj_id]
            day_counts = []
            for day in range(DAYS):
                bools = []
                for lesson in available_lessons:
                    var = schedule_vars[cls.id][(day, lesson)]
                    b = model.NewBoolVar(f"even_dist_cls{cls.id}_d{day}_subj{subj_id}")
                    model.Add(var == subj_idx).OnlyEnforceIf(b)
                    model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                    bools.append(b)
                total = model.NewIntVar(
                    0, len(bools), f"daily_total_cls{cls.id}_subj{subj_id}_d{day}"
                )
                model.Add(total == sum(bools))
                day_counts.append(total)
            for i in range(1, DAYS):
                diff = model.NewIntVar(-10, 10, f"diff_cls{cls.id}_subj{subj_id}_d{i}")
                model.Add(diff == day_counts[i] - day_counts[i - 1])
                abs_diff = model.NewIntVar(
                    0, 10, f"absdiff_cls{cls.id}_subj{subj_id}_d{i}"
                )
                model.AddAbsEquality(abs_diff, diff)
                penalty_vars.append(abs_diff)

        # 🔹 Понедельник (0) и суббота (5) – больше лёгких предметов
        for day in [0, 5]:
            easy_bools = []
            for lesson in available_lessons:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="easy"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(f"light_cls{cls.id}_d{day}_l{lesson}")
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        easy_bools.append(b)
            total_easy = model.NewIntVar(
                0, len(easy_bools), f"easy_total_cls{cls.id}_d{day}"
            )
            model.Add(total_easy == sum(easy_bools))
            penalty_vars.append(
                -total_easy
            )  # минимизация отрицательного = максимизация лёгких

        # 🔹 Лёгкие предметы — в начале и конце, сложные — в середине
        middle = available_lessons[
            len(available_lessons) // 3 : -len(available_lessons) // 3
        ]
        edges = [l for l in available_lessons if l not in middle]
        for day in range(DAYS):
            for lesson in edges:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="easy"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(
                            f"easy_on_edge_cls{cls.id}_d{day}_l{lesson}"
                        )
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        penalty_vars.append(-b)

            for lesson in middle:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="hard"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(
                            f"hard_in_middle_cls{cls.id}_d{day}_l{lesson}"
                        )
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        penalty_vars.append(-b)

        # 🔹 Не более 2 пустых первых уроков в неделю

        allowed_subject_indexes = sorted(
            set(subject_index[sid] for sid in class_subject_ids)
        )
        allowed_subject_indexes.append(FAKE_SUBJECT_INDEX)

        for day in range(DAYS):
            for lesson in available_lessons:
                var = model.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(allowed_subject_indexes),
                    f"class{cls.id}_d{day}_l{lesson}",
                )
                schedule_vars[cls.id][(day, lesson)] = var

        for subj_id, hours in {
            p.subject.id: p.hours_per_week
            for p in SubjectHours.objects.filter(school_class=cls)
        }.items():
            subj_idx = subject_index[subj_id]
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

        hard_subject_indexes = [
            subject_index[s.id]
            for s in Subject.objects.filter(difficulty="hard")
            if s.id in subject_index
        ]

        for day in range(DAYS):
            for i in range(1, len(available_lessons)):
                prev_var = schedule_vars[cls.id][(day, available_lessons[i - 1])]
                curr_var = schedule_vars[cls.id][(day, available_lessons[i])]
                for hard_idx in hard_subject_indexes:
                    b1 = model.NewBoolVar(
                        f"hard_seq1_cls{cls.id}_d{day}_l{i}_subj{hard_idx}"
                    )
                    b2 = model.NewBoolVar(
                        f"hard_seq2_cls{cls.id}_d{day}_l{i}_subj{hard_idx}"
                    )
                    model.Add(prev_var == hard_idx).OnlyEnforceIf(b1)
                    model.Add(prev_var != hard_idx).OnlyEnforceIf(b1.Not())
                    model.Add(curr_var == hard_idx).OnlyEnforceIf(b2)
                    model.Add(curr_var != hard_idx).OnlyEnforceIf(b2.Not())
                    model.AddBoolOr([b1.Not(), b2.Not()])

        for day in range(DAYS):
            for i in range(1, len(available_lessons)):
                prev_lesson = available_lessons[i - 1]
                curr_lesson = available_lessons[i]
                prev_var = schedule_vars[cls.id][(day, prev_lesson)]
                curr_var = schedule_vars[cls.id][(day, curr_lesson)]
                is_curr_filled = model.NewBoolVar(
                    f"filled_cls{cls.id}_d{day}_l{curr_lesson}"
                )
                is_prev_filled = model.NewBoolVar(
                    f"filled_cls{cls.id}_d{day}_l{prev_lesson}"
                )
                model.Add(curr_var != FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_curr_filled)
                model.Add(curr_var == FAKE_SUBJECT_INDEX).OnlyEnforceIf(
                    is_curr_filled.Not()
                )
                model.Add(prev_var != FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_prev_filled)
                model.Add(prev_var == FAKE_SUBJECT_INDEX).OnlyEnforceIf(
                    is_prev_filled.Not()
                )
                model.AddImplication(is_curr_filled, is_prev_filled)

            if 7 in available_lessons:
                var7 = schedule_vars[cls.id][(day, 7)]
                is_used = model.NewBoolVar(f"seventh_cls{cls.id}_d{day}")
                model.Add(var7 != FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_used)
                model.Add(var7 == FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_used.Not())
                penalty_vars.append(is_used)

    for cls in classes:
        # 🔹 Мягкое ограничение: равномерное распределение нагрузки по неделе
        for subj_id in class_subject_ids:
            subj_idx = subject_index[subj_id]
            day_counts = []
            for day in range(DAYS):
                bools = []
                for lesson in available_lessons:
                    var = schedule_vars[cls.id][(day, lesson)]
                    b = model.NewBoolVar(f"even_dist_cls{cls.id}_d{day}_subj{subj_id}")
                    model.Add(var == subj_idx).OnlyEnforceIf(b)
                    model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                    bools.append(b)
                total = model.NewIntVar(
                    0, len(bools), f"daily_total_cls{cls.id}_subj{subj_id}_d{day}"
                )
                model.Add(total == sum(bools))
                day_counts.append(total)
            for i in range(1, DAYS):
                diff = model.NewIntVar(-10, 10, f"diff_cls{cls.id}_subj{subj_id}_d{i}")
                model.Add(diff == day_counts[i] - day_counts[i - 1])
                abs_diff = model.NewIntVar(
                    0, 10, f"absdiff_cls{cls.id}_subj{subj_id}_d{i}"
                )
                model.AddAbsEquality(abs_diff, diff)
                penalty_vars.append(abs_diff)

        # 🔹 Понедельник (0) и суббота (5) – больше лёгких предметов
        for day in [0, 5]:
            easy_bools = []
            for lesson in available_lessons:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="easy"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(f"light_cls{cls.id}_d{day}_l{lesson}")
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        easy_bools.append(b)
            total_easy = model.NewIntVar(
                0, len(easy_bools), f"easy_total_cls{cls.id}_d{day}"
            )
            model.Add(total_easy == sum(easy_bools))
            penalty_vars.append(
                -total_easy
            )  # минимизация отрицательного = максимизация лёгких

        # 🔹 Лёгкие предметы — в начале и конце, сложные — в середине
        middle = available_lessons[
            len(available_lessons) // 3 : -len(available_lessons) // 3
        ]
        edges = [l for l in available_lessons if l not in middle]
        for day in range(DAYS):
            for lesson in edges:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="easy"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(
                            f"easy_on_edge_cls{cls.id}_d{day}_l{lesson}"
                        )
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        penalty_vars.append(-b)

            for lesson in middle:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="hard"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(
                            f"hard_in_middle_cls{cls.id}_d{day}_l{lesson}"
                        )
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        penalty_vars.append(-b)

        # 🔹 Не более 2 пустых первых уроков в неделю
        first_lesson = available_lessons[0]
        empty_first = []
        for day in range(DAYS):
            var = schedule_vars[cls.id][(day, first_lesson)]
            is_empty = model.NewBoolVar(f"empty_first_cls{cls.id}_d{day}")
            model.Add(var == FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_empty)
            model.Add(var != FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_empty.Not())
            empty_first.append(is_empty)
        excess = model.NewIntVar(0, DAYS, f"excess_empty_first_cls{cls.id}")
        model.Add(excess == sum(empty_first) - 2).OnlyEnforceIf(sum(empty_first) > 2)
        model.Add(excess == 0).OnlyEnforceIf(sum(empty_first) <= 2)
        penalty_vars.append(excess)
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

    model.Minimize(sum(penalty_vars))

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
        raise Exception("Невозможно составить расписание")

    for cls in classes:
        # 🔹 Мягкое ограничение: равномерное распределение нагрузки по неделе
        for subj_id in class_subject_ids:
            subj_idx = subject_index[subj_id]
            day_counts = []
            for day in range(DAYS):
                bools = []
                for lesson in available_lessons:
                    var = schedule_vars[cls.id][(day, lesson)]
                    b = model.NewBoolVar(f"even_dist_cls{cls.id}_d{day}_subj{subj_id}")
                    model.Add(var == subj_idx).OnlyEnforceIf(b)
                    model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                    bools.append(b)
                total = model.NewIntVar(
                    0, len(bools), f"daily_total_cls{cls.id}_subj{subj_id}_d{day}"
                )
                model.Add(total == sum(bools))
                day_counts.append(total)
            for i in range(1, DAYS):
                diff = model.NewIntVar(-10, 10, f"diff_cls{cls.id}_subj{subj_id}_d{i}")
                model.Add(diff == day_counts[i] - day_counts[i - 1])
                abs_diff = model.NewIntVar(
                    0, 10, f"absdiff_cls{cls.id}_subj{subj_id}_d{i}"
                )
                model.AddAbsEquality(abs_diff, diff)
                penalty_vars.append(abs_diff)

        # 🔹 Понедельник (0) и суббота (5) – больше лёгких предметов
        for day in [0, 5]:
            easy_bools = []
            for lesson in available_lessons:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="easy"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(f"light_cls{cls.id}_d{day}_l{lesson}")
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        easy_bools.append(b)
            total_easy = model.NewIntVar(
                0, len(easy_bools), f"easy_total_cls{cls.id}_d{day}"
            )
            model.Add(total_easy == sum(easy_bools))
            penalty_vars.append(
                -total_easy
            )  # минимизация отрицательного = максимизация лёгких

        # 🔹 Лёгкие предметы — в начале и конце, сложные — в середине
        middle = available_lessons[
            len(available_lessons) // 3 : -len(available_lessons) // 3
        ]
        edges = [l for l in available_lessons if l not in middle]
        for day in range(DAYS):
            for lesson in edges:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="easy"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(
                            f"easy_on_edge_cls{cls.id}_d{day}_l{lesson}"
                        )
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        penalty_vars.append(-b)

            for lesson in middle:
                var = schedule_vars[cls.id][(day, lesson)]
                for subj in Subject.objects.filter(difficulty="hard"):
                    if subj.id in subject_index:
                        subj_idx = subject_index[subj.id]
                        b = model.NewBoolVar(
                            f"hard_in_middle_cls{cls.id}_d{day}_l{lesson}"
                        )
                        model.Add(var == subj_idx).OnlyEnforceIf(b)
                        model.Add(var != subj_idx).OnlyEnforceIf(b.Not())
                        penalty_vars.append(-b)

        # 🔹 Не более 2 пустых первых уроков в неделю
        first_lesson = available_lessons[0]
        empty_first = []
        for day in range(DAYS):
            var = schedule_vars[cls.id][(day, first_lesson)]
            is_empty = model.NewBoolVar(f"empty_first_cls{cls.id}_d{day}")
            model.Add(var == FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_empty)
            model.Add(var != FAKE_SUBJECT_INDEX).OnlyEnforceIf(is_empty.Not())
            empty_first.append(is_empty)
        excess = model.NewIntVar(0, DAYS, f"excess_empty_first_cls{cls.id}")
        model.Add(excess == sum(empty_first) - 2).OnlyEnforceIf(sum(empty_first) > 2)
        model.Add(excess == 0).OnlyEnforceIf(sum(empty_first) <= 2)
        penalty_vars.append(excess)
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
