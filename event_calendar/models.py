import uuid
from django.db import models
from django.conf import settings


class CalendarTodo(models.Model):
    TODO_TYPES = [
        ("task", "Task"),
        ("event", "Event"),
        ("followup", "Follow Up"),
        ("meeting", "Meeting"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_todos",
    )
    todo_type = models.CharField(max_length=20, choices=TODO_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, blank=True, null=True
    )

    start = models.DateTimeField(blank=True, null=True)
    end = models.DateTimeField(blank=True, null=True)

    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="followups",
    )

    location = models.CharField(max_length=255, blank=True, null=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="todo_assignments",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "event_calendar_todos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_todo_type_display()}] {self.title}"


class MeetingAttendee(models.Model):
    todo = models.ForeignKey(
        CalendarTodo, on_delete=models.CASCADE, related_name="attendees"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = "event_calendar_meeting_attendees"
        unique_together = ["todo", "user"]

    def __str__(self):
        return f"{self.user} -> {self.todo.title}"
