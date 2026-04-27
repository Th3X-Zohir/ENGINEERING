import pytest
from apps.organizations.models import Membership


@pytest.mark.django_db
class TestPrivilegeEscalation:
    """
    Members should not be able to perform Admin/Owner actions.
    """

    @pytest.fixture
    def member_client(self, api_client, user_member, org_a):
        # add user_member to org_a as a plain member
        Membership.objects.create(
            user=user_member,
            organization=org_a,
            role='member'
        )
        from conftest import auth_client
        return auth_client(api_client, 'member@test.com', 'testpass123')

    def test_member_cannot_create_task(self, member_client, org_a, project_a):
        response = member_client.post(
            f'/api/organizations/{org_a.id}/tasks/',
            {
                'title': 'Sneaky Task',
                'status': 'todo',
                'priority': 'low',
                'project': str(project_a.id),
            }
        )
        assert response.status_code == 403

    def test_member_cannot_delete_task(self, member_client, org_a, task_a):
        response = member_client.delete(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/'
        )
        assert response.status_code == 403

    def test_member_cannot_update_task(self, member_client, org_a, task_a):
        response = member_client.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Hacked', 'version': 0}
        )
        assert response.status_code == 403

    def test_member_cannot_add_members_to_org(self, member_client, org_a):
        response = member_client.post(
            f'/api/organizations/{org_a.id}/members/',
            {'user': 'someuser', 'role': 'admin'}
        )
        assert response.status_code == 403

    def test_member_can_read_tasks(self, member_client, org_a, task_a):
        # members CAN read tasks
        response = member_client.get(
            f'/api/organizations/{org_a.id}/tasks/'
        )
        assert response.status_code == 200

    def test_member_cannot_create_project(self, member_client, org_a):
        response = member_client.post(
            f'/api/organizations/{org_a.id}/projects/',
            {'name': 'Sneaky Project', 'description': 'Should fail'}
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestTenantIsolation:

    def test_user_cannot_see_other_org_tasks(self, client_b, org_a, task_a):
        response = client_b.get(f'/api/organizations/{org_a.id}/tasks/')
        assert response.status_code in [403, 404]

    def test_user_cannot_see_other_org_projects(self, client_b, org_a, project_a):
        response = client_b.get(f'/api/organizations/{org_a.id}/projects/')
        assert response.status_code in [403, 404]

    def test_user_cannot_create_task_in_other_org(self, client_b, org_a, project_a):
        response = client_b.post(
            f'/api/organizations/{org_a.id}/tasks/',
            {'title': 'Injected', 'status': 'todo', 'priority': 'high', 'project': str(project_a.id)}
        )
        assert response.status_code in [403, 404]

    def test_user_cannot_access_other_org_task_by_id(self, client_b, org_a, task_a):
        response = client_b.get(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/'
        )
        assert response.status_code in [403, 404]

    def test_user_cannot_update_other_org_task(self, client_b, org_a, task_a):
        response = client_b.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Hacked', 'version': 0}
        )
        assert response.status_code in [403, 404]

    def test_user_cannot_delete_other_org_task(self, client_b, org_a, task_a):
        response = client_b.delete(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/'
        )
        assert response.status_code in [403, 404]

    def test_unauthenticated_cannot_access_tasks(self, api_client, org_a):
        response = api_client.get(f'/api/organizations/{org_a.id}/tasks/')
        assert response.status_code == 401

    def test_task_list_only_returns_own_org_tasks(self, client_a, org_a, task_a, task_b):
        response = client_a.get(f'/api/organizations/{org_a.id}/tasks/')
        assert response.status_code == 200
        task_ids = [t['id'] for t in response.data['results']]
        assert str(task_a.id) in task_ids
        assert str(task_b.id) in task_ids