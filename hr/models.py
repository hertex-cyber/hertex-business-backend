import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from core.models import Main
from authentication.models import User, Department
from hr.managers import EmployeeManager, AttendanceManager, LeaveManager


# ============================================================================
# CONSTANTS AND CHOICES
# ============================================================================

EMPLOYMENT_TYPE = (
    ('PERMANENT', 'Permanent'),
    ('CONTRACT', 'Contract'),
    ('TRAINEE', 'Trainee'),
    ('INTERN', 'Intern'),
    ('PART_TIME', 'Part-Time'),
)

EMPLOYEE_STATUS = (
    ('CANDIDATE', 'Candidate'),
    ('OFFERED', 'Offered'),
    ('ONBOARDING', 'Onboarding'),
    ('ACTIVE', 'Active'),
    ('ON_LEAVE', 'On Leave'),
    ('NOTICE_PERIOD', 'Notice Period'),
    ('SEPARATED', 'Separated'),
)

SEPARATION_REASON = (
    ('RESIGNED', 'Resigned'),
    ('TERMINATED', 'Terminated'),
    ('ABSCONDED', 'Absconded'),
    ('RETIRED', 'Retired'),
    ('DECEASED', 'Deceased'),
)

GENDER = (
    ('MALE', 'Male'),
    ('FEMALE', 'Female'),
    ('OTHER', 'Other'),
)

MARITAL_STATUS = (
    ('SINGLE', 'Single'),
    ('MARRIED', 'Married'),
    ('DIVORCED', 'Divorced'),
    ('WIDOWED', 'Widowed'),
)

BLOOD_GROUP = (
    ('A_POSITIVE', 'A+'),
    ('A_NEGATIVE', 'A-'),
    ('B_POSITIVE', 'B+'),
    ('B_NEGATIVE', 'B-'),
    ('AB_POSITIVE', 'AB+'),
    ('AB_NEGATIVE', 'AB-'),
    ('O_POSITIVE', 'O+'),
    ('O_NEGATIVE', 'O-'),
)

SHIFT_TYPE = (
    ('GENERAL', 'General (9 AM - 6 PM)'),
    ('ROTATIONAL', 'Rotational'),
    ('NIGHT', 'Night Shift'),
    ('FLEXIBLE', 'Flexible'),
    ('REMOTE', 'Remote'),
)

ATTENDANCE_STATUS = (
    ('PRESENT', 'Present'),
    ('ABSENT', 'Absent'),
    ('HALF_DAY', 'Half Day'),
    ('WFH', 'Work From Home'),
    ('ON_LEAVE', 'On Leave'),
)

LEAVE_STATUS = (
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
    ('CANCELLED', 'Cancelled'),
)

DOCUMENT_TYPE = (
    ('OFFER_LETTER', 'Offer Letter'),
    ('APPOINTMENT_LETTER', 'Appointment Letter'),
    ('10TH_CERTIFICATE', '10th Certificate'),
    ('12TH_CERTIFICATE', '12th Certificate'),
    ('UG_CERTIFICATE', 'UG Certificate'),
    ('PG_CERTIFICATE', 'PG Certificate'),
    ('PROFESSIONAL_CERT', 'Professional Certificate'),
    ('EXPERIENCE_CERT', 'Experience Certificate'),
    ('BGV_DOCUMENT', 'BGV Document'),
    ('AADHAAR', 'Aadhaar'),
    ('PAN', 'PAN'),
    ('PASSPORT', 'Passport'),
    ('VOTER_ID', 'Voter ID'),
    ('DRIVING_LICENSE', 'Driving License'),
    ('BANK_DETAILS', 'Bank Details'),
    ('OTHER', 'Other'),
)

LEAVE_TYPE = (
    ('CASUAL', 'Casual Leave'),
    ('SICK', 'Sick Leave'),
    ('EARNED', 'Earned Leave'),
    ('MATERNITY', 'Maternity Leave'),
    ('PATERNITY', 'Paternity Leave'),
    ('BEREAVEMENT', 'Bereavement Leave'),
    ('COMP_OFF', 'Compensatory Off'),
    ('OPTIONAL', 'Optional Holiday'),
    ('LWP', 'Leave Without Pay'),
    ('MARRIAGE', 'Marriage Leave'),
    ('STUDY', 'Study Leave'),
)

SALARY_COMPONENT_TYPE = (
    ('EARNINGS', 'Earnings'),
    ('DEDUCTIONS', 'Deductions'),
    ('FIXED', 'Fixed'),
    ('VARIABLE', 'Variable'),
)


