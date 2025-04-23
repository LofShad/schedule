from rest_framework import serializers
from schedule.models import Subject, StudyPlan, StudyPlanEntry, SchoolClass, Holiday, Lesson
from users.models import Teacher

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"

class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = "__all__"

class StudyPlanEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyPlanEntry
        fields = "__all__"

class StudyPlanSerializer(serializers.ModelSerializer):
    entries = StudyPlanEntrySerializer(many=True, read_only=True, source='studyplanentry_set')

    class Meta:
        model = StudyPlan
        fields = ["id", "name", "entries"]

class SchoolClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolClass
        fields = "__all__"

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = "__all__"

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = "__all__"
