from django.core.management.base import BaseCommand
from schedule.models import GradeLevel


class Command(BaseCommand):
    help = "Создаёт уровни классов от 5 до 11"

    def handle(self, *args, **kwargs):
        for number in range(5, 12):
            obj, created = GradeLevel.objects.get_or_create(number=number)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Создан: {number} класс"))
            else:
                self.stdout.write(f"Уже есть: {number} класс")