# ============================================================================
# PHASE 1: CORE HR - EMPLOYEE MASTER
# ============================================================================

class Designation(Main):
    """Job Designation/Position Master"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.CharField(max_length=20, blank=True, null=True)  # E.g., E1, M1, S1
    band = models.CharField(max_length=20, blank=True, null=True)   # E.g., IC1, IC2
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Designation'
        verbose_name_plural = 'Designations'

    def __str__(self):
        return f"{self.name} ({self.code})"


class CostCenter(Main):
    """Cost Center for allocation of expenses"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    budget = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Cost Center'
        verbose_name_plural = 'Cost Centers'

    def __str__(self):
        return f"{self.name} ({self.code})"


class WorkLocation(Main):
    """Work Location/Branch Master"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='India')
    pin_code = models.CharField(max_length=10, blank=True)
    address = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Work Location'
        verbose_name_plural = 'Work Locations'

    def __str__(self):
        return f"{self.name} ({self.city})"


class Employee(Main):
    """Core Employee Master Model"""
    
    # System Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee_id = models.CharField(max_length=20, unique=True)  # EMP-YYYY-XXXX
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee')
    
    # ========== PERSONAL INFORMATION ==========
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS, null=True, blank=True)
    blood_group = models.CharField(max_length=20, choices=BLOOD_GROUP, null=True, blank=True)
    nationality = models.CharField(max_length=50, default='Indian')
    
    # Contact Details
    personal_email = models.EmailField(unique=True)
    personal_mobile = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Invalid phone number')]
    )
    
    # Current Address
    current_address = models.TextField()
    current_city = models.CharField(max_length=50)
    current_state = models.CharField(max_length=50)
    current_country = models.CharField(max_length=50, default='India')
    current_pin_code = models.CharField(max_length=10)
    
    # Permanent Address
    permanent_address = models.TextField()
    permanent_city = models.CharField(max_length=50)
    permanent_state = models.CharField(max_length=50)
    permanent_country = models.CharField(max_length=50, default='India')
    permanent_pin_code = models.CharField(max_length=10)
    
    # Emergency Contacts (storing as JSON would be better, implementing as separate model in Phase 1.5)
    emergency_contact_1_name = models.CharField(max_length=100, blank=True)
    emergency_contact_1_mobile = models.CharField(max_length=20, blank=True)
    emergency_contact_1_relation = models.CharField(max_length=50, blank=True)
    
    emergency_contact_2_name = models.CharField(max_length=100, blank=True)
    emergency_contact_2_mobile = models.CharField(max_length=20, blank=True)
    emergency_contact_2_relation = models.CharField(max_length=50, blank=True)
    
    # ========== IDENTITY DOCUMENTS ==========
    aadhaar_number = models.CharField(
        max_length=12,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\d{12}$', 'Aadhaar must be 12 digits')],
        help_text="12-digit Aadhaar number"
    )
    pan_number = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', 'Invalid PAN format')],
        help_text="PAN in format: ABCDE1234F"
    )
    passport_number = models.CharField(max_length=20, blank=True, null=True, unique=True)
    voter_id_number = models.CharField(max_length=20, blank=True, null=True)
    driving_license_number = models.CharField(max_length=20, blank=True, null=True)
    
    # ========== BANK DETAILS ==========
    bank_account_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_branch = models.CharField(max_length=100, blank=True, null=True)
    ifsc_code = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^[A-Z]{4}0[A-Z0-9]{6}$', 'Invalid IFSC code')]
    )
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    
    # ========== FAMILY DETAILS ==========
    spouse_name = models.CharField(max_length=100, blank=True, null=True)
    number_of_children = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    dependents = models.TextField(blank=True, null=True, help_text="JSON or comma-separated list")
    
    # ========== EMPLOYMENT INFORMATION ==========
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE)
    date_of_joining = models.DateField()
    probation_end_date = models.DateField(blank=True, null=True)
    confirmation_date = models.DateField(blank=True, null=True)
    notice_period_days = models.IntegerField(default=30)
    
    # Employment Status
    status = models.CharField(max_length=20, choices=EMPLOYEE_STATUS, default='ONBOARDING')
    
    # Separation Info (if separated)
    separation_date = models.DateField(blank=True, null=True)
    separation_reason = models.CharField(max_length=20, choices=SEPARATION_REASON, blank=True, null=True)
    separation_notes = models.TextField(blank=True, null=True)
    
    # ========== ORGANIZATION HIERARCHIES ==========
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='employees')
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, related_name='employees')
    work_location = models.ForeignKey(WorkLocation, on_delete=models.SET_NULL, null=True, related_name='employees')
    cost_center = models.ForeignKey(CostCenter, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    grade = models.CharField(max_length=20, blank=True, null=True)  # E.g., E1, M1
    band = models.CharField(max_length=20, blank=True, null=True)   # E.g., IC1, IC2
    
    # Reporting
    reporting_manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )
    dotted_reporting_manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dotted_subordinates'
    )
    
    # Additional Employment Fields
    company_entity = models.CharField(max_length=100, blank=True, null=True)
    work_shift = models.CharField(max_length=20, choices=SHIFT_TYPE, default='GENERAL')
    
    # Photo
    photo = models.ImageField(upload_to='employee_photos/%Y/%m/', blank=True, null=True)
    
    # Additional Info
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    
    # Managers
    objects = EmployeeManager()
    
    class Meta:
        ordering = ['first_name', 'last_name']
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['aadhaar_number']),
            models.Index(fields=['pan_number']),
            models.Index(fields=['status']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.employee_id})"
    
    def get_full_name(self):
        """Return employee's full name"""
        name = f"{self.first_name} {self.last_name}"
        if self.middle_name:
            name = f"{self.first_name} {self.middle_name} {self.last_name}"
        return name.strip()
    
    def get_age(self):
        """Calculate employee's age"""
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    def save(self, *args, **kwargs):
        # Generate employee_id if not exists
        if not self.employee_id:
            from datetime import datetime
            count = Employee.objects.filter(
                created_at__year=datetime.now().year
            ).count() + 1
            year = datetime.now().year
            self.employee_id = f"EMP-{year}-{count:04d}"
        
        super().save(*args, **kwargs)


