from rest_framework import serializers
from AdminApp.models import StickyNote


class StickyNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = StickyNote
        fields = [
            "id",
            "content",
            "color",
            "reminder_at",
            "is_completed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
