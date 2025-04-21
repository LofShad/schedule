from django.db import models


class Shift(models.TextChoices):
    FIRST = "1", "Первая"
    SECOND = "2", "Вторая"


class DifficultyLevel(models.TextChoices):
    EASY = "easy", "Лёгкая"
    MEDIUM = "medium", "Средняя"
    HARD = "hard", "Высокая"


class GradeLevel(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)

    def __str__(self):
        return f"{self.number} класс"


class SubjectArea(models.TextChoices):
    LANGUAGE = "language", "Русский язык и литература"
    FOREIGN = "foreign", "Иностранные языки"
    MATH = "math", "Математика и информатика"
    SOCIAL = "social", "Общественно-научные предметы"
    NATURAL = "natural", "Естественнонаучные предметы"
    CULTURE = "culture", "Духовно-нравственная культура"
    ART = "art", "Искусство"
    TECHNOLOGY = "tech", "Технология"
    SPORT = "sport", "Физическая культура и ОБЖ"
    OTHER = "other", "Другое"


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    subject_area = models.CharField(max_length=50, choices=SubjectArea.choices)
    difficulty = models.CharField(
        max_length=10, choices=DifficultyLevel.choices, default=DifficultyLevel.MEDIUM
    )

    def __str__(self):
        return self.name


class StudyPlan(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class StudyPlanEntry(models.Model):
    study_plan = models.ForeignKey(
        StudyPlan, on_delete=models.CASCADE, related_name="entries"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    hours_per_week = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ("study_plan", "subject")

    def __str__(self):
        return (
            f"{self.study_plan.name}: {self.subject.name} — {self.hours_per_week} ч/нед"
        )


class SchoolClass(models.Model):
    grade = models.ForeignKey(GradeLevel, on_delete=models.CASCADE)
    letter = models.CharField(max_length=1)
    shift = models.CharField(max_length=1, choices=Shift.choices)
    study_plan = models.ForeignKey(
        StudyPlan, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        unique_together = ("grade", "letter")

    def __str__(self):
        return f"{self.grade.number}{self.letter}"


class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class SubjectHours(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    hours_per_week = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ("school_class", "subject")


class Lesson(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey("users.Teacher", on_delete=models.CASCADE)
    weekday = models.PositiveSmallIntegerField()  # 1–5 (Пн–Пт)
    lesson_number = models.PositiveSmallIntegerField()  # 1–7
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ("school_class", "weekday", "lesson_number")

    def __str__(self):
        return f"{self.school_class} - {self.subject} ({self.weekday}/{self.lesson_number})"


class Holiday(models.Model):
    date = models.DateField(unique=True)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.date.strftime("%d.%m.%Y")
