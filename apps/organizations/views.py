from rest_framework import generics, status
from rest_framework.response import Response
from .models import Organization, Membership
from .serializers import OrganizationSerializer, MembershipSerializer
from core.permissions import IsOrganizationMember, IsOrganizationOwner
from rest_framework.permissions import IsAuthenticated


class OrganizationListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return Organization.objects.filter(memberships__user=self.request.user)
    
    def perform_create(self, serializer):
        org = serializer.save()
        Membership.objects.create(
            user=self.request.user,
            organization=org,
            role=Membership.Role.OWNER
        )


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsOrganizationMember]

    def get_queryset(self):
        return Organization.objects.filter(memberships__user=self.request.user)
    

class MembershipListCreateView(generics.ListCreateAPIView):
    serializer_class = MembershipSerializer
    permission_classes = [IsOrganizationOwner]

    def get_queryset(self):
        org_id = self.kwargs['org_id']
        return Membership.objects.filter(organization_id=org_id).select_related('user')
    
    def perform_create(self, serializer):
        org_id = self.kwargs['org_id']
        serializer.save(organization_id=org_id)