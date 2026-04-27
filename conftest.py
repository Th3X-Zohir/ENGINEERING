import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.organizations.models import Organization, Membership
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


# ── API Client ────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


def get_tokens(client, email, password):
    response = client.post('/api/auth/login/', {
        'email': email,
        'password': password
    })
    return response.data


def auth_client(client, email, password):
    tokens = get_tokens(client, email, password)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


# ── Users ─────────────────────────────────────────────────────────────

@pytest.fixture
def user_a(db):
    return User.objects.create_user(
        email='user_a@test.com',
        password='testpass123',
        full_name='User A'
    )


@pytest.fixture
def user_b(db):
    return User.objects.create_user(
        email='user_b@test.com',
        password='testpass123',
        full_name='User B'
    )


@pytest.fixture
def user_member(db):
    return User.objects.create_user(
        email='member@test.com',
        password='testpass123',
        full_name='Member User'
    )


# ── Organizations ─────────────────────────────────────────────────────

@pytest.fixture
def org_a(db, user_a):
    org = Organization.objects.create(name='Org A', slug='org-a')
    Membership.objects.create(user=user_a, organization=org, role='owner')
    return org


@pytest.fixture
def org_b(db, user_b):
    org = Organization.objects.create(name='Org B', slug='org-b')
    Membership.objects.create(user=user_b, organization=org, role='owner')
    return org


# ── Projects ─────────────────────────────────────────────────────────

@pytest.fixture
def project_a(db, org_a, user_a):
    return Project.objects.create(
        organization=org_a,
        created_by=user_a,
        name='Project Alpha'
    )


# ── Tasks ─────────────────────────────────────────────────────────────

@pytest.fixture
def task_a(db, org_a, project_a, user_a):
    return Task.objects.create(
        organization=org_a,
        project=project_a,
        created_by=user_a,
        title='Task Alpha',
        status='todo',
        priority='high',
    )


@pytest.fixture
def task_b(db, org_a, project_a, user_a):
    return Task.objects.create(
        organization=org_a,
        project=project_a,
        created_by=user_a,
        title='Task Beta',
        status='todo',
        priority='medium',
    )


# ── Authenticated clients ─────────────────────────────────────────────

@pytest.fixture
def client_a(api_client, user_a):
    return auth_client(api_client, 'user_a@test.com', 'testpass123')


@pytest.fixture
def client_b(api_client, user_b):
    # fresh client for user_b
    client = APIClient()
    return auth_client(client, 'user_b@test.com', 'testpass123')