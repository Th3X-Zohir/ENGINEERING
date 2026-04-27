import pytest
from django.contrib.auth import get_user_model
from apps.audit.models import AuditLog
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestRegister:

    def test_register_success(self, api_client):
        response = api_client.post('/api/auth/register/', {
            'email': 'new@test.com',
            'full_name': 'New User',
            'password': 'strongpass123'
        })
        assert response.status_code == 201
        assert response.data['email'] == 'new@test.com'
        assert 'password' not in response.data  # password must never be returned

    def test_register_duplicate_email(self, api_client, user_a):
        response = api_client.post('/api/auth/register/', {
            'email': 'user_a@test.com',   # already exists
            'full_name': 'Duplicate',
            'password': 'strongpass123'
        })
        assert response.status_code == 400

    def test_register_weak_password(self, api_client):
        response = api_client.post('/api/auth/register/', {
            'email': 'weak@test.com',
            'full_name': 'Weak',
            'password': '123'             # too short
        })
        assert response.status_code == 400

    def test_register_missing_email(self, api_client):
        response = api_client.post('/api/auth/register/', {
            'full_name': 'No Email',
            'password': 'strongpass123'
        })
        assert response.status_code == 400


@pytest.mark.django_db
class TestLogin:

    def test_login_success(self, api_client, user_a):
        response = api_client.post('/api/auth/login/', {
            'email': 'user_a@test.com',
            'password': 'testpass123'
        })
        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_wrong_password(self, api_client, user_a):
        response = api_client.post('/api/auth/login/', {
            'email': 'user_a@test.com',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, api_client):
        response = api_client.post('/api/auth/login/', {
            'email': 'ghost@test.com',
            'password': 'anything'
        })
        assert response.status_code == 401


@pytest.mark.django_db
class TestRefreshToken:

    def test_refresh_success(self, api_client, user_a):
        login = api_client.post('/api/auth/login/', {
            'email': 'user_a@test.com',
            'password': 'testpass123'
        })
        refresh_token = login.data['refresh']
        response = api_client.post('/api/auth/refresh/', {
            'refresh': refresh_token
        })
        assert response.status_code == 200
        assert 'access' in response.data

    def test_invalid_refresh_token(self, api_client):
        response = api_client.post('/api/auth/refresh/', {
            'refresh': 'totally-invalid-token'
        })
        assert response.status_code == 401




def make_client(email, password):
    client = APIClient()
    r = client.post('/api/auth/login/', {'email': email, 'password': password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


@pytest.mark.django_db(transaction=True)
class TestAuditLog:

    def test_task_create_generates_audit_log(self, user_a, org_a, project_a):
        client = make_client('user_a@test.com', 'testpass123')
        response = client.post(
            f'/api/organizations/{org_a.id}/tasks/',
            {
                'title': 'Audited Task',
                'status': 'todo',
                'priority': 'medium',
                'project': str(project_a.id),
            }
        )
        assert response.status_code == 201
        task_id = response.data['id']

        log = AuditLog.objects.filter(
            entity_type='Task',
            entity_id=task_id,
            action='create'
        ).first()
        assert log is not None
        assert log.before_state is None
        assert log.after_state['title'] == 'Audited Task'

    def test_task_update_captures_before_and_after(self, user_a, org_a, task_a):
        client = make_client('user_a@test.com', 'testpass123')
        client.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Updated Title', 'version': 0}
        )
        log = AuditLog.objects.filter(
            entity_type='Task',
            entity_id=task_a.id,
            action='update'
        ).first()
        assert log is not None
        assert log.before_state['title'] == 'Task Alpha'
        assert log.after_state['title'] == 'Updated Title'

    def test_task_delete_generates_audit_log(self, user_a, org_a, task_a):
        client = make_client('user_a@test.com', 'testpass123')
        task_id = task_a.id
        client.delete(f'/api/organizations/{org_a.id}/tasks/{task_id}/')

        log = AuditLog.objects.filter(
            entity_type='Task',
            entity_id=task_id,
            action='delete'
        ).first()
        assert log is not None
        assert log.after_state is None
        assert log.before_state is not None

    def test_audit_log_endpoint_returns_history(self, user_a, org_a, task_a):
        client = make_client('user_a@test.com', 'testpass123')
        client.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Changed', 'version': 0}
        )
        response = client.get(
            f'/api/organizations/{org_a.id}/audit/task/{task_a.id}/'
        )
        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_audit_log_tenant_isolation(self, user_b, org_b, org_a, task_a):
        client = make_client('user_b@test.com', 'testpass123')
        response = client.get(
            f'/api/organizations/{org_a.id}/audit/task/{task_a.id}/'
        )
        assert response.status_code in [403, 404]

    def test_status_change_captured_in_audit(self, user_a, org_a, task_a):
        client = make_client('user_a@test.com', 'testpass123')
        client.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'status': 'in_progress', 'version': 0}
        )
        log = AuditLog.objects.filter(
            entity_type='Task',
            entity_id=task_a.id,
            action='update'
        ).first()
        assert log is not None
        assert log.before_state['status'] == 'todo'
        assert log.after_state['status'] == 'in_progress'

    def test_assignment_change_captured_in_audit(self, user_a, user_b, org_a, org_b, task_a):
        # add user_b to org_a so they can be assigned
        from apps.organizations.models import Membership
        Membership.objects.create(user=user_b, organization=org_a, role='member')

        client = make_client('user_a@test.com', 'testpass123')
        client.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'assigned_to': str(user_b.id), 'version': 0}
        )
        log = AuditLog.objects.filter(
            entity_type='Task',
            entity_id=task_a.id,
            action='update'
        ).first()
        assert log is not None
        assert log.before_state['assigned_to_id'] is None
        assert log.after_state['assigned_to_id'] == str(user_b.id)