from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from apps.tasks.models import Task
from .models import AuditLog

_task_before_state = {}


def task_to_dict(task):
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
    if instance.pk:
        try:
            old = Task.objects.get(pk=instance.pk)
            _task_before_state[str(instance.pk)] = task_to_dict(old)
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def log_task_save(sender, instance, created, **kwargs):
    from core.middleware import get_current_user
    user = get_current_user()
    before = None if created else _task_before_state.pop(str(instance.pk), None)
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE

    # capture values now before transaction ends
    org_id = instance.organization_id
    entity_id = instance.id
    after = task_to_dict(instance)
    user_id = user.id if user and user.is_authenticated else None

    def create_log():
        AuditLog.objects.create(
            organization_id=org_id,
            user_id=user_id,
            entity_type='Task',
            entity_id=entity_id,
            action=action,
            before_state=before,
            after_state=after,
        )

    transaction.on_commit(create_log)


@receiver(post_delete, sender=Task)
def log_task_delete(sender, instance, **kwargs):
    from core.middleware import get_current_user
    user = get_current_user()

    org_id = instance.organization_id
    entity_id = instance.id
    before = task_to_dict(instance)
    user_id = user.id if user and user.is_authenticated else None

    def create_log():
        AuditLog.objects.create(
            organization_id=org_id,
            user_id=user_id,
            entity_type='Task',
            entity_id=entity_id,
            action=AuditLog.Action.DELETE,
            before_state=before,
            after_state=None,
        )

    transaction.on_commit(create_log)