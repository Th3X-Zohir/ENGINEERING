from datetime import date
from django.db import transaction
from .models import Task, TaskDependency


# ─── Cycle Detection ────────────────────────────────────────────────
def has_cycle(task_id, new_dep_id):
    """
    DFS to detect if adding new_dep_id as a dependency of task_id
    would create a cycle.

    Algorithm: walk the dependency graph from new_dep_id.
    If we reach task_id, a cycle exists.

    Complexity: O(V + E) where V=tasks, E=dependencies
    """
    visited = set()

    def dfs(current_id):
        if current_id == task_id:
            return True          # found a path back — cycle!
        if current_id in visited:
            return False         # already explored this node
        visited.add(current_id)
        # get all tasks that current_id depends on
        deps = TaskDependency.objects.filter(
            task_id=current_id
        ).values_list('depends_on_id', flat=True)
        return any(dfs(dep_id) for dep_id in deps)

    return dfs(new_dep_id)


# ─── Priority Score ──────────────────────────────────────────────────
def calculate_urgency_score(task, assignee_workload: dict):
    """
    urgency_score =
        (days_overdue * 3)
        + (priority_weight * 2)
        + dependency_block_count
        + assignee_workload_penalty
    """
    today = date.today()

    # days overdue (0 if not due yet)
    days_overdue = 0
    if task.due_date and task.due_date < today:
        days_overdue = (today - task.due_date).days

    # priority weight: low=1, medium=2, high=3, critical=4
    priority_weight = Task.PRIORITY_WEIGHTS.get(task.priority, 1)

    # how many tasks are blocked by THIS task
    dependency_block_count = task.dependents.count()

    # how many tasks the assignee already has (fetched once, passed in)
    assignee_workload_penalty = 0
    if task.assigned_to_id:
        assignee_workload_penalty = assignee_workload.get(task.assigned_to_id, 0)

    score = (
        (days_overdue * 3)
        + (priority_weight * 2)
        + dependency_block_count
        + assignee_workload_penalty
    )
    return score


def get_prioritized_tasks(queryset):
    """
    Returns tasks sorted by urgency score descending.
    Fetches workload counts in one query to avoid N+1.
    """
    from django.db.models import Count

    # single query to get workload per assignee
    workload_qs = (
        Task.objects
        .filter(
            assigned_to__isnull=False,
            status__in=['todo', 'in_progress']
        )
        .values('assigned_to_id')
        .annotate(count=Count('id'))
    )
    assignee_workload = {
        row['assigned_to_id']: row['count']
        for row in workload_qs
    }

    # eager load related data to avoid N+1
    tasks = queryset.prefetch_related('dependents', 'dependencies').select_related(
        'assigned_to', 'created_by', 'project'
    )

    # score each task in Python
    scored = [
        (task, calculate_urgency_score(task, assignee_workload))
        for task in tasks
    ]

    # sort descending by score
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored


# ─── Bulk Import ─────────────────────────────────────────────────────
def bulk_import_tasks(rows, organization, project, created_by):
    """
    Processes a list of dicts from CSV.
    Returns summary with success count and per-row errors.
    """
    created = []
    errors = []

    valid_statuses = [s.value for s in Task.Status]
    valid_priorities = [p.value for p in Task.Priority]

    for i, row in enumerate(rows, start=1):
        row_errors = []

        title = row.get('title', '').strip()
        if not title:
            row_errors.append('title is required')

        status = row.get('status', 'todo').strip().lower()
        if status not in valid_statuses:
            row_errors.append(f'invalid status: {status}')

        priority = row.get('priority', 'medium').strip().lower()
        if priority not in valid_priorities:
            row_errors.append(f'invalid priority: {priority}')

        due_date = None
        raw_due = row.get('due_date', '').strip()
        if raw_due:
            try:
                from datetime import datetime
                due_date = datetime.strptime(raw_due, '%Y-%m-%d').date()
            except ValueError:
                row_errors.append('due_date must be YYYY-MM-DD')

        if row_errors:
            errors.append({'row': i, 'title': title, 'errors': row_errors})
            continue

        created.append(Task(
            organization=organization,
            project=project,
            created_by=created_by,
            title=title,
            description=row.get('description', '').strip(),
            status=status,
            priority=priority,
            due_date=due_date,
        ))

    # bulk insert in one query — much faster than individual saves
    if created:
        Task.objects.bulk_create(created, ignore_conflicts=True)

    return {
        'total_rows': len(rows),
        'created': len(created),
        'failed': len(errors),
        'errors': errors,
    }