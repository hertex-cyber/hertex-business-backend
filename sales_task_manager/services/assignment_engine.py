from django.db.models import Count, Q
from sales_task_manager.models import SalesTask, TargetAssignmentRule


class AssignmentEngine:
    """Core engine for intelligent task assignment"""

    def assign_by_strategy(self, rule: TargetAssignmentRule, target, deal=None, programme=None):
        """Determine assignee based on strategy"""
        strategy = rule.assignment_strategy

        if strategy == 'DEAL_OWNER' and deal:
            return self._assign_deal_owner(deal)

        elif strategy == 'TARGET_OWNER':
            return self._assign_target_owner(target)

        elif strategy == 'LEAST_LOADED':
            return self._assign_least_loaded(target, programme)

        elif strategy == 'ROUND_ROBIN':
            return self._assign_round_robin(target, programme)

        elif strategy == 'MANAGER':
            return self._assign_manager(target)

        return None

    def _assign_deal_owner(self, deal):
        """Assign to whoever owns the linked CRM deal"""
        if hasattr(deal, 'assigned_user') and deal.assigned_user:
            return deal.assigned_user
        return None

    def _assign_target_owner(self, target):
        """Assign to the user whose target it falls under"""
        return target.assigned_user

    def _assign_least_loaded(self, target, programme):
        """Find user with fewest active tasks"""
        if not programme:
            return target.assigned_user

        eligible_users = list(programme.team_members.all())
        if not eligible_users:
            return target.assigned_user

        # Count active tasks per user in this programme
        user_loads = {}
        for user in eligible_users:
            count = SalesTask.objects.filter(
                programme=programme,
                assigned_to=user,
                status__in=['TODO', 'IN_PROGRESS']
            ).count()
            user_loads[user] = count

        # Return the user with the lowest load
        return min(user_loads, key=user_loads.get)

    def _assign_round_robin(self, target, programme):
        """Cycle through eligible users sequentially"""
        if not programme:
            return target.assigned_user

        eligible_users = list(programme.team_members.all())
        if not eligible_users:
            return target.assigned_user

        # Find the last assigned task in this programme
        last_task = SalesTask.objects.filter(
            programme=programme,
            assigned_to__in=eligible_users,
            is_auto_generated=True
        ).order_by('-created_at').first()

        if last_task and last_task.assigned_to in eligible_users:
            try:
                last_index = eligible_users.index(last_task.assigned_to)
                next_index = (last_index + 1) % len(eligible_users)
                return eligible_users[next_index]
            except ValueError:
                return eligible_users[0]

        return eligible_users[0]

    def _assign_manager(self, target):
        """Assign to the programme manager"""
        if hasattr(target, 'programmes') and target.programmes.exists():
            programme = target.programmes.first()
            if programme.programme_manager:
                return programme.programme_manager
        return None
