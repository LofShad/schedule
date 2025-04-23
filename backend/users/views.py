from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Teacher
from .serializers import TeacherSerializer, TeacherShortSerializer, TeacherLoginSerializer, AdminUserSerializer


class TeacherViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Teacher.objects.all()
    serializer_class = TeacherShortSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], authentication_classes=[JWTAuthentication])
    def me(self, request):
        if not isinstance(request.user, Teacher):
            return Response({"detail": "Неверный пользователь"}, status=403)
        serializer = TeacherSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def login(self, request):
        serializer = TeacherLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        try:
            teacher = Teacher.objects.get(username=username)
        except Teacher.DoesNotExist:
            return Response({"detail": "Неверный логин или пароль"}, status=400)

        if not teacher.check_password(password):
            return Response({"detail": "Неверный логин или пароль"}, status=400)

        refresh = RefreshToken.for_user(teacher)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        )


class MeView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        serializer = AdminUserSerializer(request.user)
        return Response(serializer.data)
