from decimal import Decimal
from django.db.models import Sum
from sales_task_manager.models import SalesTarget, SalesTask


STATUS_FACTORS = {
    'DONE': Decimal('1.0'),
    'IN_REVIEW': Decimal('0.8'),
    'IN_PROGRESS': Decimal('0.5'),
    'TODO': Decimal('0.0'),
    'BACKLOG': Decimal('0.0'),
    'BLOCKED': Decimal('0.0'),
    'CANCELLED': Decimal('0.0'),
}


class ProgressTracker:
    """Calculate weighted progress for targets and programmes"""

    @staticmethod
    def calculate_target_progress(target: SalesTarget) -> dict:
        """Calculate weighted progress for a specific target"""
        tasks = SalesTask.objects.filter(sales_target=target)

        if not tasks.exists():
            return {
                'target_id': str(target.id),
                'weighted_progress_pct': float(target.weighted_progress_pct),
                'total_tasks': 0,
                'completed_tasks': 0,
                'revenue_weighted_pct': 0,
            }

        total_weighted_progress = Decimal('0.0')
        total_max_weight = Decimal('0.0')

        for task in tasks:
            weight = task.weight_pct / Decimal('100.0')
            factor = STATUS_FACTORS.get(task.status, Decimal('0.0'))
            revenue_factor = task.revenue_impact

            weighted = weight * revenue_factor * factor
            max_weighted = weight * revenue_factor

            total_weighted_progress += weighted
            total_max_weight += max_weighted

        progress_pct = float(
            (total_weighted_progress / total_max_weight * Decimal('100'))
            if total_max_weight > 0 else 0
        )

        # Update the target's weighted_progress_pct
        target.weighted_progress_pct = Decimal(str(round(progress_pct, 2)))
        target.save(update_fields=['weighted_progress_pct'])

        return {
            'target_id': str(target.id),
            'weighted_progress_pct': round(progress_pct, 2),
            'total_tasks': tasks.count(),
            'completed_tasks': tasks.filter(status='DONE').count(),
            'revenue_weighted_pct': round(progress_pct, 2),
        }

    @staticmethod
    def calculate_programme_health(programme) -> dict:
        """Calculate programme health score"""
        milestone_health = 0
        tasks = programme.tasks.all()
        milestones = programme.milestones.all()

        # Task completion (weighted)
        task_completion = 0
        if tasks.exists():
            total_weighted = Decimal('0.0')
            achieved_weighted = Decimal('0.0')
            for task in tasks:
                weight = task.weight_pct / Decimal('100.0')
                factor = STATUS_FACTORS.get(task.status, Decimal('0.0'))
                total_weighted += weight
                achieved_weighted += weight * factor
            task_completion = float(achieved_weighted / total_weighted * 100) if total_weighted > 0 else 0

        # Milestone health
        if milestones.exists():
            achieved = milestones.filter(status='ACHIEVED').count()
            milestone_health = (achieved / milestones.count()) * 100

        # Revenue attainment
        revenue_attainment = 0
        if programme.target_revenue > 0:
            revenue_attainment = float(programme.actual_revenue / programme.target_revenue * 100)

        # Health score (weighted: 30% milestones, 30% tasks, 40% revenue)
        health_score = (
            milestone_health * 0.3 +
            task_completion * 0.3 +
            revenue_attainment * 0.4
        )

        # Determine health status
        if health_score >= 80:
            health_status = 'on_track'
        elif health_score >= 50:
            health_status = 'at_risk'
        else:
            health_status = 'behind'

        return {
            'programme_id': str(programme.id),
            'health_score': round(health_score, 1),
            'health_status': health_status,
            'task_completion_pct': round(task_completion, 1),
            'milestone_achievement_pct': round(milestone_health, 1),
            'revenue_attainment_pct': round(revenue_attainment, 1),
        }

    @staticmethod
    def check_dependencies(task: SalesTask) -> dict:
        """Check if a task's dependencies are satisfied"""
        dependencies = task.dependencies.all()
        if not dependencies.exists():
            return {'blocked': False, 'unmet_dependencies': []}

        unmet = []
        for dep in dependencies:
            if dep.dependency_type == 'FINISH_TO_START':
                if dep.depends_on.status != 'DONE':
                    unmet.append({
                        'dependency_id': str(dep.id),
                        'depends_on': str(dep.depends_on.id),
                        'depends_on_title': dep.depends_on.title,
                        'depends_on_status': dep.depends_on.status,
                        'type': 'FINISH_TO_START',
                    })

        return {
            'blocked': len(unmet) > 0,
            'unmet_dependencies': unmet,
        }

    @staticmethod
    def get_critical_path(tasks) -> list:
        """Identify the critical path from a task queryset"""
        # Build dependency graph
        task_map = {str(t.id): t for t in tasks}
        in_degree = {}
        for task in tasks:
            in_degree[str(task.id)] = 0
            for dep in task.dependencies.all():
                dep_id = str(dep.depends_on.id)
                if dep.dependency_type == 'FINISH_TO_START' and dep.depends_on.status != 'DONE':
                    if dep_id in in_degree:
                        in_degree[str(task.id)] += 1

        # Topological sort
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        topo_order = []

        while queue:
            current = queue.pop(0)
            topo_order.append(current)
            task = task_map.get(current)
            if task:
                for dep in task.dependent_tasks.all():
                    dep_id = str(dep.task.id)
                    if dep_id in in_degree:
                        in_degree[dep_id] -= 1
                        if in_degree[dep_id] == 0:
                            queue.append(dep_id)

        return topo_order

    @staticmethod
    def finalise_target(target: SalesTarget):
        """Calculate final progress and update target status"""
        progress = ProgressTracker.calculate_target_progress(target)

        # Determine status based on achieved amount vs target
        if target.achieved_amount >= target.target_amount:
            target.status = 'ACHIEVED'
            if target.achieved_amount > target.target_amount * Decimal('1.1'):
                target.status = 'EXCEEDED'
        elif target.achieved_amount > 0:
            target.status = 'IN_PROGRESS'
        else:
            target.status = 'NOT_STARTED'

        target.weighted_progress_pct = Decimal(str(progress['weighted_progress_pct']))
        target.save(update_fields=['status', 'weighted_progress_pct'])
