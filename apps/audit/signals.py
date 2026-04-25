from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from apps.tasks.models import Task
from .models import AuditLog

# store before-state temporarily
_task_before_state = {}


def task_to_dict(task):
    """Convert task fields to a plain dict for storing in audit log."""
    return {
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'priority': task.priority,
        'due_date': str(task.due_date) if task.due_date else None,
        'assigned_to_id': str(task.assigned_to_id) if task.assigned_to_id else None,
        'version': task.version,
    }


@receiver(pre_save, sender=Task)
def capture_before_state(sender, instance, **kwargs):
    """
    Before save — capture the old state if task already exists.
    pre_save fires before the DB is updated.
    """
    if instance.pk:
        try:
            old = Task.objects.get(pk=instance.pk)
            _task_before_state[str(instance.pk)] = task_to_dict(old)
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def log_task_save(sender, instance, created, **kwargs):
    """
    After save — create an audit log entry.
    post_save fires after DB is updated.
    """
    # get current request user from thread-local (set by middleware)
    from core.middleware import get_current_user
    user = get_current_user()

    before = None if created else _task_before_state.pop(str(instance.pk), None)

    AuditLog.objects.create(
        organization=instance.organization,
        user=user,
        entity_type='Task',
        entity_id=instance.id,
        action=AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE,
        before_state=before,
        after_state=task_to_dict(instance),
    )


@receiver(post_delete, sender=Task)
def log_task_delete(sender, instance, **kwargs):
    from core.middleware import get_current_user
    user = get_current_user()

    AuditLog.objects.create(
        organization=instance.organization,
        user=user,
        entity_type='Task',
        entity_id=instance.id,
        action=AuditLog.Action.DELETE,
        before_state=task_to_dict(instance),
        after_state=None,
    )