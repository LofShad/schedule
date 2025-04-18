from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import *
from .serializers import *


class TeacherListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        teachers = Teacher.objects.all()
        serializer = TeacherShortSerializer(teachers, many=True)
        return Response(serializer.data)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = AdminUserSerializer(request.user)
        return Response(serializer.data)


class TeacherMeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not isinstance(request.user, Teacher):
            return Response({"detail": "Неверный пользователь"}, status=403)
        serializer = TeacherSerializer(request.user)
        return Response(serializer.data)


class TeacherLoginView(APIView):
    def post(self, request):
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

        refresh = RefreshToken.for_user(teacher)  # работает, даже если не User
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        )
