import pytest
import io
import csv
from apps.tasks.models import Task
import threading

@pytest.mark.django_db
class TestOptimisticLocking:

    def test_stale_version_rejected(self, client_a, org_a, task_a):
        # first update succeeds (version 0 → 1)
        client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'First Update', 'version': 0}
        )
        # second update with old version 0 must fail
        response = client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Stale Update', 'version': 0}
        )
        assert response.status_code == 400
        assert 'version' in str(response.data).lower()

    def test_correct_version_succeeds(self, client_a, org_a, task_a):
        # version 0 → 1
        client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'First', 'version': 0}
        )
        # version 1 → 2
        response = client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Second', 'version': 1}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestBulkImport:

    def make_csv(self, rows):
        """Helper to build a CSV file in memory."""
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return io.BytesIO(output.getvalue().encode('utf-8'))

    def test_bulk_import_success(self, client_a, org_a, project_a):
        csv_file = self.make_csv([
            {'title': 'Task 1', 'status': 'todo', 'priority': 'high', 'description': '', 'due_date': ''},
            {'title': 'Task 2', 'status': 'in_progress', 'priority': 'low', 'description': '', 'due_date': ''},
        ])
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/bulk-import/',
            {'file': csv_file, 'project_id': str(project_a.id)},
            format='multipart'
        )
        assert response.status_code == 207
        assert response.data['created'] == 2
        assert response.data['failed'] == 0

    def test_bulk_import_partial_failure(self, client_a, org_a, project_a):
        csv_file = self.make_csv([
            {'title': 'Valid Task', 'status': 'todo', 'priority': 'high', 'description': '', 'due_date': ''},
            {'title': '', 'status': 'todo', 'priority': 'high', 'description': '', 'due_date': ''},       # missing title
            {'title': 'Bad Status', 'status': 'flying', 'priority': 'high', 'description': '', 'due_date': ''},  # invalid status
        ])
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/bulk-import/',
            {'file': csv_file, 'project_id': str(project_a.id)},
            format='multipart'
        )
        assert response.status_code == 207
        assert response.data['created'] == 1
        assert response.data['failed'] == 2
        assert len(response.data['errors']) == 2

    def test_bulk_import_invalid_date(self, client_a, org_a, project_a):
        csv_file = self.make_csv([
            {'title': 'Bad Date', 'status': 'todo', 'priority': 'low', 'description': '', 'due_date': '31-12-2025'},
        ])
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/bulk-import/',
            {'file': csv_file, 'project_id': str(project_a.id)},
            format='multipart'
        )
        assert response.data['failed'] == 1

    def test_bulk_import_no_file(self, client_a, org_a, project_a):
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/bulk-import/',
            {'project_id': str(project_a.id)},
            format='multipart'
        )
        assert response.status_code == 400

    def test_bulk_import_no_project_id(self, client_a, org_a):
        csv_file = self.make_csv([
            {'title': 'Task', 'status': 'todo', 'priority': 'low', 'description': '', 'due_date': ''},
        ])
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/bulk-import/',
            {'file': csv_file},
            format='multipart'
        )
        assert response.status_code == 400

    def test_bulk_import_duplicate_titles_handled(self, client_a, org_a, project_a):
        """
        Importing the same title twice should not crash.
        ignore_conflicts=True handles duplicates silently.
        """
        csv_file = self.make_csv([
            {'title': 'Dup Task', 'status': 'todo', 'priority': 'low', 'description': '', 'due_date': ''},
            {'title': 'Dup Task', 'status': 'todo', 'priority': 'low', 'description': '', 'due_date': ''},
        ])
        response = client_a.post(
            f'/api/organizations/{org_a.id}/tasks/bulk-import/',
            {'file': csv_file, 'project_id': str(project_a.id)},
            format='multipart'
        )
        assert response.status_code == 207
        # should not crash — duplicates silently ignored
        assert response.data['total_rows'] == 2



@pytest.mark.django_db
class TestConcurrentUpdates:

    def test_optimistic_lock_prevents_stale_update(self, client_a, org_a, task_a):
        """
        Simulates two users reading the same task (both see version=0),
        then both trying to update. The second update must be rejected.
        This is exactly what optimistic locking prevents.
        """
        # User 1 updates successfully (version 0 → 1)
        r1 = client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'User 1 Update', 'version': 0}
        )
        assert r1.status_code == 200

        # User 2 tries to update with the old version 0 — must fail
        r2 = client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'User 2 Stale Update', 'version': 0}
        )
        assert r2.status_code == 400
        assert 'version' in str(r2.data).lower()

    def test_version_increments_on_each_save(self, client_a, org_a, task_a):
        """Version counter goes up with every successful update."""
        from apps.tasks.models import Task

        # version starts at 0
        assert task_a.version == 0

        # update 1: version 0 → 1
        client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Update 1', 'version': 0}
        )
        task_a.refresh_from_db()
        assert task_a.version == 1

        # update 2: version 1 → 2
        client_a.patch(
            f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
            {'title': 'Update 2', 'version': 1}
        )
        task_a.refresh_from_db()
        assert task_a.version == 2

    def test_correct_version_always_succeeds(self, client_a, org_a, task_a):
        """Sequential updates with correct version always work."""
        for i in range(5):
            r = client_a.patch(
                f'/api/organizations/{org_a.id}/tasks/{task_a.id}/',
                {'title': f'Update {i}', 'version': i}
            )
            assert r.status_code == 200

        task_a.refresh_from_db()
        assert task_a.version == 5