class EmployeeDocument(Main):
    """Document management for employees"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE)
    document_file = models.FileField(upload_to='employee_documents/%Y/%m/')
    document_number = models.CharField(max_length=100, blank=True, null=True)
    issue_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verified_date = models.DateTimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Employee Document'
        verbose_name_plural = 'Employee Documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.employee_id} - {self.get_document_type_display()}"


# ============================================================================
# PHASE 1: ATTENDANCE & LEAVE MANAGEMENT
# ============================================================================

class LeaveType(Main):
    """Leave Type Master"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE)
    description = models.TextField(blank=True, null=True)
    
    # Leave Policy
    default_annual_allocation = models.IntegerField(default=0)  # No. of days per year
    accrual_frequency = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUAL', 'Annual'),
        ],
        default='ANNUAL'
    )
    max_carry_forward = models.IntegerField(default=0)  # Max days that can be carried forward
    can_go_negative = models.BooleanField(default=False)  # Allow negative balance
    min_balance_required = models.IntegerField(default=0)  # Min balance to apply leave
    max_continuous_days = models.IntegerField(default=999)  # Max continuous days allowed
    is_encashable = models.BooleanField(default=False)  # Can unused leave be paid?
    encashment_max_days = models.IntegerField(default=0)  # Max days that can be encashed
    
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Leave Type'
        verbose_name_plural = 'Leave Types'

    def __str__(self):
        return f"{self.name} ({self.code})"


class EmployeeLeaveBalance(Main):
    """Track leave balance for each employee per leave type"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    financial_year = models.CharField(max_length=9)  # E.g., "2025-2026"
    
    opening_balance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    accrued_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    used_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pending_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Pending approval
    encashed_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lapsed_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    current_balance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'leave_type', 'financial_year')
        verbose_name = 'Employee Leave Balance'
        verbose_name_plural = 'Employee Leave Balances'

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type.name} ({self.financial_year})"
    
    def calculate_balance(self):
        """Recalculate current balance"""
        self.current_balance = (
            self.opening_balance +
            self.accrued_days -
            self.used_days -
            self.encashed_days -
            self.lapsed_days +
            self.pending_days
        )
        return self.current_balance


class LeaveApplication(Main):
    """Leave Application/Request"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_applications')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.SET_NULL, null=True)
    
    # Dates
    date_from = models.DateField()
    date_to = models.DateField()
    number_of_days = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Application Info
    reason = models.TextField()
    remarks = models.TextField(blank=True, null=True)
    
    # Approval Workflow
    approval_status = models.CharField(max_length=20, choices=LEAVE_STATUS, default='PENDING')
    applied_date = models.DateTimeField(auto_now_add=True)
    
    # Manager Approval
    approval_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves'
    )
    approval_date = models.DateTimeField(blank=True, null=True)
    approval_comment = models.TextField(blank=True, null=True)
    
    # Cancellation
    is_cancelled = models.BooleanField(default=False)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_leaves'
    )
    cancelled_date = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    
    # Validation
    is_backdated = models.BooleanField(default=False)
    
    objects = LeaveManager()

    class Meta:
        verbose_name = 'Leave Application'
        verbose_name_plural = 'Leave Applications'
        ordering = ['-applied_date']

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type.name} ({self.date_from} to {self.date_to})"


