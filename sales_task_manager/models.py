from django.db import models
from core.models import Main


class TargetCycle(Main):
    """Defines a target period — Annual, Half-Yearly, or Quarterly"""

    CYCLE_TYPE_CHOICES = (
        ('ANNUAL', 'Annual'),
        ('HALF_YEARLY', 'Half-Yearly'),
        ('QUARTERLY', 'Quarterly'),
        ('MONTHLY', 'Monthly'),
    )

    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
        ('ARCHIVED', 'Archived'),
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    cycle_type = models.CharField(max_length=20, choices=CYCLE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    total_revenue_target = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    task_auto_generation_enabled = models.BooleanField(default=True)
    sprint_duration_days = models.IntegerField(default=14)

    # Optional link to HR AppraisalCycle
    appraisal_cycle = models.ForeignKey(
        'hr.AppraisalCycle', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='target_cycles'
    )

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Target Cycle'
        verbose_name_plural = 'Target Cycles'

    def __str__(self):
        return f"{self.name} ({self.get_cycle_type_display()})"


class SalesTarget(Main):
    """Individual or team-level target for a specific cycle"""

    ASSIGNEE_TYPE_CHOICES = (
        ('USER', 'Individual'),
        ('TEAM', 'Team'),
        ('DEPARTMENT', 'Department'),
    )

    STATUS_CHOICES = (
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('ACHIEVED', 'Achieved'),
        ('EXCEEDED', 'Exceeded'),
        ('MISSED', 'Missed'),
    )

    cycle = models.ForeignKey(TargetCycle, on_delete=models.CASCADE, related_name='sales_targets')

    assignee_type = models.CharField(max_length=20, choices=ASSIGNEE_TYPE_CHOICES, default='USER')

    assigned_user = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_targets'
    )
    assigned_department = models.ForeignKey(
        'authentication.Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_targets'
    )

    target_amount = models.DecimalField(max_digits=15, decimal_places=2)
    achieved_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    weighted_progress_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')

    new_business_target = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    renewal_target = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    upsell_target = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    assigned_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_targets'
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('cycle', 'assignee_type', 'assigned_user', 'assigned_department')
        verbose_name = 'Sales Target'
        verbose_name_plural = 'Sales Targets'
        indexes = [
            models.Index(fields=['cycle', 'assigned_user']),
            models.Index(fields=['cycle', 'assigned_department']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        assignee = self.assigned_user or self.assigned_department
        return f"{self.cycle.name} \u2192 {assignee}: \u20b9{self.target_amount}"


class TargetLineItem(Main):
    """A specific revenue expectation — linked to a CRM deal or a new opportunity"""

    LINE_ITEM_TYPE_CHOICES = (
        ('NEW_BUSINESS', 'New Business'),
        ('RENEWAL', 'Renewal'),
        ('UPSELL', 'Upsell'),
        ('EXPANSION', 'Expansion'),
    )

    PROBABILITY_CHOICES = (
        ('LOW', 'Low (<25%)'),
        ('MEDIUM', 'Medium (25-50%)'),
        ('HIGH', 'High (50-75%)'),
        ('COMMITTED', 'Committed (>75%)'),
    )

    sales_target = models.ForeignKey(SalesTarget, on_delete=models.CASCADE, related_name='line_items')

    crm_deal = models.ForeignKey(
        'crm.CRM', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='target_line_items'
    )

    description = models.CharField(max_length=255)
    expected_amount = models.DecimalField(max_digits=15, decimal_places=2)
    expected_close_date = models.DateField()
    line_item_type = models.CharField(max_length=20, choices=LINE_ITEM_TYPE_CHOICES, default='NEW_BUSINESS')
    probability = models.CharField(max_length=20, choices=PROBABILITY_CHOICES, default='MEDIUM')
    is_attained = models.BooleanField(default=False)
    attained_date = models.DateField(null=True, blank=True)
    actual_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Target Line Item'
        verbose_name_plural = 'Target Line Items'
        ordering = ['expected_close_date']

    def __str__(self):
        return f"{self.description} \u2014 \u20b9{self.expected_amount}"


class SalesProgramme(Main):
    """A focused sales initiative — the 'project' in our sales+PM hybrid"""

    PRIORITY_CHOICES = (
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    )

    STATUS_CHOICES = (
        ('PLANNING', 'Planning'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    target_cycle = models.ForeignKey(
        TargetCycle, on_delete=models.CASCADE, related_name='programmes'
    )
    sales_target = models.ForeignKey(
        SalesTarget, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='programmes'
    )

    start_date = models.DateField()
    end_date = models.DateField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNING')

    target_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    actual_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    team_members = models.ManyToManyField(
        'authentication.User', blank=True, related_name='sales_programmes'
    )

    programme_manager = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_programmes'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sales Programme'
        verbose_name_plural = 'Sales Programmes'
        indexes = [
            models.Index(fields=['target_cycle', 'status']),
            models.Index(fields=['priority', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class ProgrammeMilestone(Main):
    """Significant events within a programme"""

    MILESTONE_TYPE_CHOICES = (
        ('REVENUE_GATE', 'Revenue Gate'),
        ('CLOSE_DATE', 'Close Date'),
        ('ACTIVITY_TARGET', 'Activity Target'),
        ('TEAM_BUILDING', 'Team Building'),
        ('PRODUCT_LAUNCH', 'Product Launch'),
        ('TRAINING', 'Training'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('ACHIEVED', 'Achieved'),
        ('MISSED', 'Missed'),
    )

    programme = models.ForeignKey(
        SalesProgramme, on_delete=models.CASCADE, related_name='milestones'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    revenue_impact = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        ordering = ['target_date']
        verbose_name = 'Programme Milestone'
        verbose_name_plural = 'Programme Milestones'

    def __str__(self):
        return f"{self.programme.name} \u2192 {self.name} ({self.target_date})"


class SalesTask(Main):
    """The atomic unit of work — deeply connected to CRM deals and targets."""

    TASK_TYPE_CHOICES = (
        ('CALL', 'Call'),
        ('MEETING', 'Meeting'),
        ('DEMO', 'Demo'),
        ('PROPOSAL', 'Proposal'),
        ('QUOTE', 'Quote'),
        ('FOLLOW_UP', 'Follow Up'),
        ('EMAIL', 'Email'),
        ('RESEARCH', 'Research'),
        ('NEGOTIATION', 'Negotiation'),
        ('CONTRACT_REVIEW', 'Contract Review'),
        ('INTERNAL_REVIEW', 'Internal Review'),
        ('CLOSING', 'Closing'),
        ('OTHER', 'Other'),
    )

    PRIORITY_CHOICES = (
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    )

    STATUS_CHOICES = (
        ('BACKLOG', 'Backlog'),
        ('TODO', 'To Do'),
        ('IN_PROGRESS', 'In Progress'),
        ('IN_REVIEW', 'In Review'),
        ('DONE', 'Done'),
        ('BLOCKED', 'Blocked'),
        ('CANCELLED', 'Cancelled'),
    )

    programme = models.ForeignKey(
        SalesProgramme, on_delete=models.CASCADE, related_name='tasks'
    )
    sales_target = models.ForeignKey(
        SalesTarget, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    task_type = models.CharField(max_length=30, choices=TASK_TYPE_CHOICES, default='OTHER')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')

    assigned_to = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_tasks'
    )
    assigned_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_tasks'
    )

    due_date = models.DateField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    crm_deal = models.ForeignKey(
        'crm.CRM', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_tasks'
    )
    contact = models.ForeignKey(
        'contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_tasks'
    )

    revenue_impact = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        help_text="Estimated revenue impact if this task is completed"
    )

    weight_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.00,
        help_text="Relative weight for progress calculation (0-100%)"
    )

    order = models.PositiveIntegerField(default=0)

    is_auto_generated = models.BooleanField(
        default=False,
        help_text="True if created automatically by target engine"
    )

    class Meta:
        ordering = ['order', 'due_date', 'created_at']
        verbose_name = 'Sales Task'
        verbose_name_plural = 'Sales Tasks'
        indexes = [
            models.Index(fields=['programme', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['crm_deal']),
            models.Index(fields=['due_date']),
            models.Index(fields=['sales_target']),
        ]

    def __str__(self):
        return f"{self.title} ({self.assigned_to or 'Unassigned'})"


class TaskDependency(Main):
    """Track dependencies between tasks — borrowed from PM tools"""

    DEPENDENCY_TYPE_CHOICES = (
        ('FINISH_TO_START', 'Finish \u2192 Start'),
        ('START_TO_START', 'Start \u2192 Start'),
        ('FINISH_TO_FINISH', 'Finish \u2192 Finish'),
        ('START_TO_FINISH', 'Start \u2192 Finish'),
    )

    task = models.ForeignKey(
        SalesTask, on_delete=models.CASCADE, related_name='dependencies'
    )
    depends_on = models.ForeignKey(
        SalesTask, on_delete=models.CASCADE, related_name='dependent_tasks'
    )
    dependency_type = models.CharField(
        max_length=20, choices=DEPENDENCY_TYPE_CHOICES, default='FINISH_TO_START'
    )

    class Meta:
        unique_together = ('task', 'depends_on')
        verbose_name = 'Task Dependency'
        verbose_name_plural = 'Task Dependencies'

    def __str__(self):
        return f"{self.task.title} depends on {self.depends_on.title}"


class TaskTimeLog(Main):
    """Time spent on a task — for effort tracking and load analysis"""

    task = models.ForeignKey(SalesTask, on_delete=models.CASCADE, related_name='time_logs')
    user = models.ForeignKey('authentication.User', on_delete=models.CASCADE)
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Task Time Log'
        verbose_name_plural = 'Task Time Logs'

    def __str__(self):
        return f"{self.user.get_full_name()} \u2014 {self.task.title}: {self.hours}h"


class ProgrammeResourceAllocation(Main):
    """Track how much of a person's time is allocated to each programme"""

    ROLE_CHOICES = (
        ('LEAD', 'Programme Lead'),
        ('SDR', 'SDR'),
        ('AE', 'Account Executive'),
        ('SE', 'Solutions Engineer'),
        ('CSM', 'Customer Success'),
        ('MANAGER', 'Manager'),
        ('SUPPORT', 'Support'),
    )

    programme = models.ForeignKey(
        SalesProgramme, on_delete=models.CASCADE, related_name='resource_allocations'
    )
    user = models.ForeignKey('authentication.User', on_delete=models.CASCADE)
    allocation_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Percentage of user's time allocated (e.g., 50.00 = 50%)"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='AE')

    class Meta:
        unique_together = ('programme', 'user', 'start_date')
        verbose_name = 'Resource Allocation'
        verbose_name_plural = 'Resource Allocations'

    def __str__(self):
        return f"{self.user.get_full_name()} \u2014 {self.programme.name}: {self.allocation_pct}%"


class TargetAssignmentRule(Main):
    """Rules for auto-generating tasks when targets are set or deals move stages"""

    TRIGGER_CHOICES = (
        ('TARGET_CREATED', 'On Target Creation'),
        ('DEAL_STAGE_CHANGE', 'On Deal Stage Change'),
        ('DEAL_CREATED', 'On Deal Created'),
        ('WEEKLY', 'Weekly Recurring'),
        ('MONTHLY', 'Monthly Recurring'),
        ('MANUAL', 'Manual Only'),
    )

    ASSIGNMENT_STRATEGY_CHOICES = (
        ('DEAL_OWNER', 'Deal Owner'),
        ('TARGET_OWNER', 'Target Owner'),
        ('LEAST_LOADED', 'Least Loaded'),
        ('ROUND_ROBIN', 'Round Robin'),
        ('MANAGER', 'Manager'),
    )

    sales_target = models.ForeignKey(
        SalesTarget, on_delete=models.CASCADE, related_name='assignment_rules'
    )

    trigger = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    task_type = models.CharField(max_length=30, choices=SalesTask.TASK_TYPE_CHOICES)
    task_title_template = models.CharField(
        max_length=255,
        help_text="Use {{deal_name}}, {{contact_name}}, {{target_amount}} as variables"
    )
    task_description_template = models.TextField(blank=True)
    due_date_offset_days = models.IntegerField(
        default=7,
        help_text="Days from trigger date to set as due date"
    )
    priority = models.CharField(max_length=20, choices=SalesTask.PRIORITY_CHOICES, default='MEDIUM')
    assignment_strategy = models.CharField(
        max_length=20, choices=ASSIGNMENT_STRATEGY_CHOICES, default='TARGET_OWNER'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Assignment Rule'
        verbose_name_plural = 'Assignment Rules'

    def __str__(self):
        return f"{self.sales_target} \u2192 {self.get_task_type_display()} ({self.get_trigger_display()})"


class TaskAttachment(Main):
    """Files, notes, or links attached to a task"""

    task = models.ForeignKey(SalesTask, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/%Y/%m/', null=True, blank=True)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    note = models.TextField(blank=True)
    url = models.URLField(blank=True)
    uploaded_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Attachment'
        verbose_name_plural = 'Task Attachments'

    def __str__(self):
        return f"{self.task.title} \u2014 {self.file_name}"


class SalesTaskLog(Main):
    """Activity log for all task and target changes — matches ByteHive's ContactLog pattern"""

    ACTIVITY_TYPE_CHOICES = (
        ('TASK_CREATED', 'Task Created'),
        ('TASK_ASSIGNED', 'Task Assigned'),
        ('TASK_REASSIGNED', 'Task Reassigned'),
        ('TASK_STATUS_CHANGED', 'Task Status Changed'),
        ('TASK_DUE_DATE_CHANGED', 'Task Due Date Changed'),
        ('TASK_PRIORITY_CHANGED', 'Task Priority Changed'),
        ('TARGET_CREATED', 'Target Created'),
        ('TARGET_UPDATED', 'Target Updated'),
        ('TARGET_ACHIEVED', 'Target Achieved'),
        ('MILESTONE_ACHIEVED', 'Milestone Achieved'),
        ('PROGRAMME_STATUS_CHANGED', 'Programme Status Changed'),
        ('COMMENT_ADDED', 'Comment Added'),
    )

    task = models.ForeignKey(
        SalesTask, on_delete=models.CASCADE, null=True, blank=True,
        related_name='activity_logs'
    )
    sales_target = models.ForeignKey(
        SalesTarget, on_delete=models.CASCADE, null=True, blank=True,
        related_name='activity_logs'
    )
    user = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True
    )

    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Activity Log'
        verbose_name_plural = 'Task Activity Logs'
        indexes = [
            models.Index(fields=['task', 'created_at']),
            models.Index(fields=['sales_target', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_activity_type_display()} \u2014 {self.description[:50]}"
