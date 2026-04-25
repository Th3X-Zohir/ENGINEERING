from django.urls import path
from .views import TaskAuditLogView

urlpatterns = [
    path(
        'organizations/<uuid:org_id>/audit/task/<uuid:task_id>/',
        TaskAuditLogView.as_view(),
        name='task-audit-log'
    ),
]