class Attendance(Main):
    """Daily attendance record"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    
    # Check-in / Check-out
    check_in_time = models.TimeField(blank=True, null=True)
    check_out_time = models.TimeField(blank=True, null=True)
    
    # Location (GPS)
    check_in_location = models.CharField(max_length=255, blank=True, null=True)
    check_out_location = models.CharField(max_length=255, blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='ABSENT')
    
    # Duration
    working_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Flags
    is_late = models.BooleanField(default=False)
    late_by_minutes = models.IntegerField(default=0)
    is_early_checkout = models.BooleanField(default=False)
    early_by_minutes = models.IntegerField(default=0)
    
    # Regularization
    is_regularized = models.BooleanField(default=False)
    regularized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    regularization_reason = models.TextField(blank=True, null=True)
    
    # Shift Info
    shift = models.CharField(max_length=20, choices=SHIFT_TYPE, default='GENERAL')
    
    # Notes
    remarks = models.TextField(blank=True, null=True)
    
    objects = AttendanceManager()

    class Meta:
        unique_together = ('employee', 'date')
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance Records'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} ({self.status})"
    
    def calculate_working_hours(self):
        """Calculate working hours from check-in/out times"""
        if self.check_in_time and self.check_out_time:
            from datetime import datetime
            check_in = datetime.combine(self.date, self.check_in_time)
            check_out = datetime.combine(self.date, self.check_out_time)
            duration = check_out - check_in
            self.working_hours = duration.total_seconds() / 3600
            return self.working_hours
        return 0


class Shift(Main):
    """Shift Master and Configuration"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPE)
    description = models.TextField(blank=True, null=True)
    
    # Timing
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_duration_minutes = models.IntegerField(default=60)
    
    # Frequency
    is_rotating = models.BooleanField(default=False)
    rotation_pattern = models.TextField(blank=True, null=True, help_text="Days or weeks for rotation")
    
    # Allowances
    night_shift_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Shift'
        verbose_name_plural = 'Shifts'

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"


class CompensatoryOff(Main):
    """Compensatory Off (Comp-Off) Management"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='comp_offs')
    earned_on_date = models.DateField()  # Date employee worked extra
    earned_hours = models.DecimalField(max_digits=5, decimal_places=2)
    
    availed_on_date = models.DateField(blank=True, null=True)  # Date comp-off was taken
    status = models.CharField(
        max_length=20,
        choices=[
            ('EARNED', 'Earned'),
            ('AVAILED', 'Availed'),
            ('LAPSED', 'Lapsed'),
        ],
        default='EARNED'
    )
    
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Compensatory Off'
        verbose_name_plural = 'Compensatory Offs'

    def __str__(self):
        return f"{self.employee.employee_id} - Comp-Off ({self.earned_on_date})"


# ============================================================================
# PHASE 1: BASIC PAYROLL STRUCTURE
# ============================================================================

class SalaryComponent(Main):
    """Salary Components Master (Earnings, Deductions)"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    component_type = models.CharField(max_length=20, choices=SALARY_COMPONENT_TYPE)
    
    # Classification
    is_fixed = models.BooleanField(default=True)
    depends_on_basic = models.BooleanField(default=False)  # If True, calculated as % of basic
    percentage_of_basic = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Tax & Statutory
    is_taxable = models.BooleanField(default=False)
    is_statutory = models.BooleanField(default=False)
    exemption_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # GL Account (for accounting integration)
    gl_account = models.CharField(max_length=100, blank=True, null=True)
    
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)  # Display order

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Salary Component'
        verbose_name_plural = 'Salary Components'

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.get_component_type_display()}"


