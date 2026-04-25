from django.urls import path
from .views import (
    TaskListCreateView, TaskDetailView,
    PrioritizedTaskView, AddDependencyView, BulkImportView
)

urlpatterns = [
    path(
        'organizations/<uuid:org_id>/tasks/',
        TaskListCreateView.as_view(),
        name='task-list'
    ),
    path(
        'organizations/<uuid:org_id>/tasks/prioritized/',
        PrioritizedTaskView.as_view(),
        name='task-prioritized'
    ),
    path(
        'organizations/<uuid:org_id>/tasks/bulk-import/',
        BulkImportView.as_view(),
        name='task-bulk-import'
    ),
    path(
        'organizations/<uuid:org_id>/tasks/<uuid:pk>/',
        TaskDetailView.as_view(),
        name='task-detail'
    ),
    path(
        'organizations/<uuid:org_id>/tasks/<uuid:task_id>/dependencies/',
        AddDependencyView.as_view(),
        name='task-add-dependency'
    ),
]