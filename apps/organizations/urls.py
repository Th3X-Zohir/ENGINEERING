from django.urls import path
from .views import OrganizationListCreateView, OrganizationDetailView, MembershipListCreateView, Membership


urlpatterns = [
    path('organizations/', OrganizationListCreateView.as_view(), name='org-list'),
    path('organizations/<uuid:pk>/', OrganizationDetailView.as_view(), name='org-detail'),
    path('organizations/<uuid:org_id>/members/', MembershipListCreateView.as_view(), name='org-members'),
]