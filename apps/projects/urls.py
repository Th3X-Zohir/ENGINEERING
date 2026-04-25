from django.urls import path
from .views import ProjectListCreateView, ProjectDetailView

urlpatterns = [
    path(
        'organizations/<uuid:org_id>/projects/',
        ProjectListCreateView.as_view(),
        name='project-list'
    ),
    path(
        'organizations/<uuid:org_id>/projects/<uuid:pk>/',
        ProjectDetailView.as_view(),
        name='project-detail'
    ),
]