from rest_framework import serializers
from .models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "start",
            "end",
            "is_all_day",
            "priority",
            "location",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        if data.get("start") and data.get("end") and data["start"] >= data["end"]:
            raise serializers.ValidationError(
                {"end": "End time must be after start time."}
            )
        return data
