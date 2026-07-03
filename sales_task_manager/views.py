from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from sales_task_manager.models import (
    TargetCycle, SalesTarget, TargetLineItem, SalesProgramme,
    ProgrammeMilestone, SalesTask, TaskDependency, TaskTimeLog,
    ProgrammeResourceAllocation, TargetAssignmentRule, TaskAttachment,
    SalesTaskLog
)
from sales_task_manager.serializers import (
    TargetCycleSerializer, SalesTargetSerializer, TargetLineItemSerializer,
    SalesProgrammeSerializer, SalesProgrammeListSerializer,
    ProgrammeMilestoneSerializer, SalesTaskSerializer, SalesTaskDetailSerializer,
    TaskDependencySerializer, TaskTimeLogSerializer,
    ProgrammeResourceAllocationSerializer, TargetAssignmentRuleSerializer,
    TaskAttachmentSerializer, SalesTaskLogSerializer
)
from sales_task_manager.permissions import (
    IsSalesManager, IsSalesAdmin, IsTaskOwnerOrManager,
    CanAssignTasks, CanManageProgrammes, CanManageConfig
)
from sales_task_manager.services.progress_tracker import ProgressTracker


# ============================================================================
# TARGET CYCLE VIEWSET
# ============================================================================

class TargetCycleViewSet(viewsets.ModelViewSet):
    queryset = TargetCycle.objects.all().order_by('-start_date')
    serializer_class = TargetCycleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['cycle_type', 'status']
    search_fields = ['name', 'code']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'activate', 'close']:
            permission_classes = [IsSalesAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate cycle → auto-generate tasks if enabled"""
        cycle = self.get_object()
        cycle.status = 'ACTIVE'
        cycle.save()

        # Trigger auto-generation if enabled
        if cycle.task_auto_generation_enabled:
            self._auto_generate_tasks(cycle, request.user)

        return Response({'success': True, 'message': f'Cycle {cycle.name} activated'})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close cycle, finalise attainment"""
        cycle = self.get_object()
        cycle.status = 'CLOSED'
        cycle.save()

        # Finalise all targets
        for target in cycle.sales_targets.all():
            ProgressTracker.finalise_target(target)

        return Response({'success': True, 'message': f'Cycle {cycle.name} closed'})

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Dashboard summary data for the cycle"""
        cycle = self.get_object()
        targets = cycle.sales_targets.all()
        programmes = cycle.programmes.all()

        total_target = targets.aggregate(total=Sum('target_amount'))['total'] or 0
        total_achieved = targets.aggregate(total=Sum('achieved_amount'))['total'] or 0

        return Response({
            'total_target': total_target,
            'total_achieved': total_achieved,
            'attainment_pct': round((total_achieved / total_target * 100), 2) if total_target else 0,
            'total_targets': targets.count(),
            'achieved_targets': targets.filter(status__in=['ACHIEVED', 'EXCEEDED']).count(),
            'total_programmes': programmes.count(),
            'active_programmes': programmes.filter(status='ACTIVE').count(),
        })

    def _auto_generate_tasks(self, cycle, user):
        """Auto-generate tasks for all active targets"""
        from sales_task_manager.services.task_generator import TaskGenerator
        generator = TaskGenerator()
        for target in cycle.sales_targets.all():
            generator.generate_from_target(target, user)


# ============================================================================
# SALES TARGET VIEWSET
# ============================================================================

class SalesTargetViewSet(viewsets.ModelViewSet):
    queryset = SalesTarget.objects.all().select_related(
        'cycle', 'assigned_user', 'assigned_by'
    ).prefetch_related('line_items')
    serializer_class = SalesTargetSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['cycle', 'assigned_user', 'assigned_department', 'status', 'assignee_type']
    search_fields = ['assigned_user__email', 'assigned_user__first_name', 'notes']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'assign', 'bulk_create']:
            permission_classes = [IsSalesManager]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign target to a user/team"""
        target = self.get_object()
        user_id = request.data.get('assigned_user')
        dept_id = request.data.get('assigned_department')

        if user_id:
            from authentication.models import User
            try:
                user = User.objects.get(id=user_id)
                target.assigned_user = user
                target.assignee_type = 'USER'
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)

        if dept_id:
            from authentication.models import Department
            try:
                dept = Department.objects.get(id=dept_id)
                target.assigned_department = dept
                target.assignee_type = 'DEPARTMENT'
            except Department.DoesNotExist:
                return Response({'error': 'Department not found'}, status=status.HTTP_400_BAD_REQUEST)

        target.save()
        return Response(SalesTargetSerializer(target).data)

    @action(detail=True, methods=['post'])
    def generate_tasks(self, request, pk=None):
        """Auto-generate tasks from this target"""
        target = self.get_object()
        from sales_task_manager.services.task_generator import TaskGenerator
        generator = TaskGenerator()
        tasks = generator.generate_from_target(target, request.user)
        return Response({
            'message': f'Generated {len(tasks)} tasks',
            'tasks': SalesTaskSerializer(tasks, many=True).data
        })

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Weighted progress calculation"""
        target = self.get_object()
        tracker = ProgressTracker()
        progress = tracker.calculate_target_progress(target)
        return Response(progress)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create targets from a list"""
        data = request.data.get('targets', [])
        if not data:
            return Response({'error': 'No targets provided'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        errors = []
        for idx, item in enumerate(data):
            serializer = self.get_serializer(data=item)
            if serializer.is_valid():
                serializer.save(assigned_by=request.user)
                created.append(serializer.data)
            else:
                errors.append({'index': idx, 'errors': serializer.errors})

        return Response({
            'created_count': len(created),
            'error_count': len(errors),
            'created': created,
            'errors': errors,
        })


# ============================================================================
# TARGET LINE ITEM VIEWSET
# ============================================================================

class TargetLineItemViewSet(viewsets.ModelViewSet):
    queryset = TargetLineItem.objects.all().select_related('sales_target', 'crm_deal')
    serializer_class = TargetLineItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sales_target', 'crm_deal', 'line_item_type', 'is_attained']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsSalesManager]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]


# ============================================================================
# SALES PROGRAMME VIEWSET
# ============================================================================

class SalesProgrammeViewSet(viewsets.ModelViewSet):
    queryset = SalesProgramme.objects.all().select_related(
        'target_cycle', 'sales_target', 'programme_manager'
    ).prefetch_related('milestones', 'resource_allocations', 'team_members')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['target_cycle', 'sales_target', 'status', 'priority', 'programme_manager']
    search_fields = ['name', 'description']

    def get_serializer_class(self):
        if self.action == 'list':
            return SalesProgrammeListSerializer
        return SalesProgrammeSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'add_member', 'remove_member']:
            permission_classes = [CanManageProgrammes]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        programme = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        from authentication.models import User
        try:
            user = User.objects.get(id=user_id)
            programme.team_members.add(user)
            return Response({'message': f'Added {user.get_full_name()} to programme'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        programme = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        from authentication.models import User
        try:
            user = User.objects.get(id=user_id)
            programme.team_members.remove(user)
            return Response({'message': f'Removed {user.get_full_name()} from programme'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def gantt(self, request, pk=None):
        """Gantt chart data — tasks grouped by assignee with dependencies"""
        programme = self.get_object()
        tasks = programme.tasks.all().select_related('assigned_to').prefetch_related('dependencies', 'dependent_tasks')

        task_data = []
        for task in tasks:
            task_data.append({
                'id': str(task.id),
                'title': task.title,
                'assignee': task.assigned_to.get_full_name() if task.assigned_to else 'Unassigned',
                'status': task.status,
                'priority': task.priority,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'estimated_hours': float(task.estimated_hours) if task.estimated_hours else None,
                'revenue_impact': float(task.revenue_impact),
                'weight_pct': float(task.weight_pct),
                'dependencies': [str(d.depends_on.id) for d in task.dependencies.all()],
                'order': task.order,
            })

        milestones = []
        for m in programme.milestones.all():
            milestones.append({
                'id': str(m.id),
                'name': m.name,
                'target_date': m.target_date.isoformat(),
                'completed_date': m.completed_date.isoformat() if m.completed_date else None,
                'status': m.status,
                'revenue_impact': float(m.revenue_impact),
            })

        return Response({
            'tasks': task_data,
            'milestones': milestones,
        })

    @action(detail=True, methods=['get'])
    def resource_load(self, request, pk=None):
        """Resource allocation view"""
        programme = self.get_object()
        allocations = programme.resource_allocations.all().select_related('user')

        resource_data = []
        for alloc in allocations:
            active_tasks = SalesTask.objects.filter(
                programme=programme,
                assigned_to=alloc.user,
                status__in=['TODO', 'IN_PROGRESS']
            ).count()

            resource_data.append({
                'user_id': str(alloc.user.id),
                'user_name': alloc.user.get_full_name(),
                'role': alloc.get_role_display(),
                'allocation_pct': float(alloc.allocation_pct),
                'active_tasks': active_tasks,
                'start_date': alloc.start_date.isoformat(),
                'end_date': alloc.end_date.isoformat(),
            })

        return Response(resource_data)


# ============================================================================
# PROGRAMME MILESTONE VIEWSET
# ============================================================================

class ProgrammeMilestoneViewSet(viewsets.ModelViewSet):
    queryset = ProgrammeMilestone.objects.all().select_related('programme')
    serializer_class = ProgrammeMilestoneSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['programme', 'milestone_type', 'status']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'achieve']:
            permission_classes = [IsSalesManager]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    @action(detail=True, methods=['post'])
    def achieve(self, request, pk=None):
        """Mark milestone achieved"""
        milestone = self.get_object()
        milestone.status = 'ACHIEVED'
        milestone.completed_date = timezone.now().date()
        milestone.save()

        # Log the achievement
        SalesTaskLog.objects.create(
            sales_target=milestone.programme.sales_target,
            user=request.user,
            activity_type='MILESTONE_ACHIEVED',
            description=f"Milestone '{milestone.name}' achieved in programme '{milestone.programme.name}'",
            metadata={'milestone_id': str(milestone.id), 'revenue_impact': float(milestone.revenue_impact)}
        )

        return Response(ProgrammeMilestoneSerializer(milestone).data)


# ============================================================================
# SALES TASK VIEWSET
# ============================================================================

class SalesTaskViewSet(viewsets.ModelViewSet):
    queryset = SalesTask.objects.all().select_related(
        'programme', 'sales_target', 'assigned_to', 'assigned_by',
        'crm_deal', 'contact'
    ).prefetch_related('dependencies', 'dependent_tasks', 'time_logs', 'attachments', 'activity_logs')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        'programme': ['exact'],
        'assigned_to': ['exact'],
        'sales_target': ['exact'],
        'status': ['exact'],
        'priority': ['exact'],
        'task_type': ['exact'],
        'crm_deal': ['exact'],
        'is_auto_generated': ['exact'],
        'due_date': ['exact', 'gte', 'lte'],
    }
    search_fields = ['title', 'description']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SalesTaskDetailSerializer
        return SalesTaskSerializer

    def get_permissions(self):
        if self.action in ['destroy', 'assign', 'bulk_update_status', 'bulk_reorder']:
            permission_classes = [IsSalesManager]
        elif self.action in ['create', 'update', 'partial_update']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        # Staff users see only their own tasks
        if user.is_authenticated and user.role == 'Staff':
            qs = qs.filter(assigned_to=user)

        return qs

    def perform_create(self, serializer):
        task = serializer.save(assigned_by=self.request.user)
        SalesTaskLog.objects.create(
            task=task,
            user=self.request.user,
            activity_type='TASK_CREATED',
            description=f"Task '{task.title}' created",
            metadata={'programme_id': str(task.programme.id) if task.programme else None}
        )

    def perform_update(self, serializer):
        old = self.get_object()
        task = serializer.save()

        # Log status changes
        if old.status != task.status:
            SalesTaskLog.objects.create(
                task=task,
                user=self.request.user,
                activity_type='TASK_STATUS_CHANGED',
                description=f"Status changed from {old.get_status_display()} to {task.get_status_display()}",
                metadata={'old_status': old.status, 'new_status': task.status}
            )

        # Log assignment changes
        if old.assigned_to != task.assigned_to:
            SalesTaskLog.objects.create(
                task=task,
                user=self.request.user,
                activity_type='TASK_REASSIGNED' if old.assigned_to else 'TASK_ASSIGNED',
                description=f"Assigned to {task.assigned_to.get_full_name() if task.assigned_to else 'Unassigned'}",
                metadata={
                    'old_assignee': str(old.assigned_to.id) if old.assigned_to else None,
                    'new_assignee': str(task.assigned_to.id) if task.assigned_to else None
                }
            )

        # Log due date changes
        if old.due_date != task.due_date:
            SalesTaskLog.objects.create(
                task=task,
                user=self.request.user,
                activity_type='TASK_DUE_DATE_CHANGED',
                description=f"Due date changed from {old.due_date} to {task.due_date}",
                metadata={'old_due_date': old.due_date.isoformat() if old.due_date else None,
                          'new_due_date': task.due_date.isoformat() if task.due_date else None}
            )

        # Log priority changes
        if old.priority != task.priority:
            SalesTaskLog.objects.create(
                task=task,
                user=self.request.user,
                activity_type='TASK_PRIORITY_CHANGED',
                description=f"Priority changed from {old.get_priority_display()} to {task.get_priority_display()}",
                metadata={'old_priority': old.priority, 'new_priority': task.priority}
            )

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        SalesTaskLog.objects.create(
            task=task,
            user=request.user,
            activity_type='TASK_STATUS_CHANGED',
            description=f"Task '{task.title}' deleted",
            metadata={'deleted': True}
        )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign/reassign task"""
        task = self.get_object()
        user_id = request.data.get('assigned_to')
        if not user_id:
            return Response({'error': 'assigned_to is required'}, status=status.HTTP_400_BAD_REQUEST)

        from authentication.models import User
        try:
            user = User.objects.get(id=user_id)
            old_assignee = task.assigned_to
            task.assigned_to = user
            task.save()

            SalesTaskLog.objects.create(
                task=task,
                user=request.user,
                activity_type='TASK_REASSIGNED' if old_assignee else 'TASK_ASSIGNED',
                description=f"Task assigned to {user.get_full_name()}",
                metadata={
                    'old_assignee': str(old_assignee.id) if old_assignee else None,
                    'new_assignee': str(user.id),
                }
            )

            return Response(SalesTaskSerializer(task).data)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a task (set started_at)"""
        task = self.get_object()
        task.status = 'IN_PROGRESS'
        task.started_at = timezone.now()
        task.save()

        SalesTaskLog.objects.create(
            task=task,
            user=request.user,
            activity_type='TASK_STATUS_CHANGED',
            description=f"Task started",
            metadata={'status': 'IN_PROGRESS'}
        )

        return Response(SalesTaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete a task"""
        task = self.get_object()
        task.status = 'DONE'
        task.completed_at = timezone.now()

        # Calculate actual hours if started_at is set
        if task.started_at and not task.actual_hours:
            delta = timezone.now() - task.started_at
            task.actual_hours = round(delta.total_seconds() / 3600, 2)

        task.save()

        SalesTaskLog.objects.create(
            task=task,
            user=request.user,
            activity_type='TASK_STATUS_CHANGED',
            description=f"Task completed",
            metadata={'status': 'DONE'}
        )

        return Response(SalesTaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Mark task as blocked"""
        task = self.get_object()
        reason = request.data.get('reason', 'No reason provided')
        task.status = 'BLOCKED'
        task.save()

        SalesTaskLog.objects.create(
            task=task,
            user=request.user,
            activity_type='TASK_STATUS_CHANGED',
            description=f"Task blocked: {reason}",
            metadata={'status': 'BLOCKED', 'reason': reason}
        )

        return Response(SalesTaskSerializer(task).data)

    @action(detail=False, methods=['post'])
    def bulk_reorder(self, request):
        """Reorder tasks (drag & drop)"""
        items = request.data.get('items', [])
        for item in items:
            SalesTask.objects.filter(id=item['id']).update(order=item['order'])
        return Response({'success': True, 'updated': len(items)})

    @action(detail=False, methods=['post'])
    def bulk_update_status(self, request):
        """Bulk status change"""
        task_ids = request.data.get('task_ids', [])
        new_status = request.data.get('status')
        if not task_ids or not new_status:
            return Response({'error': 'task_ids and status are required'}, status=status.HTTP_400_BAD_REQUEST)

        updated = SalesTask.objects.filter(id__in=task_ids).update(status=new_status)

        for task in SalesTask.objects.filter(id__in=task_ids):
            SalesTaskLog.objects.create(
                task=task,
                user=request.user,
                activity_type='TASK_STATUS_CHANGED',
                description=f"Bulk status changed to {new_status}",
                metadata={'new_status': new_status, 'bulk': True}
            )

        return Response({'success': True, 'updated': updated})

    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """Current user's active tasks"""
        tasks = SalesTask.objects.filter(
            assigned_to=request.user
        ).exclude(
            status__in=['DONE', 'CANCELLED']
        ).select_related('programme').order_by('due_date', 'priority')

        page = self.paginate_queryset(tasks)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_deal(self, request):
        """All tasks for a deal"""
        deal_id = request.query_params.get('deal_id')
        if not deal_id:
            return Response({'error': 'deal_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        tasks = SalesTask.objects.filter(crm_deal_id=deal_id).select_related(
            'programme', 'assigned_to'
        ).order_by('due_date')

        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)


# ============================================================================
# TASK DEPENDENCY VIEWSET
# ============================================================================

class TaskDependencyViewSet(viewsets.ModelViewSet):
    queryset = TaskDependency.objects.all().select_related('task', 'depends_on')
    serializer_class = TaskDependencySerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            permission_classes = [IsSalesManager]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]


# ============================================================================
# TIME TRACKING VIEWSET
# ============================================================================

class TaskTimeLogViewSet(viewsets.ModelViewSet):
    queryset = TaskTimeLog.objects.all().select_related('task', 'user')
    serializer_class = TaskTimeLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['task', 'user', 'date']

    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            permission_classes = [IsTaskOwnerOrManager]
        elif self.action == 'destroy':
            permission_classes = [IsSalesAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Time summary per user/programme"""
        programme_id = request.query_params.get('programme')
        user_id = request.query_params.get('user')

        qs = TaskTimeLog.objects.all()
        if programme_id:
            qs = qs.filter(task__programme_id=programme_id)
        if user_id:
            qs = qs.filter(user_id=user_id)

        summary = qs.values('user', 'task__programme').annotate(
            total_hours=Sum('hours'),
            log_count=Count('id')
        )

        return Response(list(summary))


# ============================================================================
# RESOURCE ALLOCATION VIEWSET
# ============================================================================

class ProgrammeResourceAllocationViewSet(viewsets.ModelViewSet):
    queryset = ProgrammeResourceAllocation.objects.all().select_related('programme', 'user')
    serializer_class = ProgrammeResourceAllocationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['programme', 'user', 'role']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [CanManageProgrammes]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]


# ============================================================================
# ASSIGNMENT RULE VIEWSET
# ============================================================================

class TargetAssignmentRuleViewSet(viewsets.ModelViewSet):
    queryset = TargetAssignmentRule.objects.all().select_related('sales_target')
    serializer_class = TargetAssignmentRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sales_target', 'trigger', 'assignment_strategy', 'is_active']
    permission_classes = [CanManageConfig]


# ============================================================================
# TASK ATTACHMENT VIEWSET
# ============================================================================

class TaskAttachmentViewSet(viewsets.ModelViewSet):
    queryset = TaskAttachment.objects.all().select_related('task', 'uploaded_by')
    serializer_class = TaskAttachmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['task']

    def get_permissions(self):
        if self.action == 'destroy':
            permission_classes = [IsSalesAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


# ============================================================================
# SALES TASK LOG VIEWSET (read-only)
# ============================================================================

class SalesTaskLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SalesTaskLog.objects.all().select_related('task', 'sales_target', 'user')
    serializer_class = SalesTaskLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['task', 'sales_target', 'user', 'activity_type']
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        # Staff see only their own task logs
        if user.is_authenticated and user.role == 'Staff':
            qs = qs.filter(Q(task__assigned_to=user) | Q(user=user))

        return qs


# ============================================================================
# DASHBOARD VIEWSET (non-model, aggregate data)
# ============================================================================

class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def executive(self, request):
        """VP/CRO executive overview"""
        from authentication.models import User

        # Top-level stats
        total_target = TargetCycle.objects.filter(status='ACTIVE').aggregate(
            total=Sum('total_revenue_target')
        )['total'] or 0

        total_achieved = SalesTarget.objects.filter(
            cycle__status='ACTIVE'
        ).aggregate(total=Sum('achieved_amount'))['total'] or 0

        active_programmes = SalesProgramme.objects.filter(status='ACTIVE')
        total_programmes = active_programmes.count()
        at_risk_programmes = active_programmes.filter(status='ACTIVE', priority='CRITICAL').count()

        # Top performers
        top_reps = SalesTarget.objects.filter(
            cycle__status='ACTIVE', assignee_type='USER'
        ).exclude(assigned_user__isnull=True).values(
            'assigned_user', 'assigned_user__first_name', 'assigned_user__last_name'
        ).annotate(
            total_target=Sum('target_amount'),
            total_achieved=Sum('achieved_amount')
        ).order_by('-total_achieved')[:10]

        return Response({
            'total_target': total_target,
            'total_achieved': total_achieved,
            'attainment_pct': round(total_achieved / total_target * 100, 2) if total_target else 0,
            'active_programmes': total_programmes,
            'at_risk_programmes': at_risk_programmes,
            'top_performers': [
                {
                    'name': f"{r['assigned_user__first_name']} {r['assigned_user__last_name']}".strip(),
                    'target': r['total_target'],
                    'achieved': r['total_achieved'],
                    'attainment_pct': round(r['total_achieved'] / r['total_target'] * 100, 2) if r['total_target'] else 0,
                }
                for r in top_reps
            ],
        })

    @action(detail=False, methods=['get'])
    def manager(self, request):
        """Manager's team overview"""
        # Find team members under this manager
        team_members = User.objects.filter(supervisor=request.user)

        team_targets = SalesTarget.objects.filter(
            assigned_user__in=team_members,
            cycle__status='ACTIVE'
        )

        team_tasks = SalesTask.objects.filter(
            assigned_to__in=team_members,
            programme__target_cycle__status='ACTIVE'
        )

        return Response({
            'team_size': team_members.count(),
            'total_target': team_targets.aggregate(total=Sum('target_amount'))['total'] or 0,
            'total_achieved': team_targets.aggregate(total=Sum('achieved_amount'))['total'] or 0,
            'task_summary': {
                'total': team_tasks.count(),
                'done': team_tasks.filter(status='DONE').count(),
                'in_progress': team_tasks.filter(status='IN_PROGRESS').count(),
                'blocked': team_tasks.filter(status='BLOCKED').count(),
                'todo': team_tasks.filter(status='TODO').count(),
            },
            'team_members': [
                {
                    'id': str(m.id),
                    'name': m.get_full_name(),
                    'target': team_targets.filter(assigned_user=m).aggregate(total=Sum('target_amount'))['total'] or 0,
                    'achieved': team_targets.filter(assigned_user=m).aggregate(total=Sum('achieved_amount'))['total'] or 0,
                }
                for m in team_members
            ],
        })

    @action(detail=False, methods=['get'])
    def my_target(self, request):
        """Rep's personal dashboard"""
        my_targets = SalesTarget.objects.filter(
            assigned_user=request.user,
            cycle__status='ACTIVE'
        )

        my_tasks = SalesTask.objects.filter(
            assigned_to=request.user,
            programme__target_cycle__status='ACTIVE'
        )

        today_tasks = my_tasks.filter(
            due_date=timezone.now().date()
        ).exclude(status__in=['DONE', 'CANCELLED'])

        return Response({
            'targets': SalesTargetSerializer(my_targets, many=True).data,
            'task_summary': {
                'total': my_tasks.count(),
                'done': my_tasks.filter(status='DONE').count(),
                'in_progress': my_tasks.filter(status='IN_PROGRESS').count(),
                'blocked': my_tasks.filter(status='BLOCKED').count(),
                'todo': my_tasks.filter(status='TODO').count(),
            },
            'today_tasks': SalesTaskSerializer(today_tasks, many=True).data,
            'time_logged_today': TaskTimeLog.objects.filter(
                user=request.user,
                date=timezone.now().date()
            ).aggregate(total=Sum('hours'))['total'] or 0,
        })
