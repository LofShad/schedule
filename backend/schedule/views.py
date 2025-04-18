from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from .models import *
from .serializers import *


class TeacherScheduleView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, teacher_id):
        lessons = Lesson.objects.filter(teacher_id=teacher_id)
        serializer = LessonSerializer(lessons, many=True)
        return Response(serializer.data)


class ClassScheduleView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, class_id):
        lessons = Lesson.objects.filter(school_class_id=class_id)
        serializer = LessonSerializer(lessons, many=True)
        return Response(serializer.data)


class SchoolClassListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        classes = SchoolClass.objects.select_related("grade").all()
        serializer = SchoolClassSerializer(classes, many=True)
        return Response(serializer.data)
