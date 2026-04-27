"""
Run with: python manage.py shell < scripts/seed.py
"""
import django
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import date, timedelta
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization, Membership
from apps.projects.models import Project
from apps.tasks.models import Task, TaskDependency

User = get_user_model()

print("Seeding database...")

# ── Users ─────────────────────────────────────────────────────────────
owner = User.objects.create_user(
    email='owner@demo.com', password='demo1234', full_name='Alice Owner'
)
admin = User.objects.create_user(
    email='admin@demo.com', password='demo1234', full_name='Bob Admin'
)
member = User.objects.create_user(
    email='member@demo.com', password='demo1234', full_name='Carol Member'
)

# ── Organization ──────────────────────────────────────────────────────
org = Organization.objects.create(name='Demo Company', slug='demo-company')
Membership.objects.create(user=owner, organization=org, role='owner')
Membership.objects.create(user=admin, organization=org, role='admin')
Membership.objects.create(user=member, organization=org, role='member')

# ── Project ───────────────────────────────────────────────────────────
project = Project.objects.create(
    organization=org,
    created_by=owner,
    name='Product Launch',
    description='Q1 product launch project'
)

# ── Tasks ─────────────────────────────────────────────────────────────
t1 = Task.objects.create(
    organization=org, project=project, created_by=owner,
    assigned_to=admin,
    title='Design system architecture',
    description='Define the overall system design',
    status='done', priority='critical',
    due_date=date.today() - timedelta(days=5)
)
t2 = Task.objects.create(
    organization=org, project=project, created_by=owner,
    assigned_to=admin,
    title='Set up CI/CD pipeline',
    description='GitHub Actions for automated deploys',
    status='in_progress', priority='high',
    due_date=date.today() + timedelta(days=3)
)
t3 = Task.objects.create(
    organization=org, project=project, created_by=owner,
    assigned_to=member,
    title='Write API documentation',
    description='Document all endpoints with examples',
    status='todo', priority='medium',
    due_date=date.today() + timedelta(days=7)
)
t4 = Task.objects.create(
    organization=org, project=project, created_by=owner,
    assigned_to=member,
    title='Implement user notifications',
    description='Email notifications on task assignment',
    status='todo', priority='low',
    due_date=date.today() - timedelta(days=2)   # overdue
)
t5 = Task.objects.create(
    organization=org, project=project, created_by=owner,
    title='Conduct security audit',
    description='Penetration testing and vulnerability scan',
    status='todo', priority='critical',
    due_date=date.today() + timedelta(days=1)
)

# ── Dependencies ──────────────────────────────────────────────────────
TaskDependency.objects.create(task=t2, depends_on=t1)   # CI/CD blocked by architecture
TaskDependency.objects.create(task=t3, depends_on=t2)   # docs blocked by CI/CD

print("✅ Seed complete!")
print("──────────────────────────────")
print("Login credentials:")
print("  owner@demo.com  / demo1234  (Owner)")
print("  admin@demo.com  / demo1234  (Admin)")
print("  member@demo.com / demo1234  (Member)")
print(f"  Org ID: {org.id}")
print(f"  Project ID: {project.id}")