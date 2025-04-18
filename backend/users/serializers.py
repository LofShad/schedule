from rest_framework import serializers
from .models import *


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUser
        fields = ["id", "username", "is_staff", "is_superuser"]


class TeacherLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = ["id", "username", "first_name", "last_name", "middle_name"]


class TeacherShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = ["id", "last_name", "first_name", "middle_name"]
