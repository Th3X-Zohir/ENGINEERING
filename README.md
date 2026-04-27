# WorkManager API

> Production-grade multi-tenant work management API built with Django + Django REST Framework.

[![Tests](https://img.shields.io/badge/tests-58%20passed-brightgreen)](.)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)](.)
[![Python](https://img.shields.io/badge/python-3.12-blue)](.)
[![Django](https://img.shields.io/badge/django-6.0-green)](.)

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Quick Start — Local](#quick-start--local)
- [Quick Start — Docker](#quick-start--docker)
- [API Documentation](#api-documentation)
- [Architecture Decisions](#architecture-decisions)
- [Security Considerations](#security-considerations)
- [Performance Considerations](#performance-considerations)
- [Database Schema & Indexing](#database-schema--indexing)
- [Testing](#testing)
- [Benchmarks](#benchmarks)
- [Tradeoffs & Known Limitations](#tradeoffs--known-limitations)
- [Seed Data](#seed-data)

---

## Overview

WorkManager is a production-grade multi-tenant work management API. It supports multiple isolated organizations (tenants), each with their own projects, tasks, and members. Key features include:

- **JWT authentication** with access/refresh token rotation
- **Role-based access control** — Owner, Admin, Member
- **Strict tenant isolation** — no cross-organization data leakage
- **Advanced task engine** — urgency scoring, dependency graph, cycle detection
- **Full audit trail** — every mutation logged with before/after state
- **Bulk CSV import** — 10,000+ tasks with partial failure handling
- **Optimistic locking** — concurrent update protection
- **Cursor pagination** — scales to 100,000+ tasks

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Framework | Django 6.0 + Django REST Framework |
| Database | PostgreSQL 15 |
| Auth | JWT via `djangorestframework-simplejwt` |
| Docs | OpenAPI/Swagger via `drf-spectacular` |
| Testing | Pytest + pytest-django |
| Container | Docker + Docker Compose |

---

## Quick Start — Local

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Git

### 1. Clone and setup virtual environment

```bash
git clone <your-repo-url>
cd workmanager
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 2. Create the database

```bash
psql -U postgres
```

Inside psql:

```sql
CREATE USER workmanager_user WITH PASSWORD 'workmanager123';
CREATE DATABASE workmanager_db OWNER workmanager_user;
GRANT ALL PRIVILEGES ON DATABASE workmanager_db TO workmanager_user;
\q
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials if different from defaults
```

`.env` file:

```
SECRET_KEY=workmanager-super-secret-key-change-this-in-production-2025
DEBUG=True
ALLOWED_HOSTS=localhost 127.0.0.1
DB_NAME=workmanager_db
DB_USER=workmanager_user
DB_PASSWORD=workmanager123
DB_HOST=localhost
DB_PORT=5432
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Load seed data (optional)

```bash
python manage.py shell < scripts/seed.py
```

### 6. Start the server

```bash
python manage.py runserver
```

### 7. Open API docs

Visit: **http://127.0.0.1:8000/api/docs/**

---

## Quick Start — Docker

```bash
git clone <your-repo-url>
cd workmanager
cp .env.example .env.docker
docker-compose up --build
```

Visit: **http://localhost:8000/api/docs/**

The `docker-compose.yml` automatically runs migrations on startup. No manual steps required.

---

## API Documentation

Interactive Swagger UI is available at `/api/docs/` when the server is running.

### Base URL

```
http://localhost:8000/api/
```

### Authentication

All endpoints (except register and login) require a JWT Bearer token.

```
Authorization: Bearer <access_token>
```

---

### Auth Endpoints

#### POST /auth/register/

Register a new user account.

**Request body:**
```json
{
  "email": "user@example.com",
  "full_name": "John Doe",
  "password": "strongpassword123"
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe"
}
```

**Errors:**
- `400` — email already exists, password too short, missing fields

---

#### POST /auth/login/

Login and receive JWT tokens.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "strongpassword123"
}
```

**Response `200 OK`:**
```json
{
  "access": "<access_token>",
  "refresh": "<refresh_token>"
}
```

- Access token expires in **60 minutes**
- Refresh token expires in **7 days**

**Errors:**
- `401` — invalid credentials

---

#### POST /auth/refresh/

Get a new access token using a refresh token.

**Request body:**
```json
{
  "refresh": "<refresh_token>"
}
```

**Response `200 OK`:**
```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

> **Note:** Refresh tokens are rotated on every use. Old refresh tokens are blacklisted immediately.

---

### Organization Endpoints

#### GET /organizations/

List all organizations the authenticated user belongs to.

**Response `200 OK`:**
```json
[
  {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

#### POST /organizations/

Create a new organization. The creator is automatically assigned the **Owner** role.

**Required role:** Authenticated user (any)

**Request body:**
```json
{
  "name": "Acme Corp",
  "slug": "acme-corp"
}
```

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

#### GET /organizations/{org_id}/members/

List all members of an organization.

**Required role:** Owner

**Response `200 OK`:**
```json
[
  {
    "id": "uuid",
    "user": "uuid",
    "user_email": "admin@example.com",
    "user_name": "Jane Admin",
    "role": "admin",
    "joined_at": "2025-01-01T00:00:00Z"
  }
]
```

---

#### POST /organizations/{org_id}/members/

Add a user to the organization.

**Required role:** Owner

**Request body:**
```json
{
  "user": "uuid",
  "role": "member"
}
```

**Role options:** `owner`, `admin`, `member`

---

### Project Endpoints

#### GET /organizations/{org_id}/projects/

List all projects in an organization.

**Required role:** Member, Admin, or Owner

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| search | string | Search by project name |
| ordering | string | Sort field (e.g. `created_at`, `-created_at`) |

**Response `200 OK`:**
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "Product Launch",
      "description": "Q1 launch plan",
      "organization": "uuid",
      "created_by": "uuid",
      "created_by_email": "owner@example.com",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

#### POST /organizations/{org_id}/projects/

Create a new project.

**Required role:** Admin or Owner

**Request body:**
```json
{
  "name": "Product Launch",
  "description": "Q1 launch plan"
}
```

**Response `201 Created`:** Full project object.

---

#### GET /organizations/{org_id}/projects/{project_id}/

Retrieve a single project.

**Required role:** Member, Admin, or Owner

---

#### PATCH /organizations/{org_id}/projects/{project_id}/

Update a project.

**Required role:** Admin or Owner

---

#### DELETE /organizations/{org_id}/projects/{project_id}/

Delete a project. Cascades to all tasks within the project.

**Required role:** Admin or Owner

---

### Task Endpoints

#### GET /organizations/{org_id}/tasks/

List tasks in an organization with filtering, search, and cursor pagination.

**Required role:** Member, Admin, or Owner

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| status | string | Filter by status: `todo`, `in_progress`, `in_review`, `done`, `cancelled` |
| priority | string | Filter by priority: `low`, `medium`, `high`, `critical` |
| assigned_to | uuid | Filter by assignee user ID |
| project | uuid | Filter by project ID |
| due_before | date | Filter tasks due before date (YYYY-MM-DD) |
| due_after | date | Filter tasks due after date (YYYY-MM-DD) |
| search | string | Search in title and description |
| ordering | string | Sort by: `created_at`, `-created_at`, `due_date`, `priority` |
| cursor | string | Cursor for next/previous page |

**Response `200 OK`:**
```json
{
  "next": "http://localhost:8000/api/organizations/uuid/tasks/?cursor=xxx",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "title": "Build login page",
      "description": "JWT login flow",
      "status": "todo",
      "priority": "high",
      "due_date": "2025-03-01",
      "project": "uuid",
      "organization": "uuid",
      "assigned_to": "uuid",
      "assigned_to_email": "dev@example.com",
      "created_by": "uuid",
      "created_by_email": "owner@example.com",
      "dependencies": [],
      "version": 0,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

#### POST /organizations/{org_id}/tasks/

Create a new task.

**Required role:** Admin or Owner

**Request body:**
```json
{
  "title": "Build login page",
  "description": "Implement JWT login flow",
  "status": "todo",
  "priority": "high",
  "due_date": "2025-03-01",
  "project": "uuid",
  "assigned_to": "uuid"
}
```

**Status options:** `todo`, `in_progress`, `in_review`, `done`, `cancelled`

**Priority options:** `low`, `medium`, `high`, `critical`

**Response `201 Created`:** Full task object.

---

#### GET /organizations/{org_id}/tasks/{task_id}/

Retrieve a single task.

**Required role:** Member, Admin, or Owner

---

#### PATCH /organizations/{org_id}/tasks/{task_id}/

Update a task. Requires `version` field for optimistic locking.

**Required role:** Admin or Owner

**Request body:**
```json
{
  "title": "Updated title",
  "status": "in_progress",
  "version": 0
}
```

> **Important:** The `version` field must match the current version in the database. If another user has updated the task since you last fetched it, you will receive a `400` error. Refresh the task and retry.

**Response `200 OK`:** Updated task object with incremented version.

**Errors:**
- `400` — version mismatch (concurrent update detected)

---

#### DELETE /organizations/{org_id}/tasks/{task_id}/

Delete a task.

**Required role:** Admin or Owner

**Response `204 No Content`**

---

#### GET /organizations/{org_id}/tasks/prioritized/

Returns tasks sorted by urgency score (descending). Only returns active tasks (excludes `done` and `cancelled`). Limited to top 500 by recency for performance.

**Required role:** Member, Admin, or Owner

**Urgency score formula:**
```
urgency_score =
    (days_overdue × 3)
  + (priority_weight × 2)
  + dependency_block_count
  + assignee_workload_penalty
```

Where:
- `days_overdue` — days past due_date (0 if not yet due)
- `priority_weight` — low=1, medium=2, high=3, critical=4
- `dependency_block_count` — how many other tasks this task is blocking
- `assignee_workload_penalty` — how many active tasks the assignee already has

**Response `200 OK`:**
```json
[
  {
    "id": "uuid",
    "title": "Fix critical bug",
    "status": "in_progress",
    "priority": "critical",
    "due_date": "2025-01-01",
    "assigned_to_email": "dev@example.com",
    "urgency_score": 42.0
  }
]
```

---

#### POST /organizations/{org_id}/tasks/{task_id}/dependencies/

Add a dependency between tasks (task is blocked by another task).

**Required role:** Member, Admin, or Owner

**Request body:**
```json
{
  "depends_on_id": "uuid"
}
```

**Validation:**
- A task cannot depend on itself
- The dependency target must be in the same organization
- Circular dependencies are rejected (e.g. A→B→C→A)

**Response `201 Created`:**
```json
{
  "detail": "Dependency added."
}
```

**Errors:**
- `400` — self-dependency, cross-org task, or cycle detected

---

#### POST /organizations/{org_id}/tasks/bulk-import/

Import tasks from a CSV file. Accepts up to 10,000+ rows.

**Required role:** Admin or Owner

**Request:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| file | CSV file | Yes |
| project_id | UUID | Yes |

**CSV format:**

```csv
title,description,status,priority,due_date
"Build API","REST endpoints","todo","high","2025-03-01"
"Write tests","Unit tests","todo","medium",""
"Deploy","Production deploy","todo","critical","2025-02-15"
```

**CSV field rules:**
- `title` — required, non-empty string
- `status` — must be one of: `todo`, `in_progress`, `in_review`, `done`, `cancelled`
- `priority` — must be one of: `low`, `medium`, `high`, `critical`
- `due_date` — optional, format must be `YYYY-MM-DD`
- `description` — optional

**Response `207 Multi-Status`:**
```json
{
  "total_rows": 100,
  "created": 97,
  "failed": 3,
  "errors": [
    {
      "row": 4,
      "title": "",
      "errors": ["title is required"]
    },
    {
      "row": 12,
      "title": "Bad task",
      "errors": ["invalid status: flying"]
    },
    {
      "row": 45,
      "title": "Wrong date",
      "errors": ["due_date must be YYYY-MM-DD"]
    }
  ]
}
```

> **Transactional strategy:** Valid rows are saved regardless of other row failures (partial success). Invalid rows are skipped and reported. Duplicate tasks are silently ignored (`ignore_conflicts=True`).

---

### Audit Endpoints

#### GET /organizations/{org_id}/audit/task/{task_id}/

Retrieve the full audit history for a task. Returns all create, update, and delete events in reverse chronological order.

**Required role:** Member, Admin, or Owner

**Response `200 OK`:**
```json
[
  {
    "id": "uuid",
    "entity_type": "Task",
    "entity_id": "uuid",
    "action": "update",
    "user": "uuid",
    "user_email": "admin@example.com",
    "before_state": {
      "title": "Old title",
      "status": "todo",
      "priority": "medium",
      "due_date": null,
      "assigned_to_id": null,
      "version": 0
    },
    "after_state": {
      "title": "New title",
      "status": "in_progress",
      "priority": "high",
      "due_date": "2025-03-01",
      "assigned_to_id": "uuid",
      "version": 1
    },
    "created_at": "2025-01-15T10:30:00Z"
  },
  {
    "id": "uuid",
    "entity_type": "Task",
    "entity_id": "uuid",
    "action": "create",
    "user": "uuid",
    "user_email": "owner@example.com",
    "before_state": null,
    "after_state": {
      "title": "Old title",
      "status": "todo",
      "priority": "medium",
      "due_date": null,
      "assigned_to_id": null,
      "version": 0
    },
    "created_at": "2025-01-14T09:00:00Z"
  }
]
```

**Tracked events:**
- Task created — `before_state` is null
- Task updated — both states captured (title, status, priority, due_date, assigned_to, version)
- Task deleted — `after_state` is null
- Status changes — reflected in before/after state
- Assignment changes — `assigned_to_id` captured in before/after state

---

### Health Endpoint

#### GET /health/

Returns server health status. No authentication required.

**Response `200 OK`:**
```json
{
  "status": "ok"
}
```

---

## Architecture Decisions

### Multi-Tenancy Strategy

Every model that belongs to a tenant carries an `organization` foreign key. The `TenantQuerysetMixin` (in `core/mixins.py`) is applied to every ViewSet and enforces this at the `get_queryset()` level — the lowest possible enforcement point in DRF.

```
Request → JWT Auth → Permission Check → get_queryset() [tenant filter here] → Response
```

This means even if a developer forgets to add a permission class, the queryset itself is already scoped. Defense in depth.

IDOR protection is implemented by returning `404 Not Found` instead of `403 Forbidden` when a user accesses a resource in another organization — this avoids leaking whether the resource exists.

### JWT Strategy

- Access tokens: 60-minute lifetime — short enough to limit damage if stolen
- Refresh tokens: 7-day lifetime with rotation — old tokens blacklisted immediately after use
- Token blacklist: `rest_framework_simplejwt.token_blacklist` app handles this automatically

### Role-Based Permissions

Three roles with explicit hierarchy:

| Action | Owner | Admin | Member |
|--------|-------|-------|--------|
| Manage org members | ✅ | ❌ | ❌ |
| Create/delete projects | ✅ | ✅ | ❌ |
| Create/delete tasks | ✅ | ✅ | ❌ |
| Read tasks/projects | ✅ | ✅ | ✅ |
| Add dependencies | ✅ | ✅ | ✅ |
| View audit logs | ✅ | ✅ | ✅ |

### Optimistic Locking

Tasks have a `version: IntegerField(default=0)` column. Every PATCH/PUT must include the current `version`. The serializer validates that the submitted version matches the DB version before saving, then increments it. If another user saved between your read and write, the versions won't match and you get a `400` error.

**Why optimistic over pessimistic?**
- Tasks are read far more than written — no need to lock rows on reads
- Pessimistic locking holds DB row locks and can cause deadlocks under load
- Optimistic locking is stateless — works perfectly with JWT-based APIs
- Conflicts are rare in practice; optimistic locking has zero overhead on the happy path

### Audit Log via Django Signals

`pre_save` captures the before-state, `post_save` and `post_delete` write the log entry. `transaction.on_commit()` ensures the log is only written after the transaction successfully commits — no phantom audit logs for rolled-back changes.

A `CurrentUserMiddleware` stores the request user in thread-local storage so signals can attribute changes without being passed the request object.

### Cycle Detection Algorithm

DFS (Depth First Search) on the directed dependency graph.

**When adding dependency A → B (A blocked by B):**
1. Start DFS from node B
2. Recursively walk all outgoing edges (B's dependencies, their dependencies, etc.)
3. If we reach node A at any point → cycle detected → reject with `400`

**Complexity:** O(V + E) per insertion, where V = number of tasks, E = number of dependency edges. Worst case O(V²) for a fully connected graph, but dependency graphs in practice are sparse.

### Priority Score — SQL-Level Calculation

The urgency score is computed entirely in PostgreSQL using Django ORM annotations (subqueries + `CASE WHEN` + `ExpressionWrapper`). This means:

- No Python-level loops over tasks
- Sorting happens in DB — only the ordered result set is transferred
- Single round trip to the database regardless of dataset size

```
urgency_score =
    (days_overdue × 3)          -- cast to int, floored at 0
  + (priority_weight × 2)       -- CASE WHEN mapping
  + dependency_block_count       -- correlated subquery COUNT
  + assignee_workload_penalty    -- correlated subquery COUNT
```

---

## Security Considerations

### Tenant Isolation
- Enforced at queryset level (`get_queryset`), not just view level
- Returns 404 not 403 to avoid resource enumeration (IDOR protection)
- Every model query is scoped to `organization_id`
- Verified by 8 dedicated tenant isolation tests

### Authentication
- Passwords hashed with bcrypt via Django's `AbstractBaseUser`
- JWT tokens are short-lived (60 min access)
- Refresh token rotation prevents replay attacks
- Token blacklist prevents use of rotated tokens

### Authorization
- Role check happens before queryset evaluation
- Members cannot create, update, or delete tasks/projects
- Only Owners can manage organization membership
- 6 dedicated privilege escalation tests

### Input Validation
- All inputs validated via DRF serializers before DB write
- CSV imports validated row-by-row with explicit error messages
- UUID fields reject non-UUID values with `400`
- Dependency additions validated for cross-org and cycle safety

---

## Performance Considerations

### N+1 Query Prevention
- `select_related('assigned_to', 'created_by', 'project')` on all task queries
- `prefetch_related('dependencies')` for dependency lists
- Confirmed by `test_task_list_no_n_plus_1` test (asserts ≤ 6 queries for any list size)

### Prioritized Endpoint
- Urgency score computed in pure SQL using Django annotations
- Subqueries for `dependency_block_count` and `workload_penalty` run in the DB
- No Python loops over individual tasks
- Limited to 500 active tasks to keep response time under 10ms

### Cursor Pagination
- Used on `/tasks/` instead of offset pagination
- Cursor-based pagination uses a stable pointer — no `OFFSET` clause
- `OFFSET N` requires the DB to count and skip N rows — becomes slow at N=50,000+
- Cursor pagination is O(1) regardless of page number

### Database Indexes

| Table | Index | Purpose |
|-------|-------|---------|
| tasks | `(organization_id, status)` | Filter active tasks per org |
| tasks | `(organization_id, assigned_to_id)` | Filter by assignee per org |
| tasks | `(organization_id, priority)` | Filter by priority per org |
| tasks | `(due_date)` | Sort/filter overdue tasks |
| tasks | `(project_id)` | All tasks for a project |
| memberships | `(user_id, organization_id)` unique | Tenant auth check (every request) |
| audit_logs | `(entity_type, entity_id)` | Audit history per task |
| audit_logs | `(organization_id, created_at)` | Org-scoped audit queries |

### Bulk Import
- `Task.objects.bulk_create(tasks, ignore_conflicts=True)` — all valid rows in a single INSERT
- 10,000 rows = 1 query instead of 10,000 queries
- Invalid rows collected separately and reported without aborting valid rows

---

## Database Schema & Indexing

See full schema in [`docs/ERD.md`](docs/ERD.md).

### Entity Relationships

```
USER ──< MEMBERSHIP >── ORGANIZATION
ORGANIZATION ──< PROJECT
ORGANIZATION ──< TASK
PROJECT ──< TASK
USER ──< TASK (assigned_to)
USER ──< TASK (created_by)
TASK ──< TASK_DEPENDENCY >── TASK
USER ──< AUDIT_LOG
ORGANIZATION ──< AUDIT_LOG
```

---

## Testing

### Run all tests

```bash
pytest
```

### Run with coverage report

```bash
pytest --cov=apps --cov-report=term-missing -v
```

### Run specific test categories

```bash
# Security tests only
pytest tests/test_tenant_isolation.py -v

# Audit log tests
pytest tests/test_auth.py::TestAuditLog -v

# Edge case tests (locking, bulk import, cycles)
pytest tests/test_edge_cases.py -v

# Performance / N+1 guard
pytest tests/test_task.py::TestQueryPerformance -v
```

### Test results

```
58 passed in 29.86s — 93% coverage
```

### Test categories

| Category | File | Count | What it covers |
|----------|------|-------|----------------|
| Auth | `test_auth.py` | 9 | Register, login, refresh, token edge cases |
| Audit | `test_auth.py::TestAuditLog` | 7 | Create/update/delete logging, status/assignment capture |
| Tasks | `test_task.py` | 13 | CRUD, filtering, search, priority scoring, cycle detection |
| Security | `test_tenant_isolation.py` | 14 | Cross-tenant access, privilege escalation, unauthenticated access |
| Edge cases | `test_edge_cases.py` | 10 | Optimistic locking, bulk import failures, duplicates |
| Performance | `test_task.py::TestQueryPerformance` | 1 | N+1 query count assertion |

---

## Benchmarks

Tested against **100,000 task records** on local PostgreSQL (no tuning).

| Endpoint | Time | Queries | Notes |
|----------|------|---------|-------|
| `GET /tasks/` | **4.68ms** | 2 | Cursor pagination + indexes |
| `GET /tasks/prioritized/` | **1.39ms** | 1 | Full SQL annotation, top 20 active tasks |
| `GET /audit/task/{id}` | **1.32ms** | 1 | Indexed on `(entity_type, entity_id)` |
| Membership check (per request) | **0.37ms** | 1 | Indexed unique lookup |

### Bulk create throughput

```
100,000 tasks created in batches of 5,000
Total insertion time: ~30 seconds
= ~3,300 tasks/second using bulk_create
```

### Note on concurrent testing

True concurrent threading tests are unreliable in Django's test environment because the test runner wraps tests in a single transaction — separate threads share the same DB connection and don't see each other's commits. Optimistic locking behavior is verified through sequential stale-version tests which accurately simulate the conflict scenario. In production with real separate DB connections, the version check prevents simultaneous overwrites.

---

## Tradeoffs & Known Limitations

### Partial bulk import (not all-or-nothing)
Valid rows are saved even if other rows fail. This was a deliberate choice — an all-or-nothing strategy would reject an entire 10,000-row import because of one bad date format. The `207 Multi-Status` response clearly reports what succeeded and what failed.

### Cycle detection is per-insertion, not pre-validated
DFS runs at dependency creation time, not on bulk import. Bulk-imported tasks have no dependencies, so cycles can't be introduced through import.

### Prioritized endpoint is limited to 500 tasks
The formula scores tasks in SQL, but returning and serializing 75,000 JSON objects is slow regardless. The 500-task limit keeps response time under 10ms. In production this would be configurable per organization.

### No Celery/background jobs
Bulk import runs synchronously. For very large imports (100,000+ rows), a task queue (Celery + Redis) would be the next step. This is noted as a known tradeoff — the synchronous approach handles 10,000 rows reliably within request timeout limits.

### Audit log is Task-only
The assessment required auditing Task mutations. Project and Organization mutations are not currently audited. Extending to other models requires adding signal handlers in `apps/audit/signals.py` — the pattern is established.

---

## Seed Data

After running `python manage.py shell < scripts/seed.py`:

| Email | Password | Role | Organization |
|-------|----------|------|-------------|
| owner@demo.com | demo1234 | Owner | Demo Company |
| admin@demo.com | demo1234 | Admin | Demo Company |
| member@demo.com | demo1234 | Member | Demo Company |

The seed creates:
- 1 organization: **Demo Company**
- 1 project: **Product Launch**
- 5 tasks with varied priorities, statuses, and due dates
- 2 task dependencies (demonstrating the dependency graph)

### Quick demo flow

```bash
# 1. Login as owner
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@demo.com","password":"demo1234"}'

# 2. Copy the access token, then list tasks
curl http://localhost:8000/api/organizations/<org_id>/tasks/ \
  -H "Authorization: Bearer <access_token>"

# 3. Get prioritized tasks
curl http://localhost:8000/api/organizations/<org_id>/tasks/prioritized/ \
  -H "Authorization: Bearer <access_token>"
```

Or use the Swagger UI at **http://localhost:8000/api/docs/** — click **Authorize**, paste the Bearer token, and explore all endpoints interactively.

---

## Run benchmark script

```bash
python scripts/benchmark.py
```

Creates 100,000 tasks (if not already present) and measures query times for each endpoint pattern. Results are printed to stdout.

## Author 
Md. Sakibur Rahman 