from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from schedule.models import Subject
from django.contrib.postgres.fields import JSONField

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
LESSONS = [
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "1.5",
    "1.6",
    "1.7",
    "2.1",
    "2.2",
    "2.3",
    "2.4",
    "2.5",
    "2.6",
]


class Teacher(models.Model):
    username = models.CharField(max_length=150, unique=True, default="")
    password = models.CharField(max_length=128, default="password")

    last_name = models.CharField("Фамилия", max_length=50, default="")
    first_name = models.CharField("Имя", max_length=50, default="")
    middle_name = models.CharField("Отчество", max_length=50, default="")
    subjects = models.ManyToManyField(Subject, related_name="teachers")
    work_time = models.JSONField(default=dict)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.username})"


class AdminUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Имя пользователя обязательно")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, password, **extra_fields)


class AdminUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    objects = AdminUserManager()

    def __str__(self):
        return self.username