class SalaryStructure(Main):
    """Salary Structure Template"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    
    # Applicable to
    grade = models.CharField(max_length=20, blank=True, null=True)
    band = models.CharField(max_length=20, blank=True, null=True)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Effective Dates
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Salary Structure'
        verbose_name_plural = 'Salary Structures'
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"


class SalaryStructureDetail(Main):
    """Components in a Salary Structure"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    salary_structure = models.ForeignKey(SalaryStructure, on_delete=models.CASCADE, related_name='components')
    component = models.ForeignKey(SalaryComponent, on_delete=models.CASCADE)
    
    # Amount
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    is_percentage = models.BooleanField(default=False)  # If True, amount is %
    
    order = models.IntegerField(default=0)

    class Meta:
        unique_together = ('salary_structure', 'component')
        ordering = ['order']
        verbose_name = 'Salary Structure Detail'
        verbose_name_plural = 'Salary Structure Details'

    def __str__(self):
        return f"{self.salary_structure.code} - {self.component.name}"


class EmployeeSalary(Main):
    """Employee Salary Details"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salary_details')
    salary_structure = models.ForeignKey(SalaryStructure, on_delete=models.SET_NULL, null=True)
    
    # CTC Details
    ctc = models.DecimalField(max_digits=15, decimal_places=2)  # Cost to Company
    gross_salary = models.DecimalField(max_digits=15, decimal_places=2)
    net_salary = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Basic Components
    basic_salary = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Effective Dates
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    # Previous Salary (for increment tracking)
    previous_salary = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_salary'
    )

    class Meta:
        verbose_name = 'Employee Salary'
        verbose_name_plural = 'Employee Salaries'
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.employee.employee_id} - {self.effective_from}"


class Payroll(Main):
    """Monthly Payroll Record"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_records')
    
    # Period
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.IntegerField()
    payroll_period = models.CharField(max_length=20)  # E.g., "2025-01"
    
    # Attendance
    working_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    present_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    absent_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    half_day_count = models.IntegerField(default=0)
    
    # Leave
    leave_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Salary Calculation
    gross_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Additional
    arrears = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    final_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PROCESSED', 'Processed'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Bank Details
    bank_transfer_date = models.DateField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Audit
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    processed_date = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payrolls'
    )
    approved_date = models.DateTimeField(blank=True, null=True)
    
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        verbose_name = 'Payroll'
        verbose_name_plural = 'Payrolls'
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.employee.employee_id} - {self.payroll_period}"


