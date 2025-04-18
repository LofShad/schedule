# notifications/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from .models import FCMToken


class FCMSubscribeView(APIView):
    def post(self, request):
        token = request.data.get("token")
        teacher_id = request.data.get("teacher_id")
        class_id = request.data.get("class_id")

        if not token:
            return Response({"error": "FCM token is required"}, status=400)

        fcm_token, created = FCMToken.objects.update_or_create(
            token=token,
            defaults={
                "teacher_id": teacher_id,
                "school_class_id": class_id,
            },
        )

        return Response({"status": "subscribed"})
