from django.db.models import Q
from rest_framework import viewsets, permissions
from .models import CalendarTodo
from .serializers import CalendarTodoSerializer


class CalendarTodoViewSet(viewsets.ModelViewSet):
    serializer_class = CalendarTodoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role in ("Superadmin", "Admin"):
            qs = CalendarTodo.objects.filter(user=user)
        else:
            qs = CalendarTodo.objects.filter(
                Q(assigned_to=user) | Q(attendees__user=user)
            )

        qs = (
            qs.select_related("assigned_to", "contact")
            .prefetch_related("attendees__user")
            .distinct()
        )

        todo_type = self.request.query_params.get("todo_type")
        if todo_type:
            qs = qs.filter(todo_type=todo_type)

        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        if start and end:
            qs = qs.filter(start__gte=start, start__lte=end)
        else:
            if start:
                qs = qs.filter(start__gte=start)
            if end:
                qs = qs.filter(start__lte=end)

        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
