from rest_framework import generics
from core.permissions import IsOrganizationMember
from core.mixins import TenantQuerysetMixin
from .models import AuditLog
from .serializers import AuditLogSerializer


class TaskAuditLogView(TenantQuerysetMixin, generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsOrganizationMember]
    queryset = AuditLog.objects.select_related('user')

    def get_queryset(self):
        org, _ = self.get_organization()
        return AuditLog.objects.filter(
            organization=org,
            entity_type='Task',
            entity_id=self.kwargs['task_id']
        ).select_related('user')