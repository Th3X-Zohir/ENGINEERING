from rest_framework import serializers
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(
        source='created_by.email', read_only=True
    )

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description',
            'organization', 'created_by', 'created_by_email',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_by', 'created_at', 'updated_at']