class PayrollComponentDetail(Main):
    """Component-wise breakdown for a payroll"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='components')
    component = models.ForeignKey(SalaryComponent, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        unique_together = ('payroll', 'component')
        verbose_name = 'Payroll Component Detail'
        verbose_name_plural = 'Payroll Component Details'

    def __str__(self):
        return f"{self.payroll.payroll_period} - {self.component.name}: {self.amount}"


# Special Models for Enhanced Functionality

class Holiday(Main):
    """Holiday Calendar Master"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    holiday_date = models.DateField()
    is_national = models.BooleanField(default=True)
    applicable_locations = models.ManyToManyField(WorkLocation, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Holiday'
        verbose_name_plural = 'Holidays'
        ordering = ['holiday_date']

    def __str__(self):
        return f"{self.name} ({self.holiday_date})"


# ==========================================
# RECRUITMENT & ONBOARDING MODELS
# ==========================================

class JobRequisition(Main):
    """Job Requisition Form (JRF)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    designation = models.ForeignKey(Designation, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='requisitions_raised')
    vacancies = models.PositiveIntegerField()
    priority = models.CharField(max_length=20, choices=[('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical')])
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Closed', 'Closed')], default='Pending')
    justification = models.TextField()
    budget_allocated = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Job Requisition'
        verbose_name_plural = 'Job Requisitions'
        ordering = ['-created_at']

class Candidate(Main):
    """Candidate Database for ATS"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    resume = models.FileField(upload_to='resumes/%Y/%m/', null=True, blank=True)
    source = models.CharField(max_length=50, null=True, blank=True)
    skills = models.JSONField(default=list, blank=True)
    experience_years = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    class Meta:
        verbose_name = 'Candidate'
        verbose_name_plural = 'Candidates'

class JobApplication(Main):
    """ATS Pipeline for a Candidate"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='applications')
    requisition = models.ForeignKey(JobRequisition, on_delete=models.CASCADE, related_name='applications')
    stage = models.CharField(max_length=50, choices=[
        ('Applied', 'Applied'), ('Screening', 'Screening'), ('L1_Interview', 'L1 Interview'),
        ('L2_Interview', 'L2 Interview'), ('HR_Round', 'HR Round'), ('Offered', 'Offered'),
        ('Accepted', 'Accepted'), ('Rejected', 'Rejected')
    ], default='Applied')
    applied_on = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Job Application'
        verbose_name_plural = 'Job Applications'

# ==========================================
# PERFORMANCE MANAGEMENT SYSTEM (PMS)
# ==========================================

class AppraisalCycle(Main):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)  # e.g. FY 2025-26 Annual Appraisal
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=[('Active', 'Active'), ('Closed', 'Closed')])
    
    class Meta:
        verbose_name = 'Appraisal Cycle'
        verbose_name_plural = 'Appraisal Cycles'

class PerformanceGoal(Main):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='goals')
    cycle = models.ForeignKey(AppraisalCycle, on_delete=models.CASCADE)
    description = models.TextField()
    weightage = models.DecimalField(max_digits=5, decimal_places=2)  # percentage
    status = models.CharField(max_length=20, default='Pending')

class PerformanceReview(Main):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='reviews')
    cycle = models.ForeignKey(AppraisalCycle, on_delete=models.CASCADE)
    self_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    manager_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    final_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    manager_comments = models.TextField(null=True, blank=True)

# ==========================================
# TRAINING & DEVELOPMENT (L&D)
# ==========================================

class TrainingProgram(Main):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    training_type = models.CharField(max_length=50, choices=[('Internal', 'Internal'), ('External', 'External'), ('Online', 'Online')])
    start_date = models.DateField()
    end_date = models.DateField()
    trainer_name = models.CharField(max_length=100, null=True, blank=True)

class TrainingNomination(Main):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[('Nominated', 'Nominated'), ('Approved', 'Approved'), ('Completed', 'Completed'), ('Failed', 'Failed')])
    completion_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

# ==========================================
# EXIT MANAGEMENT
# ==========================================

class Resignation(Main):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='resignations')
    submitted_on = models.DateField(auto_now_add=True)
    reason = models.TextField()
    requested_last_working_day = models.DateField()
    approved_last_working_day = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Withdrawn', 'Withdrawn')])

class ExitClearance(Main):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resignation = models.ForeignKey(Resignation, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    is_cleared = models.BooleanField(default=False)
    comments = models.TextField(null=True, blank=True)


# ============================================================================
# PHASE 3: STATUTORY COMPLIANCE
# ============================================================================

# -------- PROVIDENT FUND (PF) --------

class PFConfiguration(Main):
    """PF Configuration Master"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee_contribution_pct = models.DecimalField(max_digits=5, decimal_places=2, default=12.00,
        help_text="Employee PF contribution % of Basic+DA")
    employer_epf_pct = models.DecimalField(max_digits=5, decimal_places=2, default=3.67,
        help_text="Employer EPF contribution % of Basic+DA")
    employer_eps_pct = models.DecimalField(max_digits=5, decimal_places=2, default=8.33,
        help_text="Employer EPS contribution % of Basic+DA")
    employer_edli_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.50,
        help_text="EDLI contribution % of Basic+DA")
    employer_admin_charges_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.50)
    edli_admin_charges_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.01)

    wage_ceiling = models.DecimalField(max_digits=15, decimal_places=2, default=15000.00,
        help_text="Statutory wage ceiling for PF eligibility")
    eps_max_pensionable_salary = models.DecimalField(max_digits=15, decimal_places=2, default=15000.00,
        help_text="Max salary considered for EPS pension calculation")

    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'PF Configuration'
        verbose_name_plural = 'PF Configurations'

    def __str__(self):
        return f"PF Config effective {self.effective_from}"


class PFContribution(Main):
    """Monthly PF Contribution Record per Employee"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='pf_contributions')
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='pf_contributions', null=True, blank=True)

    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.IntegerField()

    # Wages
    basic_da = models.DecimalField(max_digits=15, decimal_places=2, help_text="Basic + DA for the month")
    gross_salary = models.DecimalField(max_digits=15, decimal_places=2)

    # Contributions
    employee_pf = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employer_epf = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employer_eps = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employer_edli = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employer_admin_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    edli_admin_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    total_employee_contribution = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_employer_contribution = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # UAN & KYC
    uan = models.CharField(max_length=12, blank=True, null=True)
    is_ecr_generated = models.BooleanField(default=False)
    ecr_file = models.FileField(upload_to='pf_ecr/%Y/%m/', blank=True, null=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        verbose_name = 'PF Contribution'
        verbose_name_plural = 'PF Contributions'
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.employee.employee_id} PF - {self.month}/{self.year}"


# -------- EMPLOYEE STATE INSURANCE (ESI) --------

class ESIConfiguration(Main):
    """ESI Configuration Master"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee_contribution_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.75,
        help_text="Employee ESI contribution % of gross salary")
    employer_contribution_pct = models.DecimalField(max_digits=5, decimal_places=2, default=3.25,
        help_text="Employer ESI contribution % of gross salary")
    wage_ceiling = models.DecimalField(max_digits=15, decimal_places=2, default=21000.00,
        help_text="Gross salary ceiling for ESI eligibility")

    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'ESI Configuration'
        verbose_name_plural = 'ESI Configurations'

    def __str__(self):
        return f"ESI Config effective {self.effective_from}"


