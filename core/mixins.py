from rest_framework.exceptions import PermissionDenied, NotFound
from apps.organizations.models import Organization, Membership  



class TenantQuerysetMixin:
    def get_organization(self):
        org_id = self.kwargs.get('org_id') or self.request.query_params.get('org_id')
        if not org_id:
            raise PermissionDenied("Organization ID is required.")
        try:
            m = Membership.objects.select_related('organization').get(user=self.request.user, organization_id=org_id)
        except Membership.DoesNotExist:
            raise NotFound("Organization not found or you do not have access.")
        return m.organization, m.role
    
    def get_queryset(self):
        org, role = self.get_organization()
        return super().get_queryset().filter(organization=org)