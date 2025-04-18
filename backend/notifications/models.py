from django.db import models
from users.models import Teacher
from schedule.models import SchoolClass


class FCMToken(models.Model):
    token = models.CharField(max_length=255, unique=True)
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, null=True, blank=True
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
