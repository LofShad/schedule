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
WEEKDAYS = list(range(1, 7))       # Mon(1)–Sat(6)
FIRST_SHIFT_SLOTS = list(range(1, 8))   # Lessons 1–7
SECOND_SHIFT_SLOTS = list(range(8, 14)) # Lessons 8–13

class Command(BaseCommand):
    help = 'Generate schedule considering first and second shifts with diagnostics.'

    def handle(self, *args, **options):
        self.stdout.write('Starting schedule generation...')

        # 1) Clear existing lessons
        deleted, _ = Lesson.objects.all().delete()
        self.stdout.write(f'Cleared {deleted} previous lessons.')

        # 2) Load data
        classes = list(SchoolClass.objects.all())
        hours_map = {(sh.school_class_id, sh.subject_id): sh.hours_per_week for sh in SubjectHours.objects.all()}
        teachers = list(Teacher.objects.prefetch_related('subjects').all())
        rooms = list(Room.objects.all())

        # 3) Validate data
        total_slots = {Shift.FIRST: len(WEEKDAYS) * len(FIRST_SHIFT_SLOTS),
                       Shift.SECOND: len(WEEKDAYS) * len(SECOND_SHIFT_SLOTS)}
        errors = False
        # 3.1) Class-subject hours
        for (c_id, s_id), hrs in hours_map.items():
            cls = SchoolClass.objects.get(id=c_id)
            available = total_slots[cls.shift]
            if hrs > available:
                subj = Subject.objects.get(id=s_id)
                self.stderr.write(f'Error: {subj.name} for {cls} requires {hrs}h, only {available} slots available')
                errors = True
        # 3.2) Subject-level resource check
        from collections import defaultdict
        subj_hours = defaultdict(int)
        for (c_id, s_id), hrs in hours_map.items(): subj_hours[s_id] += hrs
        for s_id, total_hrs in subj_hours.items():
            qualified = [t for t in teachers if s_id in {s.id for s in t.subjects.all()}]
            if not qualified:
                subj = Subject.objects.get(id=s_id)
                self.stderr.write(f'Error: no teacher for subject {subj.name}')
                errors = True
                continue
            capacity = sum(t.work_time.get('max_hours_per_week', total_slots[Shift.SECOND]) for t in qualified)
            if total_hrs > capacity:
                subj = Subject.objects.get(id=s_id)
                self.stderr.write(f'Error: {subj.name} needs {total_hrs}h, total teacher capacity {capacity}h')
                errors = True
        if errors:
            self.stderr.write('Data validation failed. Please fix errors and retry.')
            return

        # 4) Build CP-SAT model
        model = cp_model.CpModel()
        y = {}  # y[(class, subject, teacher, day, slot)]
        teacher_subjects = {t.id: {s.id for s in t.subjects.all()} for t in teachers}

        # Create variables per class-subject-teacher-day-slot
        for cls in classes:
            slots = FIRST_SHIFT_SLOTS if cls.shift == Shift.FIRST else SECOND_SHIFT_SLOTS
            for (c_id, s_id), hrs in hours_map.items():
                if c_id != cls.id: continue
                for t in teachers:
                    if s_id not in teacher_subjects[t.id]: continue
                    for d in WEEKDAYS:
                        for l in slots:
                            y[(c_id, s_id, t.id, d, l)] = model.NewBoolVar(
                                f'y_c{c_id}_s{s_id}_t{t.id}_d{d}_l{l}'
                            )

        # 4.1) Hours per plan: sum across teachers, days, slots
        for (c_id, s_id), hrs in hours_map.items():
            vars_h = [var for (c, s, t, d, l), var in y.items() if c==c_id and s==s_id]
            model.Add(sum(vars_h) == hrs)

        # 4.2) One lesson per class per slot
        for cls in classes:
            slots = FIRST_SHIFT_SLOTS if cls.shift == Shift.FIRST else SECOND_SHIFT_SLOTS
            for d in WEEKDAYS:
                for l in slots:
                    vars_c = [var for (c, s, t, dd, ll), var in y.items() if c==cls.id and dd==d and ll==l]
                    model.Add(sum(vars_c) <= 1)

        # 4.3) Teacher constraints: one lesson per slot per shift + weekly load
        for t in teachers:
            max_h = t.work_time.get('max_hours_per_week', total_slots[Shift.SECOND])
            # per shift & slot
            for shift_val in [Shift.FIRST, Shift.SECOND]:
                slots = FIRST_SHIFT_SLOTS if shift_val==Shift.FIRST else SECOND_SHIFT_SLOTS
                classes_in_shift = [cl.id for cl in classes if cl.shift==shift_val]
                for d in WEEKDAYS:
                    for l in slots:
                        vars_t = [var for (c, s, tid, dd, ll), var in y.items()
                                  if tid==t.id and c in classes_in_shift and dd==d and ll==l]
                        model.Add(sum(vars_t) <= 1)
            # weekly load
            vars_week = [var for (c, s, tid, d, l), var in y.items() if tid==t.id]
            model.Add(sum(vars_week) <= max_h)

        # 4.4) No gaps: lessons proceed consecutively per class/day
        for cls in classes:
            slots = FIRST_SHIFT_SLOTS if cls.shift == Shift.FIRST else SECOND_SHIFT_SLOTS
            for d in WEEKDAYS:
                for idx in range(1, len(slots)):
                    l = slots[idx]
                    prev_l = slots[idx-1]
                    v_curr = [var for (c, s, t, dd, ll), var in y.items()
                              if c==cls.id and dd==d and ll==l]
                    v_prev = [var for (c, s, t, dd, ll), var in y.items()
                              if c==cls.id and dd==d and ll==prev_l]
                    model.Add(sum(v_curr) <= sum(v_prev))

        # 5) Solve with logging
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60
        solver.parameters.log_to_stdout = True
        solver.parameters.log_search_progress = True
        solver.parameters.num_search_workers = 8
        status = solver.Solve(model)
        self.stdout.write(f'CP-SAT status: {solver.StatusName(status)}')
        self.stdout.write(solver.ResponseStats())
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self.stderr.write('INFEASIBLE: no solution found.')
            return

        # 6) Save schedule
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
        self.stdout.write(self.style.SUCCESS('Schedule generated successfully with shifts.'))
