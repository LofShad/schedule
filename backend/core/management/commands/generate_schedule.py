# core/management/commands/generate_schedule.py
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from ortools.sat.python import cp_model

from schedule.models import SchoolClass, SubjectHours, Room, Lesson, Subject, Shift
from users.models import Teacher

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

# Schedule parameters
WEEKDAYS = list(range(1, 7))            # Mon(1)–Sat(6)
FIRST_SHIFT_SLOTS = list(range(1, 8))    # Lessons 1–7
SECOND_SHIFT_SLOTS = list(range(8, 14))  # Lessons 8–13

class Command(BaseCommand):
    help = 'Generate schedule with balanced distribution of lessons per week'

    def handle(self, *args, **options):
        self.stdout.write('Starting balanced schedule generation...')

        # 1) Clear existing lessons
        deleted, _ = Lesson.objects.all().delete()
        self.stdout.write(f'Cleared {deleted} previous lessons.')

        # 2) Load data
        classes = list(SchoolClass.objects.all())
        hours_map = {(sh.school_class_id, sh.subject_id): sh.hours_per_week for sh in SubjectHours.objects.all()}
        teachers = list(Teacher.objects.prefetch_related('subjects').all())
        rooms = list(Room.objects.all())

        # 3) Determine slots per class based on shift
        class_slots = {
            cls.id: FIRST_SHIFT_SLOTS if cls.shift == Shift.FIRST else SECOND_SHIFT_SLOTS
            for cls in classes
        }
        total_slots = {
            Shift.FIRST: len(WEEKDAYS) * len(FIRST_SHIFT_SLOTS),
            Shift.SECOND: len(WEEKDAYS) * len(SECOND_SHIFT_SLOTS)
        }

        # 4) Data validation
        # 4.1) Class-subject hours fit into available slots per shift
        total_slots = {
            Shift.FIRST: len(WEEKDAYS) * len(FIRST_SHIFT_SLOTS),
            Shift.SECOND: len(WEEKDAYS) * len(SECOND_SHIFT_SLOTS)
        }
        errors = False
        for (c_id, s_id), hrs in hours_map.items():
            cls_obj = next(c for c in classes if c.id == c_id)
            available = total_slots[cls_obj.shift]
            if hrs > available:
                subj = Subject.objects.get(id=s_id)
                self.stderr.write(
                    f"Error: {subj.name} for {cls_obj} requires {hrs}h, only {available} slots available"
                )
                errors = True
        # 4.2) Subject-level teacher capacity
        from collections import defaultdict
        subj_hours = defaultdict(int)
        for (c_id, s_id), hrs in hours_map.items():
            subj_hours[s_id] += hrs
        for s_id, need in subj_hours.items():
            qualified = [t for t in teachers if s_id in {subj.id for subj in t.subjects.all()}]
            if not qualified:
                subj = Subject.objects.get(id=s_id)
                self.stderr.write(f"Error: no teachers for subject {subj.name}")
                errors = True
                continue
            capacity = sum(
                t.work_time.get('max_hours_per_week', total_slots[Shift.SECOND])
                for t in qualified
            )
            if need > capacity:
                subj = Subject.objects.get(id=s_id)
                self.stderr.write(
                    f"Error: {subj.name} needs {need}h, total capacity {capacity}h from {len(qualified)} teachers"
                )
                errors = True
        if errors:
            self.stderr.write('Data validation failed. Fix errors and rerun.')
            return

        # 5) Build CP-SAT model
        model = cp_model.CpModel()

        # 5.1) Variables y[(c,s,t,d,l)] and z[(c,s,t)]
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
                    z[(c_id, s_id, t.id)] = model.NewBoolVar(f'z_c{c_id}_s{s_id}_t{t.id}')
                    for d in WEEKDAYS:
                        for l in slots:
                            y[(c_id, s_id, t.id, d, l)] = model.NewBoolVar(
                                f'y_c{c_id}_s{s_id}_t{t.id}_d{d}_l{l}'
                            )
                            model.Add(y[(c_id, s_id, t.id, d, l)] <= z[(c_id, s_id, t.id)])

        # 5.2) One teacher per class-subject
        for (c_id, s_id), hrs in hours_map.items():
            teacher_vars = [z[(c_id, s_id, t.id)] for t in teachers if (c_id, s_id, t.id) in z]
            model.Add(sum(teacher_vars) == 1)

        # 5.3) Hours per plan
        for (c_id, s_id), hrs in hours_map.items():
            lesson_vars = [y[key] for key in y if key[0] == c_id and key[1] == s_id]
            model.Add(sum(lesson_vars) == hrs)

        # 5.4) FGOS: at most one lesson of same subject per day, exactly one if hrs == days
        for (c_id, s_id), hrs in hours_map.items():
            slots = class_slots[c_id]
            for d in WEEKDAYS:
                daily_vars = [y[(c_id, s_id, t.id, d, l)]
                              for t in teachers
                              for l in slots
                              if (c_id, s_id, t.id, d, l) in y]
                model.Add(sum(daily_vars) <= 1)
                if hrs == len(WEEKDAYS):
                    model.Add(sum(daily_vars) == 1)

        # 5.5) One lesson per class per slot
        for cls in classes:
            slots = class_slots[cls.id]
            for d in WEEKDAYS:
                for l in slots:
                    slot_vars = [y[(c, s, t, d, l)] for (c, s, t, dd, ll) in y if c == cls.id and dd == d and ll == l]
                    model.Add(sum(slot_vars) <= 1)

        # 5.6) Teacher constraints: one lesson per slot per shift + weekly load
        for t in teachers:
            max_h = t.work_time.get('max_hours_per_week', total_slots[Shift.SECOND])
            # per shift and slot
            for shift_val in [Shift.FIRST, Shift.SECOND]:
                slots = FIRST_SHIFT_SLOTS if shift_val == Shift.FIRST else SECOND_SHIFT_SLOTS
                cls_ids = [c.id for c in classes if c.shift == shift_val]
                for d in WEEKDAYS:
                    for l in slots:
                        t_vars = [y[(c, s, t.id, d, l)] for (c, s, tid, dd, ll) in y
                                  if tid == t.id and c in cls_ids and dd == d and ll == l]
                        model.Add(sum(t_vars) <= 1)
            # weekly load
            week_vars = [y[var] for var in y if var[2] == t.id]
            model.Add(sum(week_vars) <= max_h)

        # 5.7) No gaps per class/day
        for cls in classes:
            slots = class_slots[cls.id]
            for d in WEEKDAYS:
                for idx in range(1, len(slots)):
                    curr, prev = slots[idx], slots[idx-1]
                    curr_vars = [y[(cls.id, s, t, d, curr)] for (c, s, t, dd, ll) in y
                                 if c == cls.id and dd == d and ll == curr]
                    prev_vars = [y[(cls.id, s, t, d, prev)] for (c, s, t, dd, ll) in y
                                 if c == cls.id and dd == d and ll == prev]
                    model.Add(sum(curr_vars) <= sum(prev_vars))

        # 5.8) Balance lessons across the week (minimize max-min difference)
        Lmax = {}
        Lmin = {}
        for cls in classes:
            slots = class_slots[cls.id]
            # bounds: up to len(slots)
            Lmax[cls.id] = model.NewIntVar(0, len(slots), f'Lmax_c{cls.id}')
            Lmin[cls.id] = model.NewIntVar(0, len(slots), f'Lmin_c{cls.id}')
            for d in WEEKDAYS:
                day_load = [y[(cls.id, s, t, d, l)] for (c, s, t, dd, l) in y
                             if c == cls.id and dd == d]
                model.Add(sum(day_load) <= Lmax[cls.id])
                model.Add(sum(day_load) >= Lmin[cls.id])
        # Objective: minimize total imbalance
        model.Minimize(sum(Lmax[c.id] - Lmin[c.id] for c in classes))

        # 6) Solve with logging
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60
        solver.parameters.log_to_stdout = True
        solver.parameters.log_search_progress = True
        solver.parameters.num_search_workers = 8
        status = solver.Solve(model)

        self.stdout.write(f'CP-SAT status: {solver.StatusName(status)}')
        self.stdout.write(solver.ResponseStats())
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self.stderr.write('No solution found.')
            return

        # 7) Save schedule
        with transaction.atomic():
            for (c_id, s_id, t_id, d, l), var in y.items():
                if solver.Value(var):
                    room = rooms[0] if rooms else None
                    Lesson.objects.create(
                        school_class_id=c_id,
                        subject_id=s_id,
                        teacher_id=t_id,
                        weekday=d,
                        lesson_number=l,
                        room=room,
                    )
        self.stdout.write(self.style.SUCCESS('Balanced schedule generated successfully.'))
