from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta

from authentication.models import Department
from hr.models import (
    Employee, EmployeeDocument, Designation, WorkLocation, CostCenter,
    LeaveType, EmployeeLeaveBalance, LeaveApplication, Attendance,
    Shift, CompensatoryOff, SalaryComponent, SalaryStructure,
    SalaryStructureDetail, EmployeeSalary, Payroll, PayrollComponentDetail,
    Holiday,
    PFConfiguration, PFContribution, ESIConfiguration, ESIContribution,
    ProfessionalTaxSlab, PTContribution, TDSConfiguration,
    InvestmentDeclaration, TDSCalculation, GratuityConfiguration,
    GratuityCalculation, BonusConfiguration, BonusCalculation,
    ComplianceCalendarEntry
)
from hr.serializers import (
    DepartmentSerializer, DesignationSerializer, WorkLocationSerializer,
    CostCenterSerializer, ShiftSerializer, EmployeeListSerializer,
    EmployeeDetailSerializer, EmployeeDocumentSerializer, LeaveTypeSerializer,
    EmployeeLeaveBalanceSerializer, LeaveApplicationSerializer, AttendanceSerializer,
    CompensatoryOffSerializer, SalaryComponentSerializer, SalaryStructureSerializer,
    EmployeeSalarySerializer, PayrollSerializer, HolidaySerializer,
    PFConfigurationSerializer, PFContributionSerializer, ESIConfigurationSerializer,
    ESIContributionSerializer, ProfessionalTaxSlabSerializer, PTContributionSerializer,
    TDSConfigurationSerializer, InvestmentDeclarationSerializer, TDSCalculationSerializer,
    GratuityConfigurationSerializer, GratuityCalculationSerializer,
    BonusConfigurationSerializer, BonusCalculationSerializer,
    ComplianceCalendarEntrySerializer
)
from hr.permissions import (
    IsHRAdmin, IsHRStaff, IsManagerOrHR, IsEmployeeOrHR,
    CanApproveLeave, CanProcessPayroll, CanViewAttendance, CanEditEmployeeData
)


# ============================================================================
# MASTER DATA VIEWSETS
# ============================================================================

class DesignationViewSet(viewsets.ModelViewSet):
    """ViewSet for Designation master"""
    queryset = Designation.objects.filter(is_active=True)
    serializer_class = DesignationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['department', 'grade', 'is_active']
    search_fields = ['name', 'code']


class WorkLocationViewSet(viewsets.ModelViewSet):
    """ViewSet for Work Location master"""
    queryset = WorkLocation.objects.filter(is_active=True)
    serializer_class = WorkLocationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['state', 'city', 'is_active']
    search_fields = ['name', 'code', 'city']


class CostCenterViewSet(viewsets.ModelViewSet):
    """ViewSet for Cost Center master"""
    queryset = CostCenter.objects.filter(is_active=True)
    serializer_class = CostCenterSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['department', 'is_active']
    search_fields = ['name', 'code']


class ShiftViewSet(viewsets.ModelViewSet):
    """ViewSet for Shift master"""
    queryset = Shift.objects.filter(is_active=True)
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['shift_type', 'is_rotating', 'is_active']
    search_fields = ['name', 'code']


# ============================================================================
# EMPLOYEE MANAGEMENT VIEWSET
# ============================================================================

