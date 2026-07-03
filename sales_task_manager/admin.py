from django.contrib import admin
from sales_task_manager.models import (
    TargetCycle, SalesTarget, TargetLineItem, SalesProgramme,
    ProgrammeMilestone, SalesTask, TaskDependency, TaskTimeLog,
    ProgrammeResourceAllocation, TargetAssignmentRule, TaskAttachment,
    SalesTaskLog
)


@admin.register(TargetCycle)
class TargetCycleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'cycle_type', 'start_date', 'end_date', 'status', 'total_revenue_target']
    list_filter = ['cycle_type', 'status', 'start_date']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']


class TargetLineItemInline(admin.TabularInline):
    model = TargetLineItem
    extra = 1
    fields = ['description', 'expected_amount', 'expected_close_date', 'line_item_type', 'probability', 'is_attained']


@admin.register(SalesTarget)
class SalesTargetAdmin(admin.ModelAdmin):
    list_display = ['cycle', 'assigned_user', 'assigned_department', 'target_amount', 'achieved_amount', 'weighted_progress_pct', 'status']
    list_filter = ['cycle', 'status', 'assignee_type']
    search_fields = ['assigned_user__email', 'assigned_user__first_name', 'assigned_department__name']
    readonly_fields = ['achieved_amount', 'weighted_progress_pct', 'created_at', 'updated_at']
    inlines = [TargetLineItemInline]


@admin.register(TargetLineItem)
class TargetLineItemAdmin(admin.ModelAdmin):
    list_display = ['description', 'sales_target', 'expected_amount', 'expected_close_date', 'line_item_type', 'probability', 'is_attained']
    list_filter = ['line_item_type', 'probability', 'is_attained']
    search_fields = ['description']
    readonly_fields = ['created_at', 'updated_at']


class ProgrammeMilestoneInline(admin.TabularInline):
    model = ProgrammeMilestone
    extra = 1
    fields = ['name', 'target_date', 'milestone_type', 'status', 'revenue_impact']


class ProgrammeResourceAllocationInline(admin.TabularInline):
    model = ProgrammeResourceAllocation
    extra = 1


@admin.register(SalesProgramme)
class SalesProgrammeAdmin(admin.ModelAdmin):
    list_display = ['name', 'target_cycle', 'status', 'priority', 'start_date', 'end_date', 'target_revenue']
    list_filter = ['status', 'priority', 'target_cycle']
    search_fields = ['name', 'description']
    readonly_fields = ['actual_revenue', 'created_at', 'updated_at']
    inlines = [ProgrammeMilestoneInline, ProgrammeResourceAllocationInline]
    filter_horizontal = ['team_members']


@admin.register(ProgrammeMilestone)
class ProgrammeMilestoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'programme', 'target_date', 'milestone_type', 'status', 'revenue_impact']
    list_filter = ['milestone_type', 'status']
    search_fields = ['name', 'programme__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SalesTask)
class SalesTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'programme', 'task_type', 'priority', 'status', 'assigned_to', 'due_date', 'revenue_impact']
    list_filter = ['status', 'priority', 'task_type', 'programme']
    search_fields = ['title', 'description']
    readonly_fields = ['is_auto_generated', 'started_at', 'completed_at', 'created_at', 'updated_at']


@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ['task', 'depends_on', 'dependency_type']
    list_filter = ['dependency_type']
    search_fields = ['task__title', 'depends_on__title']


@admin.register(TaskTimeLog)
class TaskTimeLogAdmin(admin.ModelAdmin):
    list_display = ['task', 'user', 'date', 'hours']
    list_filter = ['date', 'user']
    search_fields = ['task__title', 'user__email']


@admin.register(ProgrammeResourceAllocation)
class ProgrammeResourceAllocationAdmin(admin.ModelAdmin):
    list_display = ['user', 'programme', 'allocation_pct', 'start_date', 'end_date', 'role']
    list_filter = ['role', 'programme']
    search_fields = ['user__email', 'programme__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TargetAssignmentRule)
class TargetAssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ['sales_target', 'trigger', 'task_type', 'assignment_strategy', 'is_active']
    list_filter = ['trigger', 'assignment_strategy', 'is_active']
    search_fields = ['sales_target__assigned_user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ['task', 'file_name', 'file_size', 'uploaded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['file_name', 'task__title']


@admin.register(SalesTaskLog)
class SalesTaskLogAdmin(admin.ModelAdmin):
    list_display = ['activity_type', 'task', 'sales_target', 'user', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['description', 'task__title']
    readonly_fields = ['created_at', 'updated_at']
