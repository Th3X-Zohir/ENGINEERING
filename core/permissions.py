from rest_framework.permissions import BasePermission
from apps.organizations.models import Membership



def get_user_role(user, organization_id):
    if not user or not user.is_authenticated:
        return None
    
    try:
        m = Membership.objects.get(user=user, organization_id=organization_id)
        return m.role
    except Membership.DoesNotExist:
        return None
    

class IsOrganizationOwner(BasePermission):
    def has_permission(self, request, view):
        org_id = view.kwargs.get('org_id') or request.query_params.get('org_id')
        return get_user_role(request.user, org_id) == Membership.Role.OWNER
    

class IsOrganizationAdmin(BasePermission):
    def has_permission(self, request, view):
        org_id = view.kwargs.get('org_id') or request.query_params.get('org_id')
        return get_user_role(request.user, org_id) in [Membership.Role.OWNER, Membership.Role.ADMIN]
    

class IsOrganizationMember(BasePermission):
    def has_permission(self, request, view):
        org_id = view.kwargs.get('org_id') or request.query_params.get('org_id')
        return get_user_role(request.user, org_id) is not None

