from rest_framework import generics
from core.mixins import TenantQuerysetMixin
from core.permissions import IsOrganizationAdmin, IsOrganizationMember
from .models import Project
from .serializers import ProjectSerializer


class ProjectListCreateView(TenantQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()

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


class ProjectDetailView(TenantQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsOrganizationAdmin()]
        return [IsOrganizationMember()]