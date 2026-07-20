from django.utils import timezone
from rest_framework import serializers
from .models import CalendarTodo, MeetingAttendee


class MeetingAttendeeSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = MeetingAttendee
        fields = ["id", "user", "user_name"]
        read_only_fields = ["id"]

    def get_user_name(self, obj):
        user = obj.user
        if user.first_name:
            return f"{user.first_name} {user.last_name or ''}".strip()
        return user.email


class CalendarTodoSerializer(serializers.ModelSerializer):
    attendees = MeetingAttendeeSerializer(many=True, read_only=True)
    attendee_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )
    assigned_to_name = serializers.SerializerMethodField()
    contact_name = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = CalendarTodo
        fields = [
            "id",
            "user",
            "todo_type",
            "title",
            "description",
            "priority",
            "start",
            "end",
            "contact",
            "location",
            "status",
            "hold_reason",
            "extension_request",
            "completion_remarks",
            "assigned_to",
            "attendees",
            "attendee_ids",
            "assigned_to_name",
            "contact_name",
            "user_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return None
        user = obj.assigned_to
        if user.first_name:
            return f"{user.first_name} {user.last_name or ''}".strip()
        return user.email

    def get_contact_name(self, obj):
        if not obj.contact:
            return None
        return obj.contact.name or obj.contact.email

    def get_user_name(self, obj):
        user = obj.user
        if user.first_name:
            return f"{user.first_name} {user.last_name or ''}".strip()
        return user.email

    def validate(self, data):
        todo_type = data.get("todo_type", getattr(self.instance, "todo_type", None))

        start_missing = "start" in data and not data.get("start")

        if todo_type == "task":
            if start_missing or (self.instance is None and not data.get("start")):
                raise serializers.ValidationError(
                    {"start": "Deadline is required for tasks."}
                )
            status = data.get("status")
            if status and status not in (
                "assigned",
                "progress",
                "completed",
                "canceled",
                "on_hold",
                "overdue",
                "approved",
            ):
                raise serializers.ValidationError(
                    {"status": f"Invalid status '{status}' for tasks."}
                )

        elif todo_type == "event":
            if not data.get("description"):
                raise serializers.ValidationError(
                    {"description": "Description is required for events."}
                )
            if start_missing or (self.instance is None and not data.get("start")):
                raise serializers.ValidationError(
                    {"start": "Date is required for events."}
                )

        elif todo_type == "followup":
            if start_missing or (self.instance is None and not data.get("start")):
                raise serializers.ValidationError(
                    {"start": "Follow-up date is required."}
                )

        elif todo_type == "meeting":
            if start_missing or (self.instance is None and not data.get("start")):
                raise serializers.ValidationError(
                    {"start": "Date & time is required for meetings."}
                )

        if data.get("start") and data.get("end") and data["start"] >= data["end"]:
            raise serializers.ValidationError(
                {"end": "End time must be after start time."}
            )

        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if (
            instance.todo_type == "task"
            and instance.start
            and instance.status not in ("completed", "on_hold", "approved", "canceled")
        ):
            if instance.start < timezone.now():
                data["status"] = "overdue"
        return data

    def create(self, validated_data):
        attendee_ids = validated_data.pop("attendee_ids", [])
        todo = CalendarTodo.objects.create(**validated_data)

        if todo.todo_type == "meeting" and attendee_ids:
            for uid in attendee_ids:
                MeetingAttendee.objects.create(todo=todo, user_id=uid)

        return todo

    def update(self, instance, validated_data):
        attendee_ids = validated_data.pop("attendee_ids", None)

        new_status = validated_data.get("status")
        start = validated_data.get("start")
        if instance.status == "on_hold" and new_status and new_status != "on_hold":
            validated_data["hold_reason"] = None
        if instance.status == "overdue" and new_status and new_status != "overdue":
            validated_data["extension_request"] = None
        if instance.status == "completed" and new_status and new_status != "completed":
            validated_data["completion_remarks"] = None
        if instance.extension_request and start:
            validated_data["extension_request"] = None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if attendee_ids is not None and instance.todo_type == "meeting":
            instance.attendees.all().delete()
            for uid in attendee_ids:
                MeetingAttendee.objects.create(todo=instance, user_id=uid)

        return instance
