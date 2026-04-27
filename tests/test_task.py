import pytest
from datetime import date, timedelta
from apps.tasks.models import Task, TaskDependency
from apps.tasks.services import has_cycle, calculate_urgency_score
from django.db import connection, reset_queries


@pytest.mark.django_db
class TestTaskCRUD:

    def test_create_task(self, client_a, org_a, project_a):
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/',
            {
                'title': 'New Task',
                'description': 'Details here',
                'status': 'todo',
                'priority': 'medium',
                'project': str(project_a.id),
            }
        )
        assert response.status_code == 201
        assert response.data['title'] == 'New Task'

    def test_list_tasks(self, client_a, org_a, task_a, task_b):
        response = client_a.get(f'/api/organizations/{org_a.id}/tasks/')
        assert response.status_code == 200
        assert len(response.data['results']) == 2

    def test_filter_tasks_by_status(self, client_a, org_a, task_a):
        response = client_a.get(
            f'/api/organizations/{org_a.id}/tasks/?status=todo'
        )
        assert response.status_code == 200
        for task in response.data['results']:
            assert task['status'] == 'todo'

    def test_filter_tasks_by_priority(self, client_a, org_a, task_a):
        response = client_a.get(
            f'/api/organizations/{org_a.id}/tasks/?priority=high'
        )
        assert response.status_code == 200
        for task in response.data['results']:
            assert task['priority'] == 'high'

    def test_search_tasks(self, client_a, org_a, task_a):
        response = client_a.get(
            f'/api/organizations/{org_a.id}/tasks/?search=Alpha'
        )
        assert response.status_code == 200
        assert any('Alpha' in t['title'] for t in response.data['results'])

    def test_update_task(self, client_a, org_a, task_a):
        response = client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Updated Title', 'version': 0}
        )
        assert response.status_code == 200

    def test_delete_task(self, client_a, org_a, task_a):
        response = client_a.delete(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/'
        )
        assert response.status_code == 204
        assert not Task.objects.filter(id=task_a.id).exists()

    def test_tenant_isolation_security(self, client_a, org_b, task_b):
    
        response = client_a.get(f'/api/organizations/{org_b.id}/tasks/{task_b.id}/')
        assert response.status_code in [403, 404]


from apps.tasks.services import get_prioritized_tasks
from django.db.models import Q

@pytest.mark.django_db
class TestPriorityEngine:

    def test_prioritized_endpoint_returns_200(self, client_a, org_a, task_a):
        response = client_a.get(
            f'/api/organizations/{org_a.id}/tasks/prioritized/'
        )
        assert response.status_code == 200

    def test_overdue_task_has_higher_score(self, db, org_a, project_a, user_a):
        # 1. Create tasks
        overdue = Task.objects.create(
            organization=org_a, project=project_a, created_by=user_a,
            title='Overdue', priority='low', status='todo',
            due_date=date.today() - timedelta(days=10)
        )
        not_due = Task.objects.create(
            organization=org_a, project=project_a, created_by=user_a,
            title='Not Due', priority='low', status='todo',
            due_date=date.today() + timedelta(days=10)
        )

        # 2. Score them using the Database Service
        qs = get_prioritized_tasks(Task.objects.filter(id__in=[overdue.id, not_due.id]))
        
        # 3. Pull from queryset and check the annotated _urgency_score
        overdue_scored = qs.get(id=overdue.id)
        not_due_scored = qs.get(id=not_due.id)
        
        assert overdue_scored._urgency_score > not_due_scored._urgency_score

    def test_critical_priority_higher_than_low(self, db, org_a, project_a, user_a):
        critical = Task.objects.create(
            organization=org_a, project=project_a, created_by=user_a,
            title='Critical', priority='critical', status='todo'
        )
        low = Task.objects.create(
            organization=org_a, project=project_a, created_by=user_a,
            title='Low', priority='low', status='todo'
        )

        # Score via DB service
        qs = get_prioritized_tasks(Task.objects.filter(id__in=[critical.id, low.id]))
        
        assert qs.get(id=critical.id)._urgency_score > qs.get(id=low.id)._urgency_score

    def test_prioritized_sorted_descending(self, client_a, org_a, project_a, user_a):
        Task.objects.create(
            organization=org_a, project=project_a, created_by=user_a,
            title='Low priority task', priority='low', status='todo'
        )
        Task.objects.create(
            organization=org_a, project=project_a, created_by=user_a,
            title='Critical task', priority='critical', status='todo'
        )
        
        response = client_a.get(
            f'/api/organizations/{org_a.id}/tasks/prioritized/'
        )
        
        # Note: Your Serializer should be mapping '_urgency_score' to 'urgency_score'
        scores = [t['urgency_score'] for t in response.data]
        assert scores == sorted(scores, reverse=True)

@pytest.mark.django_db
class TestCycleDetection:

    def test_no_cycle_simple(self, task_a, task_b):
        # A depends on B — no cycle
        assert not has_cycle(task_a.id, task_b.id)

    def test_direct_cycle_rejected(self, client_a, org_a, task_a, task_b):
        # Add A depends on B
        TaskDependency.objects.create(task=task_a, depends_on=task_b)
        # Try to add B depends on A — should create cycle
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/{task_b.id}/dependencies/',
            {'depends_on_id': str(task_a.id)}
        )
        assert response.status_code == 400
        assert 'cycle' in str(response.data).lower()

    def test_self_dependency_rejected(self, client_a, org_a, task_a):
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/dependencies/',
            {'depends_on_id': str(task_a.id)}
        )
        assert response.status_code == 400

    def test_transitive_cycle_rejected(self, db, org_a, project_a, user_a, client_a):
        # A → B → C → A would be a cycle
        t1 = Task.objects.create(
            organization=org_a, project=project_a,
            created_by=user_a, title='T1', status='todo', priority='low'
        )
        t2 = Task.objects.create(
            organization=org_a, project=project_a,
            created_by=user_a, title='T2', status='todo', priority='low'
        )
        t3 = Task.objects.create(
            organization=org_a, project=project_a,
            created_by=user_a, title='T3', status='todo', priority='low'
        )
        TaskDependency.objects.create(task=t1, depends_on=t2)
        TaskDependency.objects.create(task=t2, depends_on=t3)
        # now try t3 → t1 which would complete the cycle
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/{t3.id}/dependencies/',
            {'depends_on_id': str(t1.id)}
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestQueryPerformance:

    def test_task_list_no_n_plus_1(self, client_a, org_a, project_a, user_a):
        """
        Create 10 tasks, then assert the list endpoint
        does NOT make N+1 queries (should be ~3-4 queries total).
        """
        from apps.tasks.models import Task
        # create 10 tasks
        for i in range(10):
            Task.objects.create(
                organization=org_a, project=project_a,
                created_by=user_a, title=f'Task {i}',
                status='todo', priority='medium'
            )

        # count DB queries during the request
        from django.conf import settings
        settings.DEBUG = True
        reset_queries()

        client_a.get(f'/api/organizations/{org_a.id}/tasks/')

        query_count = len(connection.queries)
        settings.DEBUG = False

        # with proper eager loading, should never exceed 6 queries
        # regardless of number of tasks
        assert query_count <= 6, (
            f"Too many queries: {query_count}. "
            f"Possible N+1 detected. Queries: {[q['sql'][:80] for q in connection.queries]}"
        )