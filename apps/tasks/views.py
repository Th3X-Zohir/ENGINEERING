import csv
import io
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from core.mixins import TenantQuerysetMixin
from core.permissions import IsOrganizationAdmin, IsOrganizationMember
from .models import Task, TaskDependency
from .serializers import (
    TaskSerializer, TaskUpdateSerializer,
    AddDependencySerializer, PrioritizedTaskSerializer
)
from .filters import TaskFilter
from .services import get_prioritized_tasks, bulk_import_tasks


class TaskListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = TaskSerializer
    queryset = Task.objects.select_related(
        'assigned_to', 'created_by', 'project'
    ).prefetch_related('dependencies')
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TaskFilter
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'due_date', 'priority']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsOrganizationAdmin()]
        return [IsOrganizationMember()]

    def perform_create(self, serializer):
        org, _ = self.get_organization()
        serializer.save(
            organization=org,
            created_by=self.request.user
        )


class TaskDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.select_related(
        'assigned_to', 'created_by', 'project'
    ).prefetch_related('dependencies')

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsOrganizationAdmin()]
        return [IsOrganizationMember()]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TaskUpdateSerializer
        return TaskSerializer


class PrioritizedTaskView(TenantQuerysetMixin, APIView):
    permission_classes = [IsOrganizationMember]

    def get(self, request, org_id):
        org, _ = self.get_organization()
        base_qs = Task.objects.filter(
            organization=org
        ).exclude(status='done')

        scored = get_prioritized_tasks(base_qs)

        # attach score to each task object
        result = []
        for task, score in scored:
            task._urgency_score = score
            result.append(task)

        serializer = PrioritizedTaskSerializer(result, many=True)
        return Response(serializer.data)


class AddDependencyView(TenantQuerysetMixin, APIView):
    permission_classes = [IsOrganizationMember]

    def post(self, request, org_id, task_id):
        org, _ = self.get_organization()
        try:
            task = Task.objects.get(id=task_id, organization=org)
        except Task.DoesNotExist:
            return Response({'detail': 'Task not found.'}, status=404)

        serializer = AddDependencySerializer(
            data=request.data,
            context={'task': task}
        )
        if serializer.is_valid():
            TaskDependency.objects.get_or_create(
                task=task,
                depends_on_id=serializer.validated_data['depends_on_id']
            )
            return Response({'detail': 'Dependency added.'}, status=201)
        return Response(serializer.errors, status=400)


class BulkImportView(TenantQuerysetMixin, APIView):
    permission_classes = [IsOrganizationAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request, org_id):
        org, _ = self.get_organization()

        # get the project for import
        project_id = request.data.get('project_id')
        if not project_id:
            return Response({'detail': 'project_id is required.'}, status=400)

        from apps.projects.models import Project
        try:
            project = Project.objects.get(id=project_id, organization=org)
        except Project.DoesNotExist:
            return Response({'detail': 'Project not found.'}, status=404)

        # read the CSV file
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'detail': 'CSV file is required.'}, status=400)

        decoded = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)

        if not rows:
            return Response({'detail': 'CSV file is empty.'}, status=400)

        summary = bulk_import_tasks(
            rows=rows,
            organization=org,
            project=project,
            created_by=request.user
        )
        return Response(summary, status=207)  # 207 Multi-Status