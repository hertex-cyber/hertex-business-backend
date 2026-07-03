from django.urls import path, include
from rest_framework.routers import DefaultRouter
from hr.views import (
    DesignationViewSet, WorkLocationViewSet, CostCenterViewSet,
    ShiftViewSet, EmployeeViewSet, EmployeeDocumentViewSet,
    LeaveTypeViewSet, EmployeeLeaveBalanceViewSet, LeaveApplicationViewSet,
    AttendanceViewSet, CompensatoryOffViewSet, SalaryComponentViewSet,
    SalaryStructureViewSet, EmployeeSalaryViewSet, PayrollViewSet,
    HolidayViewSet,
    PFConfigurationViewSet, PFContributionViewSet, ESIConfigurationViewSet,
    ESIContributionViewSet, ProfessionalTaxSlabViewSet, PTContributionViewSet,
    TDSConfigurationViewSet, InvestmentDeclarationViewSet, TDSCalculationViewSet,
    GratuityConfigurationViewSet, GratuityCalculationViewSet,
    BonusConfigurationViewSet, BonusCalculationViewSet,
    ComplianceCalendarEntryViewSet
)
from hr.views_extended import (
    JobRequisitionViewSet, CandidateViewSet, JobApplicationViewSet,
    AppraisalCycleViewSet, PerformanceGoalViewSet, PerformanceReviewViewSet,
    TrainingProgramViewSet, TrainingNominationViewSet,
    ResignationViewSet, ExitClearanceViewSet
)

router = DefaultRouter()

# Master Data Routers
router.register(r'designations', DesignationViewSet, basename='designation')
router.register(r'work-locations', WorkLocationViewSet, basename='work-location')
router.register(r'cost-centers', CostCenterViewSet, basename='cost-center')
router.register(r'shifts', ShiftViewSet, basename='shift')

# Employee Management
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'employee-documents', EmployeeDocumentViewSet, basename='employee-document')

# Attendance & Leave
router.register(r'leave-types', LeaveTypeViewSet, basename='leave-type')
router.register(r'leave-balances', EmployeeLeaveBalanceViewSet, basename='leave-balance')
router.register(r'leave-applications', LeaveApplicationViewSet, basename='leave-application')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'comp-offs', CompensatoryOffViewSet, basename='comp-off')

# Payroll
router.register(r'salary-components', SalaryComponentViewSet, basename='salary-component')
router.register(r'salary-structures', SalaryStructureViewSet, basename='salary-structure')
router.register(r'employee-salary', EmployeeSalaryViewSet, basename='employee-salary')
router.register(r'payroll', PayrollViewSet, basename='payroll')

# Others
router.register(r'holidays', HolidayViewSet, basename='holiday')

# Statutory Compliance
router.register(r'pf-configurations', PFConfigurationViewSet, basename='pf-configuration')
router.register(r'pf-contributions', PFContributionViewSet, basename='pf-contribution')
router.register(r'esi-configurations', ESIConfigurationViewSet, basename='esi-configuration')
router.register(r'esi-contributions', ESIContributionViewSet, basename='esi-contribution')
router.register(r'professional-tax-slabs', ProfessionalTaxSlabViewSet, basename='professional-tax-slab')
router.register(r'pt-deductions', PTContributionViewSet, basename='pt-deduction')
router.register(r'tds-configurations', TDSConfigurationViewSet, basename='tds-configuration')
router.register(r'investment-declarations', InvestmentDeclarationViewSet, basename='investment-declaration')
router.register(r'tds-calculations', TDSCalculationViewSet, basename='tds-calculation')
router.register(r'gratuity-configurations', GratuityConfigurationViewSet, basename='gratuity-configuration')
router.register(r'gratuity-calculations', GratuityCalculationViewSet, basename='gratuity-calculation')
router.register(r'bonus-configurations', BonusConfigurationViewSet, basename='bonus-configuration')
router.register(r'bonus-calculations', BonusCalculationViewSet, basename='bonus-calculation')
router.register(r'compliance-calendar', ComplianceCalendarEntryViewSet, basename='compliance-calendar')

# Recruitment
router.register(r'job-requisitions', JobRequisitionViewSet, basename='job-requisition')
router.register(r'candidates', CandidateViewSet, basename='candidate')
router.register(r'job-applications', JobApplicationViewSet, basename='job-application')

# Performance (PMS)
router.register(r'appraisal-cycles', AppraisalCycleViewSet, basename='appraisal-cycle')
router.register(r'performance-goals', PerformanceGoalViewSet, basename='performance-goal')
router.register(r'performance-reviews', PerformanceReviewViewSet, basename='performance-review')

# Training (L&D)
router.register(r'training-programs', TrainingProgramViewSet, basename='training-program')
router.register(r'training-nominations', TrainingNominationViewSet, basename='training-nomination')

# Exit Management
router.register(r'resignations', ResignationViewSet, basename='resignation')
router.register(r'exit-clearances', ExitClearanceViewSet, basename='exit-clearance')


app_name = 'hr'

urlpatterns = [
    path('', include(router.urls)),
]
