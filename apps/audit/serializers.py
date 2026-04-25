from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'entity_type', 'entity_id',
            'action', 'user', 'user_email',
            'before_state', 'after_state', 'created_at'
        ]