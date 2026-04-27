"""
Benchmark script — tests query performance with large dataset.

Run with:
    python scripts/benchmark.py

Make sure server is running:
    python manage.py runserver
"""
import os
import time
import django
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection, reset_queries
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization, Membership
from apps.projects.models import Project
from apps.tasks.models import Task
from apps.tasks.services import get_prioritized_tasks

settings.DEBUG = True
User = get_user_model()

print("=" * 60)
print("WORKMANAGER BENCHMARK — 100,000 TASKS")
print("=" * 60)


# ── Setup ─────────────────────────────────────────────────────
print("\n[1] Setting up benchmark data...")

user, _ = User.objects.get_or_create(
    email='bench@test.com',
    defaults={'full_name': 'Bench User'}
)
user.set_password('bench123')
user.save()

org, _ = Organization.objects.get_or_create(
    slug='bench-org',
    defaults={'name': 'Benchmark Org'}
)
Membership.objects.get_or_create(
    user=user, organization=org,
    defaults={'role': 'owner'}
)
project, _ = Project.objects.get_or_create(
    organization=org,
    name='Bench Project',
    defaults={'created_by': user}
)

current_count = Task.objects.filter(organization=org).count()
TARGET = 100_000

if current_count < TARGET:
    needed = TARGET - current_count
    print(f"   Creating {needed:,} tasks (current: {current_count:,})...")

    BATCH = 5000
    from datetime import date, timedelta
    import random

    statuses = ['todo', 'in_progress', 'in_review', 'done']
    priorities = ['low', 'medium', 'high', 'critical']

    for batch_start in range(0, needed, BATCH):
        batch_size = min(BATCH, needed - batch_start)
        tasks = [
            Task(
                organization=org,
                project=project,
                created_by=user,
                title=f'Bench Task {current_count + batch_start + i}',
                status=statuses[i % 4],
                priority=priorities[i % 4],
                due_date=date.today() - timedelta(days=random.randint(-30, 30))
            )
            for i in range(batch_size)
        ]
        Task.objects.bulk_create(tasks)
        print(f"   ... {min(batch_start + BATCH, needed):,} / {needed:,} created")

print(f"   Total tasks: {Task.objects.filter(organization=org).count():,}")


# ── Benchmark 1: Simple task list ─────────────────────────────
print("\n[2] Benchmark: GET /tasks/ (first page, cursor pagination)")
reset_queries()
start = time.perf_counter()

tasks = Task.objects.filter(
    organization=org
).select_related(
    'assigned_to', 'created_by', 'project'
).prefetch_related(
    'dependencies'
).order_by('-created_at')[:20]

list(tasks)  # force evaluation

elapsed = time.perf_counter() - start
print(f"   Time:    {elapsed * 1000:.2f} ms")
print(f"   Queries: {len(connection.queries)}")


# ── Benchmark 2: Prioritized endpoint ─────────────────────────
print("\n[3] Benchmark: GET /tasks/prioritized/ (all non-done tasks)")
reset_queries()
start = time.perf_counter()

base_qs = Task.objects.filter(
    organization=org
).exclude(status='done')

scored = get_prioritized_tasks(base_qs)

elapsed = time.perf_counter() - start
print(f"   Time:    {elapsed * 1000:.2f} ms")
print(f"   Tasks scored: {len(scored):,}")
print(f"   Queries: {len(connection.queries)}")


# ── Benchmark 3: Audit log lookup ─────────────────────────────
print("\n[4] Benchmark: GET /audit/task/{id}")
from apps.audit.models import AuditLog
task = Task.objects.filter(organization=org).first()

reset_queries()
start = time.perf_counter()

logs = list(AuditLog.objects.filter(
    entity_type='Task',
    entity_id=task.id
).select_related('user'))

elapsed = time.perf_counter() - start
print(f"   Time:    {elapsed * 1000:.2f} ms")
print(f"   Queries: {len(connection.queries)}")


# ── Benchmark 4: Tenant isolation check ───────────────────────
print("\n[5] Benchmark: Membership lookup (runs on every request)")
reset_queries()
start = time.perf_counter()

for _ in range(100):
    Membership.objects.filter(
        user=user, organization=org
    ).exists()

elapsed = time.perf_counter() - start
print(f"   100 membership checks: {elapsed * 1000:.2f} ms")
print(f"   Per check: {elapsed * 10:.3f} ms")
print(f"   Queries: {len(connection.queries)}")


# ── Summary ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BENCHMARK COMPLETE")
print("=" * 60)
print("\nAll query times should be under 500ms for 100k records.")
print("If prioritized/ is slow, consider limiting to non-done tasks only.")
settings.DEBUG = False