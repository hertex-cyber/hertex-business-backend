from rest_framework import serializers
from sales_task_manager.models import (
    TargetCycle, SalesTarget, TargetLineItem, SalesProgramme,
    ProgrammeMilestone, SalesTask, TaskDependency, TaskTimeLog,
    ProgrammeResourceAllocation, TargetAssignmentRule, TaskAttachment,
    SalesTaskLog
)
from authentication.serializers import UserSerializer
from authentication.models import User


# ============================================================================
# TARGET CYCLE SERIALIZER
# ============================================================================

class TargetCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetCycle
        fields = [
            'id', 'name', 'code', 'cycle_type', 'start_date', 'end_date',
            'status', 'total_revenue_target', 'task_auto_generation_enabled',
            'sprint_duration_days', 'appraisal_cycle',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# TARGET LINE ITEM SERIALIZER
# ============================================================================

class TargetLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetLineItem
        fields = [
            'id', 'sales_target', 'crm_deal',
            'description', 'expected_amount', 'expected_close_date',
            'line_item_type', 'probability',
            'is_attained', 'attained_date', 'actual_revenue',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# SALES TARGET SERIALIZER
# ============================================================================

class SalesTargetSerializer(serializers.ModelSerializer):
    line_items = TargetLineItemSerializer(many=True, read_only=True)
    assigned_user_details = UserSerializer(source='assigned_user', read_only=True)
    assigned_by_details = UserSerializer(source='assigned_by', read_only=True)

    class Meta:
        model = SalesTarget
        fields = [
            'id', 'cycle', 'assignee_type',
            'assigned_user', 'assigned_user_details',
            'assigned_department',
            'target_amount', 'achieved_amount', 'weighted_progress_pct',
            'status', 'new_business_target', 'renewal_target', 'upsell_target',
            'assigned_by', 'assigned_by_details', 'notes',
            'line_items',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'achieved_amount', 'weighted_progress_pct', 'created_at', 'updated_at']


# ============================================================================
# PROGRAMME MILESTONE SERIALIZER
# ============================================================================

class ProgrammeMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgrammeMilestone
        fields = [
            'id', 'programme', 'name', 'description',
            'target_date', 'completed_date', 'milestone_type',
            'status', 'revenue_impact',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# TASK DEPENDENCY SERIALIZER
# ============================================================================

class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDependency
        fields = ['id', 'task', 'depends_on', 'dependency_type', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# TIME LOG SERIALIZER
# ============================================================================

class TaskTimeLogSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = TaskTimeLog
        fields = [
            'id', 'task', 'user', 'user_details',
            'date', 'hours', 'description',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# TASK ATTACHMENT SERIALIZER
# ============================================================================

class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_details = UserSerializer(source='uploaded_by', read_only=True)

    class Meta:
        model = TaskAttachment
        fields = [
            'id', 'task', 'file', 'file_name', 'file_size',
            'note', 'url', 'uploaded_by', 'uploaded_by_details',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'file_size', 'created_at', 'updated_at']


# ============================================================================
# SALES TASK LOG SERIALIZER
# ============================================================================

class SalesTaskLogSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = SalesTaskLog
        fields = [
            'id', 'task', 'sales_target', 'user', 'user_details',
            'activity_type', 'description', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# RESOURCE ALLOCATION SERIALIZER
# ============================================================================

class ProgrammeResourceAllocationSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = ProgrammeResourceAllocation
        fields = [
            'id', 'programme', 'user', 'user_details',
            'allocation_pct', 'start_date', 'end_date', 'role',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# ASSIGNMENT RULE SERIALIZER
# ============================================================================

class TargetAssignmentRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetAssignmentRule
        fields = [
            'id', 'sales_target', 'trigger', 'task_type',
            'task_title_template', 'task_description_template',
            'due_date_offset_days', 'priority', 'assignment_strategy',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# SALES TASK DETAIL SERIALIZER (nested)
# ============================================================================

class SalesTaskDetailSerializer(serializers.ModelSerializer):
    assigned_to_details = UserSerializer(source='assigned_to', read_only=True)
    assigned_by_details = UserSerializer(source='assigned_by', read_only=True)
    dependencies = TaskDependencySerializer(many=True, read_only=True)
    dependent_tasks = TaskDependencySerializer(many=True, read_only=True)
    time_logs = TaskTimeLogSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    activity_logs = SalesTaskLogSerializer(many=True, read_only=True)

    class Meta:
        model = SalesTask
        fields = [
            'id', 'programme', 'sales_target',
            'title', 'description', 'task_type', 'priority', 'status',
            'assigned_to', 'assigned_to_details',
            'assigned_by', 'assigned_by_details',
            'due_date', 'started_at', 'completed_at',
            'estimated_hours', 'actual_hours',
            'crm_deal', 'contact',
            'revenue_impact', 'weight_pct', 'order',
            'is_auto_generated',
            'dependencies', 'dependent_tasks',
            'time_logs', 'attachments', 'activity_logs',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# SALES TASK LIST SERIALIZER (flat, lighter)
# ============================================================================

class SalesTaskSerializer(serializers.ModelSerializer):
    assigned_to_details = UserSerializer(source='assigned_to', read_only=True)

    class Meta:
        model = SalesTask
        fields = [
            'id', 'programme', 'sales_target',
            'title', 'description', 'task_type', 'priority', 'status',
            'assigned_to', 'assigned_to_details',
            'assigned_by',
            'due_date', 'started_at', 'completed_at',
            'estimated_hours', 'actual_hours',
            'crm_deal', 'contact',
            'revenue_impact', 'weight_pct', 'order',
            'is_auto_generated',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# SALES PROGRAMME SERIALIZER
# ============================================================================

class SalesProgrammeSerializer(serializers.ModelSerializer):
    milestones = ProgrammeMilestoneSerializer(many=True, read_only=True)
    resource_allocations = ProgrammeResourceAllocationSerializer(many=True, read_only=True)
    programme_manager_details = UserSerializer(source='programme_manager', read_only=True)

    class Meta:
        model = SalesProgramme
        fields = [
            'id', 'name', 'description',
            'target_cycle', 'sales_target',
            'start_date', 'end_date',
            'priority', 'status',
            'target_revenue', 'actual_revenue',
            'team_members', 'programme_manager', 'programme_manager_details',
            'milestones', 'resource_allocations',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'actual_revenue', 'created_at', 'updated_at']


# ============================================================================
# SALES PROGRAMME LIST SERIALIZER (lighter)
# ============================================================================

class SalesProgrammeListSerializer(serializers.ModelSerializer):
    programme_manager_details = UserSerializer(source='programme_manager', read_only=True)
    task_summary = serializers.SerializerMethodField()

    class Meta:
        model = SalesProgramme
        fields = [
            'id', 'name', 'target_cycle',
            'start_date', 'end_date', 'priority', 'status',
            'target_revenue', 'actual_revenue',
            'programme_manager', 'programme_manager_details',
            'task_summary',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_task_summary(self, obj):
        tasks = obj.tasks.all()
        return {
            'total': tasks.count(),
            'done': tasks.filter(status='DONE').count(),
            'in_progress': tasks.filter(status='IN_PROGRESS').count(),
            'blocked': tasks.filter(status='BLOCKED').count(),
            'todo': tasks.filter(status='TODO').count(),
        }
