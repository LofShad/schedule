from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import Lesson, SchoolClass
from .serializers import LessonSerializer, SchoolClassSerializer

class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Lesson.objects.select_related("teacher", "school_class", "subject", "room").all()
    serializer_class = LessonSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.request.query_params.get("teacher_id")
        class_id = self.request.query_params.get("class_id")

        qs = super().get_queryset()
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        return qs


class SchoolClassViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SchoolClass.objects.select_related("grade").all()
    serializer_class = SchoolClassSerializer
    permission_classes = [AllowAny]
