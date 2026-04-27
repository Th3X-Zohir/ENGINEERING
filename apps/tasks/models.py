import uuid
from django.db import models
from django.conf import settings


class Task(models.Model):

    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        IN_REVIEW = 'in_review', 'In Review'
        DONE = 'done', 'Done'
        CANCELLED = 'cancelled', 'Cancelled'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    # priority weight map used in scoring
    PRIORITY_WEIGHTS = {
        'low': 1,
        'medium': 2,
        'high': 3,
        'critical': 4,
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tasks'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks'
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TODO
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    due_date = models.DateField(null=True, blank=True)

    # optimistic locking — increments on every save
    version = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks'
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'assigned_to']),
            models.Index(fields=['organization', 'priority']),
            models.Index(fields=['due_date']),
            models.Index(fields=['project']),
        ]

    def __str__(self):
        return self.title


class TaskDependency(models.Model):
    """
    task depends_on another task.
    Meaning: task is BLOCKED BY depends_on.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='dependencies'
    )
    depends_on = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='dependents'
    )

    class Meta:
        db_table = 'task_dependencies'
        unique_together = [['task', 'depends_on']]

    def __str__(self):
        return f"{self.task.title} blocked by {self.depends_on.title}"