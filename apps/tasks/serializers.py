from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Task, TaskDependency
from .services import has_cycle

User = get_user_model()


class TaskDependencySerializer(serializers.ModelSerializer):
    depends_on_title = serializers.CharField(
        source='depends_on.title', read_only=True
    )

    class Meta:
        model = TaskDependency
        fields = ['id', 'depends_on', 'depends_on_title']


class TaskSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(
        source='created_by.email', read_only=True, allow_null=True
    )
    assigned_to_email = serializers.EmailField(
        source='assigned_to.email', read_only=True, allow_null = True
    )
    dependencies = TaskDependencySerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'due_date', 'project', 'organization',
            'assigned_to', 'assigned_to_email',
            'created_by', 'created_by_email',
            'dependencies', 'version',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'organization', 'created_by',
            'created_at', 'updated_at', 'version'
        ]


class TaskUpdateSerializer(serializers.ModelSerializer):
    """
    Used for updates only — includes version for optimistic locking.
    """
    version = serializers.IntegerField()

    class Meta:
        model = Task
        fields = [
            'title', 'description', 'status', 'priority',
            'due_date', 'assigned_to', 'version'
        ]

    def validate(self, attrs):
        # check version matches current DB version
        version = attrs.get('version')
        if self.instance and self.instance.version != version:
            raise serializers.ValidationError(
                {'version': 'This task was modified by someone else. Please refresh and try again.'}
            )
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop('version')        # remove before saving
        validated_data['version'] = instance.version + 1   # increment
        return super().update(instance, validated_data)


class AddDependencySerializer(serializers.Serializer):
    depends_on_id = serializers.UUIDField()

    def validate_depends_on_id(self, value):
        task = self.context['task']

        # cannot depend on itself
        if str(value) == str(task.id):
            raise serializers.ValidationError("A task cannot depend on itself.")

        # check depends_on task exists in same org
        from .models import Task as TaskModel
        if not TaskModel.objects.filter(
            id=value,
            organization=task.organization
        ).exists():
            raise serializers.ValidationError("Task not found in this organization.")

        # cycle detection
        if has_cycle(task.id, value):
            raise serializers.ValidationError(
                "This dependency would create a cycle."
            )
        return value


class PrioritizedTaskSerializer(serializers.ModelSerializer):
    urgency_score = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(
        source='assigned_to.email', read_only=True
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'status', 'priority',
            'due_date', 'assigned_to_email',
            'urgency_score'
        ]

    def get_urgency_score(self, obj):
        # score was attached by the view
        return getattr(obj, '_urgency_score', 0)