class ESIContribution(Main):
    """Monthly ESI Contribution Record per Employee"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='esi_contributions')
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='esi_contributions', null=True, blank=True)

    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.IntegerField()

    gross_salary = models.DecimalField(max_digits=15, decimal_places=2)
    employee_contribution = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employer_contribution = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_contribution = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    ip_number = models.CharField(max_length=20, blank=True, null=True, help_text="Insured Person Number")
    is_challan_generated = models.BooleanField(default=False)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        verbose_name = 'ESI Contribution'
        verbose_name_plural = 'ESI Contributions'

    def __str__(self):
        return f"{self.employee.employee_id} ESI - {self.month}/{self.year}"


# -------- PROFESSIONAL TAX (PT) --------

class ProfessionalTaxSlab(Main):
    """Professional Tax Slab Configuration per State"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=100)

    # Slab
    salary_from = models.DecimalField(max_digits=15, decimal_places=2)
    salary_to = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)

    frequency = models.CharField(max_length=20, choices=[
        ('MONTHLY', 'Monthly'),
        ('HALF_YEARLY', 'Half-Yearly'),
        ('ANNUAL', 'Annual'),
    ], default='MONTHLY')

    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Professional Tax Slab'
        verbose_name_plural = 'Professional Tax Slabs'
        ordering = ['state', 'salary_from']

    def __str__(self):
        return f"PT - {self.state} ({self.salary_from} to {self.salary_to or '∞'})"


class PTContribution(Main):
    """Professional Tax Deduction Record per Employee"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='pt_contributions')
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='pt_contributions', null=True, blank=True)

    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.IntegerField()

    gross_salary = models.DecimalField(max_digits=15, decimal_places=2)
    pt_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    state = models.CharField(max_length=100)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        verbose_name = 'PT Deduction'
        verbose_name_plural = 'PT Deductions'

    def __str__(self):
        return f"{self.employee.employee_id} PT - {self.month}/{self.year}"


# -------- TAX DEDUCTED AT SOURCE (TDS) --------

class TDSConfiguration(Main):
    """TDS Configuration Master"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    financial_year = models.CharField(max_length=9, unique=True)

    enable_old_regime = models.BooleanField(default=True)
    enable_new_regime = models.BooleanField(default=True)

    old_regime_slabs = models.JSONField(default=dict, blank=True)
    new_regime_slabs = models.JSONField(default=dict, blank=True)

    standard_deduction_old = models.DecimalField(max_digits=15, decimal_places=2, default=50000.00)
    standard_deduction_new = models.DecimalField(max_digits=15, decimal_places=2, default=75000.00)

    education_cess_pct = models.DecimalField(max_digits=5, decimal_places=2, default=4.00)

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'TDS Configuration'
        verbose_name_plural = 'TDS Configurations'

    def __str__(self):
        return f"TDS Config FY {self.financial_year}"


class InvestmentDeclaration(Main):
    """Employee Investment Declaration (Form 12BB)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='investment_declarations')
    financial_year = models.CharField(max_length=9)

    tax_regime = models.CharField(max_length=20, choices=[('OLD', 'Old Regime'), ('NEW', 'New Regime')], default='NEW')

    section_80c_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    section_80d_self_family = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    section_80d_parents = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    section_80g_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    hra_rent_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    lta_claimed = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    home_loan_interest = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    nps_employee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    is_submitted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    submitted_date = models.DateTimeField(blank=True, null=True)
    approved_date = models.DateTimeField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    proof_document = models.FileField(upload_to='investment_proofs/%Y/%m/', blank=True, null=True)

    class Meta:
        unique_together = ('employee', 'financial_year')
        verbose_name = 'Investment Declaration'
        verbose_name_plural = 'Investment Declarations'

    def __str__(self):
        return f"{self.employee.employee_id} - {self.financial_year}"


class TDSCalculation(Main):
    """Monthly TDS Calculation per Employee"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='tds_calculations')
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='tds_calculations', null=True, blank=True)
    financial_year = models.CharField(max_length=9)

    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.IntegerField()

    tax_regime = models.CharField(max_length=20, choices=[('OLD', 'Old Regime'), ('NEW', 'New Regime')], default='NEW')

    ytd_gross_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_exemptions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_standard_deduction = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_deductions_80c = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_other_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_taxable_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_cess = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_total_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ytd_tds_deducted = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    current_month_tds = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        unique_together = ('employee', 'financial_year', 'month')
        verbose_name = 'TDS Calculation'
        verbose_name_plural = 'TDS Calculations'

    def __str__(self):
        return f"{self.employee.employee_id} TDS - {self.month}/{self.year}"


