from rest_framework import serializers
from .models import *
from users.serializers import TeacherShortSerializer


class LessonSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="subject.name")
    room = serializers.CharField(source="room.name", default=None)
    teacher = TeacherShortSerializer()
    school_class = serializers.StringRelatedField()

    class Meta:
        model = Lesson
        fields = [
            "id",
            "weekday",
            "lesson_number",
            "subject",
            "teacher",
            "school_class",
            "room",
        ]


class SchoolClassSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = SchoolClass
        fields = ["id", "name"]

    def get_name(self, obj):
        return f"{obj.grade.number}{obj.letter}"
