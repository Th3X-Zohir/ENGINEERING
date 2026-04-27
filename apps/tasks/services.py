from datetime import date
from django.db import transaction
from .models import Task, TaskDependency
from django.db import models
from django.db.models import F, ExpressionWrapper, Case, When, Value, Count, OuterRef, Subquery
from django.db.models.functions import Now, ExtractDay, Greatest, Cast


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
def calculate_urgency_score():
    """
    Defines the mathematical formula for urgency as a Django SQL Expression.
    Formula: (days_overdue * 3) + (priority_weight * 2) + block_count + workload_penalty
    """
    
    # 1. Days Overdue Calculation
    # If due_date is in the past, get days. If future, result is 0.
    days_overdue_expr = Greatest(
        ExtractDay(Now() - F('due_date')),
        0
    )

    # 2. Priority Weight Mapping
    # low=1, medium=2, high=3, critical=4
    priority_weight_expr = Case(
        When(priority='critical', then=Value(4)),
        When(priority='high', then=Value(3)),
        When(priority='medium', then=Value(2)),
        default=Value(1),
        output_field=models.IntegerField(),
    )

    # 3. Handling Nulls for Subqueries
    # Ensures that if a task has 0 dependents or 0 workload, the math doesn't result in NULL
    def clean_null(field):
        return Case(When(**{f"{field}__isnull": False}, then=F(field)), default=Value(0))

    # 4. The Combined Formula
    return ExpressionWrapper(
        (Cast(days_overdue_expr, models.IntegerField()) * 3) +
        (priority_weight_expr * 2) +
        clean_null('dependency_block_count') +
        clean_null('workload_penalty'),
        output_field=models.FloatField()
    )

def get_prioritized_tasks(queryset):
    """
    Applies the urgency logic to a queryset using annotations.
    """
    
    # Subquery: Count tasks blocked by THIS task
    dependents_subquery = TaskDependency.objects.filter(
        depends_on_id=OuterRef('pk')
    ).values('depends_on_id').annotate(count=Count('id')).values('count')

    # Subquery: Count current assignee workload
    workload_subquery = Task.objects.filter(
        assigned_to_id=OuterRef('assigned_to_id'),
        status__in=['todo', 'in_progress']
    ).values('assigned_to_id').annotate(count=Count('id')).values('count')

    return queryset.annotate(
        dependency_block_count=Subquery(dependents_subquery, output_field=models.IntegerField()),
        workload_penalty=Subquery(workload_subquery, output_field=models.IntegerField()),
    ).annotate(
        # Attach the score using our separate calculation function
        _urgency_score=calculate_urgency_score()
    ).order_by('-_urgency_score')



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