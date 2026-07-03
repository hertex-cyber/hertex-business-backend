from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from sales_task_manager.models import (
    SalesProgramme, SalesTask, TargetAssignmentRule, SalesTaskLog
)


class TaskGenerator:
    """Engine for auto-generating tasks from targets and deal events"""

    def generate_from_target(self, target, user) -> list:
        """Generate tasks from a target's active assignment rules"""
        created_tasks = []

        # Find or create a programme for this target
        programme = self._get_or_create_programme(target)

        active_rules = target.assignment_rules.filter(
            trigger='TARGET_CREATED',
            is_active=True
        )

        if not active_rules.exists():
            # Create default tasks based on target breakdown
            created_tasks.extend(self._create_default_tasks(programme, target, user))
        else:
            for rule in active_rules:
                task = self._create_task_from_rule(rule, programme, target, user)
                if task:
                    created_tasks.append(task)

        return created_tasks

    def generate_from_rule(self, rule: TargetAssignmentRule, deal=None) -> SalesTask | None:
        """Generate a single task from a specific rule"""
        target = rule.sales_target
        programme = self._get_or_create_programme(target)
        user = target.assigned_by

        return self._create_task_from_rule(rule, programme, target, user, deal)

    def generate_recurring_tasks(self):
        """Generate weekly/monthly recurring tasks"""
        from sales_task_manager.models import TargetAssignmentRule
        from django.db.models import Q

        today = timezone.now().date()

        # Weekly rules
        weekly_rules = TargetAssignmentRule.objects.filter(
            trigger='WEEKLY',
            is_active=True,
            sales_target__cycle__status='ACTIVE'
        )

        for rule in weekly_rules:
            # Check if task already exists this week
            week_start = today - timedelta(days=today.weekday())
            existing = SalesTask.objects.filter(
                sales_target=rule.sales_target,
                task_type=rule.task_type,
                created_at__gte=week_start
            ).exists()

            if not existing:
                self._create_task_from_rule(rule, self._get_or_create_programme(rule.sales_target), rule.sales_target, None)

        # Monthly rules
        monthly_rules = TargetAssignmentRule.objects.filter(
            trigger='MONTHLY',
            is_active=True,
            sales_target__cycle__status='ACTIVE'
        )

        for rule in monthly_rules:
            # Check if task already exists this month
            month_start = today.replace(day=1)
            existing = SalesTask.objects.filter(
                sales_target=rule.sales_target,
                task_type=rule.task_type,
                created_at__gte=month_start
            ).exists()

            if not existing:
                self._create_task_from_rule(rule, self._get_or_create_programme(rule.sales_target), rule.sales_target, None)

    def _get_or_create_programme(self, target) -> SalesProgramme:
        """Find or create a default programme for the target"""
        programme_name = f"{target.cycle.name} - {target.assigned_user or 'Team'}"
        programme, created = SalesProgramme.objects.get_or_create(
            name=programme_name,
            target_cycle=target.cycle,
            defaults={
                'sales_target': target,
                'start_date': target.cycle.start_date,
                'end_date': target.cycle.end_date,
                'target_revenue': target.target_amount,
                'status': 'ACTIVE' if target.cycle.status == 'ACTIVE' else 'PLANNING',
            }
        )
        return programme

    def _create_default_tasks(self, programme, target, user) -> list:
        """Create default task breakdown for a target"""
        tasks = []
        default_task_configs = [
            ('Outbound Prospecting', 'CALL', Decimal('0.15')),
            ('Schedule Discovery Meetings', 'MEETING', Decimal('0.15')),
            ('Product Demonstrations', 'DEMO', Decimal('0.20')),
            ('Send Proposals', 'PROPOSAL', Decimal('0.20')),
            ('Negotiation & Closing', 'NEGOTIATION', Decimal('0.20')),
            ('Post-Sale Follow-up', 'FOLLOW_UP', Decimal('0.10')),
        ]

        for title, task_type, weight in default_task_configs:
            task = SalesTask.objects.create(
                programme=programme,
                sales_target=target,
                title=f"{title} - {target.cycle.name}",
                description=f"Default task for target {target}",
                task_type=task_type,
                priority='MEDIUM',
                status='TODO',
                assigned_to=target.assigned_user,
                assigned_by=user or target.assigned_by,
                due_date=target.cycle.end_date,
                revenue_impact=target.target_amount * weight,
                weight_pct=weight * Decimal('100'),
                is_auto_generated=True,
            )
            tasks.append(task)

            SalesTaskLog.objects.create(
                task=task,
                user=user or target.assigned_by,
                activity_type='TASK_CREATED',
                description=f"Auto-generated task '{task.title}' from target",
                metadata={
                    'target_id': str(target.id),
                    'auto_generated': True,
                    'task_type': task_type,
                }
            )

        return tasks

    def _create_task_from_rule(self, rule, programme, target, user, deal=None) -> SalesTask | None:
        """Create a task from an assignment rule with template substitution"""
        from contacts.models import Contact

        # Build title from template
        title = rule.task_title_template
        if deal:
            title = title.replace('{{deal_name}}', str(deal.contact.name if hasattr(deal, 'contact') and deal.contact else 'Unknown Deal'))
            contact = deal.contact if hasattr(deal, 'contact') else None
            if contact:
                title = title.replace('{{contact_name}}', contact.name)
        title = title.replace('{{target_amount}}', str(float(target.target_amount)))
        title = title.replace('{{cycle_name}}', target.cycle.name)

        description = rule.task_description_template
        if deal:
            description = description.replace('{{deal_name}}', str(getattr(deal.contact, 'name', 'Unknown') if hasattr(deal, 'contact') and deal.contact else 'Unknown'))

        # Calculate due date
        due_date = None
        if rule.due_date_offset_days:
            due_date = timezone.now().date() + timedelta(days=rule.due_date_offset_days)

        # Determine assignee based on strategy
        assigned_to = None
        from sales_task_manager.services.assignment_engine import AssignmentEngine
        engine = AssignmentEngine()
        assigned_to = engine.assign_by_strategy(rule, target, deal, programme)

        task = SalesTask.objects.create(
            programme=programme,
            sales_target=target,
            title=title,
            description=description,
            task_type=rule.task_type,
            priority=rule.priority,
            status='TODO',
            assigned_to=assigned_to,
            assigned_by=user or target.assigned_by,
            due_date=due_date,
            crm_deal=deal,
            revenue_impact=target.target_amount / Decimal('10') if target.target_amount else 0,
            is_auto_generated=True,
        )

        SalesTaskLog.objects.create(
            task=task,
            user=user or target.assigned_by,
            activity_type='TASK_CREATED',
            description=f"Auto-generated task '{task.title}' from rule '{rule.get_trigger_display()}'",
            metadata={
                'rule_id': str(rule.id),
                'trigger': rule.trigger,
                'auto_generated': True,
            }
        )

        return task
