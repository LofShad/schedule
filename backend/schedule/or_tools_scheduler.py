import logging
from ortools.sat.python import cp_model
from django.db import transaction

from schedule.models import SchoolClass, SubjectHours, Room, Lesson, Subject, Shift
from users.models import Teacher

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Schedule parameters
WEEKDAYS = list(range(1, 7))  # Mon(1)–Sat(6)
FIRST_SHIFT_SLOTS = list(range(1, 8))  # Lessons 1–7
SECOND_SHIFT_SLOTS = list(range(8, 14))  # Lessons 8–13


def generate_schedule():
    """
    Generate balanced weekly schedule using CP-SAT solver.
    Raises Exception if validation fails or no solution found.
    """
    logger.info("Starting balanced schedule generation...")

    # 1) Clear existing lessons
    deleted, _ = Lesson.objects.all().delete()
    logger.info(f"Cleared {deleted} previous lessons.")

    # 2) Load data
    classes = list(SchoolClass.objects.all())
    hours_map = {
        (sh.school_class_id, sh.subject_id): sh.hours_per_week
        for sh in SubjectHours.objects.all()
    }
    teachers = list(Teacher.objects.prefetch_related("subjects").all())
    rooms = list(Room.objects.all())

    # 3) Determine slots per class based on shift
    class_slots = {
        cls.id: FIRST_SHIFT_SLOTS if cls.shift == Shift.FIRST else SECOND_SHIFT_SLOTS
        for cls in classes
    }
    total_slots = {
        Shift.FIRST: len(WEEKDAYS) * len(FIRST_SHIFT_SLOTS),
        Shift.SECOND: len(WEEKDAYS) * len(SECOND_SHIFT_SLOTS),
    }

    # 4) Data validation
    errors = False
    # 4.1) Class-subject hours fit into available slots per shift
    for (c_id, s_id), hrs in hours_map.items():
        cls_obj = next(c for c in classes if c.id == c_id)
        available = total_slots[cls_obj.shift]
        if hrs > available:
            subj = Subject.objects.get(id=s_id)
            logger.error(
                f"{subj.name} for {cls_obj} requires {hrs}h, only {available} slots available"
            )
            errors = True

    # 4.2) Subject-level teacher capacity
    from collections import defaultdict

    subj_hours = defaultdict(int)
    for (c_id, s_id), hrs in hours_map.items():
        subj_hours[s_id] += hrs
    for s_id, need in subj_hours.items():
        qualified = [t for t in teachers if s_id in {s.id for s in t.subjects.all()}]
        if not qualified:
            subj = Subject.objects.get(id=s_id)
            logger.error(f"No teachers for subject {subj.name}")
            errors = True
            continue
        capacity = sum(
            t.work_time.get("max_hours_per_week", total_slots[Shift.SECOND])
            for t in qualified
        )
        if need > capacity:
            subj = Subject.objects.get(id=s_id)
            logger.error(
                f"{subj.name} needs {need}h, total capacity {capacity}h from {len(qualified)} teachers"
            )
            errors = True

    if errors:
        raise Exception("Data validation failed. Fix errors and rerun.")

    # 5) Build CP-SAT model
    model = cp_model.CpModel()
    y = {}
    z = {}
    teacher_subjects = {t.id: {s.id for s in t.subjects.all()} for t in teachers}
    for cls in classes:
        slots = class_slots[cls.id]
        for (c_id, s_id), hrs in hours_map.items():
            if c_id != cls.id:
                continue
            for t in teachers:
                if s_id not in teacher_subjects[t.id]:
                    continue
                # z enforces one teacher per class-subject
                z[(c_id, s_id, t.id)] = model.NewBoolVar(f"z_c{c_id}_s{s_id}_t{t.id}")
                for d in WEEKDAYS:
                    for l in slots:
                        y[(c_id, s_id, t.id, d, l)] = model.NewBoolVar(
                            f"y_c{c_id}_s{s_id}_t{t.id}_d{d}_l{l}"
                        )
                        model.Add(y[(c_id, s_id, t.id, d, l)] <= z[(c_id, s_id, t.id)])

    # 5.2) One teacher per class-subject
    for (c_id, s_id), hrs in hours_map.items():
        teacher_vars = [
            z[(c_id, s_id, t.id)] for t in teachers if (c_id, s_id, t.id) in z
        ]
        model.Add(sum(teacher_vars) == 1)

    # 5.3) Hours per plan
    for (c_id, s_id), hrs in hours_map.items():
        lesson_vars = [
            var
            for var_key, var in y.items()
            if var_key[0] == c_id and var_key[1] == s_id
        ]
        model.Add(sum(lesson_vars) == hrs)

    # 5.4) FGOS: at most one lesson of same subject per day
    for (c_id, s_id), hrs in hours_map.items():
        slots = class_slots[c_id]
        for d in WEEKDAYS:
            daily_vars = [
                y[(c_id, s_id, t.id, d, l)]
                for t in teachers
                for l in slots
                if (c_id, s_id, t.id, d, l) in y
            ]
            model.Add(sum(daily_vars) <= 1)
            if hrs == len(WEEKDAYS):
                model.Add(sum(daily_vars) == 1)

    # 5.5) One lesson per class per slot
    for cls in classes:
        slots = class_slots[cls.id]
        for d in WEEKDAYS:
            for l in slots:
                slot_vars = [
                    y[key]
                    for key in y
                    if key[0] == cls.id and key[3] == d and key[4] == l
                ]
                model.Add(sum(slot_vars) <= 1)

    # 5.6) Teacher constraints
    for t in teachers:
        max_h = t.work_time.get("max_hours_per_week", total_slots[Shift.SECOND])
        for shift_val in [Shift.FIRST, Shift.SECOND]:
            slots = (
                FIRST_SHIFT_SLOTS if shift_val == Shift.FIRST else SECOND_SHIFT_SLOTS
            )
            cls_ids = [c.id for c in classes if c.shift == shift_val]
            for d in WEEKDAYS:
                for l in slots:
                    t_vars = [
                        y[(c, s, t.id, d, l)]
                        for (c, s, t_id, dd, ll) in y
                        if t_id == t.id and c in cls_ids and dd == d and ll == l
                    ]
                    model.Add(sum(t_vars) <= 1)
        # Weekly load
        week_vars = [var for key, var in y.items() if key[2] == t.id]
        model.Add(sum(week_vars) <= max_h)

    # 5.7) No gaps per class/day
    for cls in classes:
        slots = class_slots[cls.id]
        for d in WEEKDAYS:
            for idx in range(1, len(slots)):
                curr, prev = slots[idx], slots[idx - 1]
                curr_vars = [
                    y[(cls.id, s, t, d, curr)]
                    for (c, s, t, dd, ll) in y
                    if c == cls.id and dd == d and ll == curr
                ]
                prev_vars = [
                    y[(cls.id, s, t, d, prev)]
                    for (c, s, t, dd, ll) in y
                    if c == cls.id and dd == d and ll == prev
                ]
                model.Add(sum(curr_vars) <= sum(prev_vars))

    # 5.8) Balance lessons across the week (minimize imbalance)
    Lmax = {}
    Lmin = {}
    for cls in classes:
        slots = class_slots[cls.id]
        Lmax[cls.id] = model.NewIntVar(0, len(slots), f"Lmax_c{cls.id}")
        Lmin[cls.id] = model.NewIntVar(0, len(slots), f"Lmin_c{cls.id}")
        for d in WEEKDAYS:
            day_vars = [
                y[(cls.id, s, t, d, l)]
                for (c, s, t, dd, l) in y
                if c == cls.id and dd == d
            ]
            model.Add(sum(day_vars) <= Lmax[cls.id])
            model.Add(sum(day_vars) >= Lmin[cls.id])
    model.Minimize(sum(Lmax[c.id] - Lmin[c.id] for c in classes))

    # 6) Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 180
    solver.parameters.log_search_progress = True
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    logger.info(f"CP-SAT status: {solver.StatusName(status)}")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise Exception("No solution found.")

    # 7) Save schedule
    with transaction.atomic():
        for key, var in y.items():
            if solver.Value(var):
                c_id, s_id, t_id, d, l = key
                room = rooms[0] if rooms else None
                Lesson.objects.create(
                    school_class_id=c_id,
                    subject_id=s_id,
                    teacher_id=t_id,
                    weekday=d,
                    lesson_number=l,
                    room=room,
                )
    logger.info("Balanced schedule generated successfully.")