# -------- GRATUITY --------

class GratuityConfiguration(Main):
    """Gratuity Calculation Rules"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    formula_numerator = models.IntegerField(default=15,
        help_text="Number of days salary per year of service (15 as per Act)")
    formula_denominator = models.IntegerField(default=26,
        help_text="Days in a month (26 as per standard)")
    min_service_years = models.IntegerField(default=5,
        help_text="Minimum years of service for gratuity eligibility")

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Gratuity Configuration'
        verbose_name_plural = 'Gratuity Configurations'

    def __str__(self):
        return f"Gratuity Config ({self.formula_numerator}/{self.formula_denominator})"


class GratuityCalculation(Main):
    """Gratuity Calculation per Employee"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='gratuity_calculations')

    date_of_joining = models.DateField()
    date_of_exit = models.DateField()
    years_of_service = models.DecimalField(max_digits=5, decimal_places=2)
    is_eligible = models.BooleanField(default=False)

    last_drawn_basic_da = models.DecimalField(max_digits=15, decimal_places=2)
    gratuity_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    monthly_provision_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0,
        help_text="Monthly provision set aside")

    calculated_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Gratuity Calculation'
        verbose_name_plural = 'Gratuity Calculations'

    def __str__(self):
        return f"{self.employee.employee_id} - Gratuity: {self.gratuity_amount}"


# -------- BONUS --------

class BonusConfiguration(Main):
    """Bonus Calculation Rules"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    financial_year = models.CharField(max_length=9)

    wage_ceiling = models.DecimalField(max_digits=15, decimal_places=2, default=21000.00,
        help_text="Salary ceiling for bonus eligibility (Payment of Bonus Act)")
    minimum_bonus_pct = models.DecimalField(max_digits=5, decimal_places=2, default=8.33)
    maximum_bonus_pct = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)

    allocable_surplus = models.DecimalField(max_digits=15, decimal_places=2, default=0,
        help_text="Allocable surplus for the year")

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Bonus Configuration'
        verbose_name_plural = 'Bonus Configurations'

    def __str__(self):
        return f"Bonus Config FY {self.financial_year}"


class BonusCalculation(Main):
    """Bonus Calculation per Employee"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='bonus_calculations')

    financial_year = models.CharField(max_length=9)

    eligible_salary = models.DecimalField(max_digits=15, decimal_places=2,
        help_text="Salary considered for bonus calculation")
    bonus_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    payout_date = models.DateField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)

    class Meta:
        unique_together = ('employee', 'financial_year')
        verbose_name = 'Bonus Calculation'
        verbose_name_plural = 'Bonus Calculations'

    def __str__(self):
        return f"{self.employee.employee_id} Bonus - {self.financial_year}"


# -------- COMPLIANCE CALENDAR --------

class ComplianceCalendarEntry(Main):
    """Compliance Calendar for statutory dues and filings"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    compliance_type = models.CharField(max_length=50, choices=[
        ('PF', 'Provident Fund'),
        ('ESI', 'Employee State Insurance'),
        ('PT', 'Professional Tax'),
        ('TDS', 'TDS'),
        ('LWF', 'Labour Welfare Fund'),
        ('GRATUITY', 'Gratuity'),
        ('BONUS', 'Bonus'),
    ])

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    due_date = models.DateField()
    frequency = models.CharField(max_length=20, choices=[
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('HALF_YEARLY', 'Half-Yearly'),
        ('ANNUAL', 'Annual'),
    ])

    period_month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)], blank=True, null=True)
    period_year = models.IntegerField()
    period_quarter = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)], blank=True, null=True)
    period_half = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(2)], blank=True, null=True)

    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
        ('WAIVED', 'Waived'),
    ], default='PENDING')

    completed_date = models.DateTimeField(blank=True, null=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True, help_text="Challan/Return reference")

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Compliance Calendar'
        verbose_name_plural = 'Compliance Calendar Entries'
        ordering = ['due_date']

    def __str__(self):
        return f"{self.get_compliance_type_display()} - {self.title} (Due: {self.due_date})"