class EmployeeViewSet(viewsets.ModelViewSet):
    """ViewSet for Employee Master"""
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['department', 'designation', 'status', 'employment_type', 'work_location']
    search_fields = ['employee_id', 'first_name', 'last_name', 'personal_email', 'pan_number']

    def get_queryset(self):
        """Filter based on user role"""
        if self.request.user.role in ['Superadmin', 'Admin']:
            return Employee.objects.all().select_related(
                'department', 'designation', 'work_location', 'reporting_manager', 'user'
            )
        elif self.request.user.role == 'Manager':
            try:
                employee = self.request.user.employee
                # Manager sees their own team
                return Employee.objects.filter(
                    reporting_manager=employee
                ).select_related(
                    'department', 'designation', 'work_location', 'reporting_manager', 'user'
                )
            except:
                return Employee.objects.none()
        else:
            # Regular employees see only their own record
            try:
                return Employee.objects.filter(user=self.request.user)
            except:
                return Employee.objects.none()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmployeeDetailSerializer
        return EmployeeListSerializer

    @action(detail=False, methods=['get'])
    def by_department(self, request):
        """Get employees filtered by department"""
        department_id = request.query_params.get('department_id')
        if department_id:
            from django.core.exceptions import ValidationError
            try:
                employees = self.get_queryset().filter(department_id=department_id)
                serializer = self.get_serializer(employees, many=True)
                return Response(serializer.data)
            except (ValidationError, ValueError):
                return Response(
                    {'error': 'Invalid department_id format. Expected a valid UUID.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response({'error': 'department_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def by_location(self, request):
        """Get employees filtered by location"""
        location_id = request.query_params.get('location_id')
        if location_id:
            from django.core.exceptions import ValidationError
            try:
                employees = self.get_queryset().filter(work_location_id=location_id)
                serializer = self.get_serializer(employees, many=True)
                return Response(serializer.data)
            except (ValidationError, ValueError):
                return Response(
                    {'error': 'Invalid location_id format. Expected a valid UUID.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response({'error': 'location_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def active_count(self, request):
        """Get count of active employees"""
        count = self.get_queryset().filter(status='ACTIVE').count()
        return Response({'active_employees': count})

    @action(detail=False, methods=['get'])
    def by_grade(self, request):
        """Get employees by grade"""
        grade = request.query_params.get('grade')
        if grade:
            employees = self.get_queryset().filter(grade=grade)
            serializer = self.get_serializer(employees, many=True)
            return Response(serializer.data)
        return Response({'error': 'grade parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def confirm_probation(self, request, pk=None):
        """Confirm employee after probation"""
        employee = self.get_object()
        if employee.status != 'ONBOARDING':
            return Response(
                {'error': 'Only onboarding employees can be confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        employee.status = 'ACTIVE'
        employee.confirmation_date = timezone.now().date()
        employee.save()
        
        return Response(
            {'status': 'Employee confirmed', 'confirmation_date': employee.confirmation_date},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def initiate_separation(self, request, pk=None):
        """Initiate employee separation"""
        employee = self.get_object()
        reason = request.data.get('reason')
        separation_date = request.data.get('separation_date')

        if not reason or not separation_date:
            return Response(
                {'error': 'reason and separation_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        employee.status = 'NOTICE_PERIOD'
        employee.separation_reason = reason
        employee.separation_date = separation_date
        employee.save()

        return Response({'status': 'Separation initiated'}, status=status.HTTP_200_OK)


class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for Employee Documents"""
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated, IsEmployeeOrHR]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['employee', 'document_type', 'is_verified']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return EmployeeDocument.objects.all()
        else:
            try:
                employee = user.employee
                return EmployeeDocument.objects.filter(employee=employee)
            except:
                return EmployeeDocument.objects.none()

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify a document"""
        document = self.get_object()
        document.is_verified = True
        document.verified_by = request.user
        document.verified_date = timezone.now()
        document.save()

        return Response({'status': 'Document verified'}, status=status.HTTP_200_OK)


# ============================================================================
# ATTENDANCE & LEAVE VIEWSETS
# ============================================================================

class LeaveTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Leave Types (Read-only)"""
    queryset = LeaveType.objects.filter(is_active=True)
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]


class EmployeeLeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Employee Leave Balances"""
    serializer_class = EmployeeLeaveBalanceSerializer
    permission_classes = [IsAuthenticated, IsEmployeeOrHR]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['employee', 'leave_type', 'financial_year']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return EmployeeLeaveBalance.objects.select_related('employee', 'leave_type')
        else:
            try:
                employee = user.employee
                return EmployeeLeaveBalance.objects.filter(employee=employee).select_related(
                    'employee', 'leave_type'
                )
            except:
                return EmployeeLeaveBalance.objects.none()

    @action(detail=False, methods=['get'])
    def current_year(self, request):
        """Get leave balances for current financial year"""
        current_year = datetime.now().year
        financial_year = f"{current_year-1}-{current_year}"
        
        balances = self.get_queryset().filter(financial_year=financial_year)
        serializer = self.get_serializer(balances, many=True)
        return Response(serializer.data)


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    """ViewSet for Leave Applications"""
    serializer_class = LeaveApplicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['employee', 'leave_type', 'approval_status']
    search_fields = ['employee__first_name', 'employee__last_name']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return LeaveApplication.objects.all().select_related(
                'employee', 'leave_type', 'approval_manager'
            )
        elif user.role == 'Manager':
            try:
                employee = user.employee
                # Manager sees their team's leave applications
                return LeaveApplication.objects.filter(
                    employee__reporting_manager=employee
                ).select_related('employee', 'leave_type', 'approval_manager')
            except:
                return LeaveApplication.objects.none()
        else:
            # Employees see their own applications
            try:
                employee = user.employee
                return LeaveApplication.objects.filter(employee=employee).select_related(
                    'employee', 'leave_type', 'approval_manager'
                )
            except:
                return LeaveApplication.objects.none()

    def create(self, request, *args, **kwargs):
        """Create new leave application"""
        try:
            employee = request.user.employee
        except:
            return Response(
                {'error': 'User is not an employee'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()
        data['employee'] = employee.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveLeave])
    def approve(self, request, pk=None):
        """Approve leave application"""
        leave_application = self.get_object()
        if leave_application.approval_status != 'PENDING':
            return Response(
                {'error': 'Only pending leaves can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )

        leave_application.approval_status = 'APPROVED'
        leave_application.approval_manager = request.user
        leave_application.approval_date = timezone.now()
        leave_application.approval_comment = request.data.get('comment', '')
        leave_application.save()

        return Response({'status': 'Leave approved'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveLeave])
    def reject(self, request, pk=None):
        """Reject leave application"""
        leave_application = self.get_object()
        if leave_application.approval_status != 'PENDING':
            return Response(
                {'error': 'Only pending leaves can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )

        leave_application.approval_status = 'REJECTED'
        leave_application.approval_manager = request.user
        leave_application.approval_date = timezone.now()
        leave_application.approval_comment = request.data.get('comment', '')
        leave_application.save()

        return Response({'status': 'Leave rejected'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel leave application"""
        leave_application = self.get_object()
        
        # Employee can only cancel their own pending leaves
        if leave_application.employee.user != request.user and request.user.role not in ['Superadmin', 'Admin']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        if leave_application.is_cancelled:
            return Response(
                {'error': 'Leave already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )

        leave_application.is_cancelled = True
        leave_application.cancelled_by = request.user
        leave_application.cancelled_date = timezone.now()
        leave_application.cancellation_reason = request.data.get('reason', '')
        leave_application.save()

        return Response({'status': 'Leave cancelled'}, status=status.HTTP_200_OK)


class AttendanceViewSet(viewsets.ModelViewSet):
    """ViewSet for Attendance Records"""
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, CanViewAttendance]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['employee', 'date', 'status']
    search_fields = ['employee__first_name', 'employee__last_name']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return Attendance.objects.select_related('employee', 'regularized_by')
        elif user.role == 'Manager':
            try:
                employee = user.employee
                return Attendance.objects.filter(
                    employee__reporting_manager=employee
                ).select_related('employee', 'regularized_by')
            except:
                return Attendance.objects.none()
        else:
            try:
                employee = user.employee
                return Attendance.objects.filter(employee=employee).select_related(
                    'employee', 'regularized_by'
                )
            except:
                return Attendance.objects.none()

    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get attendance for today"""
        today = timezone.now().date()
        attendance = self.get_queryset().filter(date=today)
        serializer = self.get_serializer(attendance, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def monthly_report(self, request):
        """Get monthly attendance report"""
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        if not month or not year:
            return Response(
                {'error': 'month and year parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attendance = self.get_queryset().filter(date__month=month, date__year=year)
        
        report_data = {
            'month': month,
            'year': year,
            'total_days': attendance.values('employee').distinct().count(),
            'present_days': attendance.filter(status='PRESENT').count(),
            'absent_days': attendance.filter(status='ABSENT').count(),
            'wfh_days': attendance.filter(status='WFH').count(),
        }

        return Response(report_data)

    @action(detail=True, methods=['post'])
    def regularize(self, request, pk=None):
        """Regularize attendance"""
        attendance = self.get_object()
        if attendance.is_regularized:
            return Response(
                {'error': 'Attendance already regularized'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attendance.is_regularized = True
        attendance.regularized_by = request.user
        attendance.regularization_reason = request.data.get('reason', '')
        attendance.save()

        return Response({'status': 'Attendance regularized'}, status=status.HTTP_200_OK)


class CompensatoryOffViewSet(viewsets.ModelViewSet):
    """ViewSet for Compensatory Off"""
    serializer_class = CompensatoryOffSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'status']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return CompensatoryOff.objects.select_related('employee')
        else:
            try:
                employee = user.employee
                return CompensatoryOff.objects.filter(employee=employee)
            except:
                return CompensatoryOff.objects.none()


# ============================================================================
# PAYROLL VIEWSETS
# ============================================================================

class SalaryComponentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Salary Components (Read-only)"""
    queryset = SalaryComponent.objects.filter(is_active=True)
    serializer_class = SalaryComponentSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class SalaryStructureViewSet(viewsets.ModelViewSet):
    """ViewSet for Salary Structures"""
    queryset = SalaryStructure.objects.filter(is_active=True)
    serializer_class = SalaryStructureSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['grade', 'band', 'designation']
    search_fields = ['name', 'code']


class EmployeeSalaryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Employee Salary (Read-only for employees)"""
    serializer_class = EmployeeSalarySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'is_active']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return EmployeeSalary.objects.select_related('employee', 'salary_structure')
        elif user.role == 'Manager':
            try:
                employee = user.employee
                return EmployeeSalary.objects.filter(
                    employee__reporting_manager=employee
                ).select_related('employee', 'salary_structure')
            except:
                return EmployeeSalary.objects.none()
        else:
            try:
                employee = user.employee
                return EmployeeSalary.objects.filter(employee=employee).select_related(
                    'employee', 'salary_structure'
                )
            except:
                return EmployeeSalary.objects.none()


class PayrollViewSet(viewsets.ModelViewSet):
    """ViewSet for Payroll"""
    serializer_class = PayrollSerializer
    permission_classes = [IsAuthenticated, CanProcessPayroll]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['employee', 'month', 'year', 'status']
    search_fields = ['employee__employee_id', 'payroll_period']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return Payroll.objects.select_related(
                'employee', 'processed_by', 'approved_by'
            ).prefetch_related('components')
        else:
            return Payroll.objects.none()

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanProcessPayroll])
    def process_payroll(self, request):
        """Process payroll for a month"""
        month = request.data.get('month')
        year = request.data.get('year')

        if not month or not year:
            return Response(
                {'error': 'month and year are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payrolls = Payroll.objects.filter(month=month, year=year, status='DRAFT')
        payrolls.update(status='PROCESSED', processed_by=request.user, processed_date=timezone.now())

        return Response({
            'message': f'Payroll processed for {month}/{year}',
            'count': payrolls.count()
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanProcessPayroll])
    def approve(self, request, pk=None):
        """Approve payroll"""
        payroll = self.get_object()
        if payroll.status != 'PROCESSED':
            return Response(
                {'error': 'Only processed payroll can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payroll.status = 'APPROVED'
        payroll.approved_by = request.user
        payroll.approved_date = timezone.now()
        payroll.save()

        return Response({'status': 'Payroll approved'}, status=status.HTTP_200_OK)


class HolidayViewSet(viewsets.ModelViewSet):
    """ViewSet for Holidays"""
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_national', 'applicable_locations']
    search_fields = ['name']

    @action(detail=False, methods=['get'])
    def current_year(self, request):
        """Get holidays for current year"""
        current_year = timezone.now().year
        holidays = self.get_queryset().filter(holiday_date__year=current_year)
        serializer = self.get_serializer(holidays, many=True)
        return Response(serializer.data)


# ============================================================================
# STATUTORY COMPLIANCE VIEWSETS
# ============================================================================

class PFConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for PF Configuration"""
    queryset = PFConfiguration.objects.filter(is_active=True)
    serializer_class = PFConfigurationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]

class PFContributionViewSet(viewsets.ModelViewSet):
    """ViewSet for PF Contributions"""
    serializer_class = PFContributionSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'month', 'year']

    def get_queryset(self):
        return PFContribution.objects.select_related('employee')

class ESIConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for ESI Configuration"""
    queryset = ESIConfiguration.objects.filter(is_active=True)
    serializer_class = ESIConfigurationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]

class ESIContributionViewSet(viewsets.ModelViewSet):
    """ViewSet for ESI Contributions"""
    serializer_class = ESIContributionSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'month', 'year']

    def get_queryset(self):
        return ESIContribution.objects.select_related('employee')

class ProfessionalTaxSlabViewSet(viewsets.ModelViewSet):
    """ViewSet for Professional Tax Slabs"""
    queryset = ProfessionalTaxSlab.objects.filter(is_active=True)
    serializer_class = ProfessionalTaxSlabSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['state', 'frequency']
    search_fields = ['state']

class PTContributionViewSet(viewsets.ModelViewSet):
    """ViewSet for PT Deductions"""
    serializer_class = PTContributionSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'month', 'year', 'state']

    def get_queryset(self):
        return PTContribution.objects.select_related('employee')

class TDSConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for TDS Configuration"""
    queryset = TDSConfiguration.objects.filter(is_active=True)
    serializer_class = TDSConfigurationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]

class InvestmentDeclarationViewSet(viewsets.ModelViewSet):
    """ViewSet for Employee Investment Declarations (Form 12BB)"""
    serializer_class = InvestmentDeclarationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'financial_year', 'is_approved']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['Superadmin', 'Admin']:
            return InvestmentDeclaration.objects.select_related('employee')
        else:
            try:
                employee = user.employee
                return InvestmentDeclaration.objects.filter(employee=employee)
            except:
                return InvestmentDeclaration.objects.none()

class TDSCalculationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for TDS Calculations"""
    serializer_class = TDSCalculationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'financial_year', 'month', 'year']

    def get_queryset(self):
        return TDSCalculation.objects.select_related('employee')

class GratuityConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for Gratuity Configuration"""
    queryset = GratuityConfiguration.objects.filter(is_active=True)
    serializer_class = GratuityConfigurationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]

class GratuityCalculationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Gratuity Calculations"""
    serializer_class = GratuityCalculationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'is_eligible']

    def get_queryset(self):
        return GratuityCalculation.objects.select_related('employee')

class BonusConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for Bonus Configuration"""
    queryset = BonusConfiguration.objects.filter(is_active=True)
    serializer_class = BonusConfigurationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]

class BonusCalculationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Bonus Calculations"""
    serializer_class = BonusCalculationSerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'financial_year', 'is_paid']

    def get_queryset(self):
        return BonusCalculation.objects.select_related('employee')

class ComplianceCalendarEntryViewSet(viewsets.ModelViewSet):
    """ViewSet for Compliance Calendar"""
    serializer_class = ComplianceCalendarEntrySerializer
    permission_classes = [IsAuthenticated, IsHRStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['compliance_type', 'status', 'frequency', 'period_year']
    search_fields = ['title']

    def get_queryset(self):
        return ComplianceCalendarEntry.objects.all()

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming compliance events"""
        from datetime import date, timedelta
        days = int(request.query_params.get('days', 30))
        today = date.today()
        cutoff = today + timedelta(days=days)
        events = self.get_queryset().filter(due_date__gte=today, due_date__lte=cutoff, status='PENDING')
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue compliance events"""
        from datetime import date
        events = self.get_queryset().filter(due_date__lt=date.today(), status='PENDING')
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Mark a compliance event as completed"""
        event = self.get_object()
        event.status = 'COMPLETED'
        event.completed_date = timezone.now()
        event.completed_by = request.user
        event.reference_number = request.data.get('reference_number', '')
        event.save()
        return Response({'status': 'Compliance event marked as completed'}, status=status.HTTP_200_OK)
