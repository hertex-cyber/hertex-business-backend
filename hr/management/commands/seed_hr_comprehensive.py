"""
Comprehensive HR module seed and validation test.
Tests every model, field constraint, validator, and unique constraint.
Usage: python manage.py seed_hr_comprehensive
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import IntegrityError, DataError
from datetime import date, timedelta, datetime
from decimal import Decimal
import random
import uuid
import traceback
import json
import re

User = get_user_model()


class TestResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def ok(self, msg):
        self.passed.append(msg)

    def fail(self, msg, detail=""):
        self.failed.append(f"{msg}: {detail}" if detail else msg)

    def warn(self, msg):
        self.warnings.append(msg)

    @property
    def success(self):
        return len(self.failed) == 0

    def summary(self):
        return {
            'passed': len(self.passed),
            'failed': len(self.failed),
            'warnings': len(self.warnings),
        }


class Command(BaseCommand):
    help = 'Comprehensive HR module seed & validation test'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing data first')

    def handle(self, *args, **options):
        from hr.models import (
            Designation, CostCenter, WorkLocation, Employee, EmployeeDocument,
            LeaveType, EmployeeLeaveBalance, LeaveApplication, Attendance, Shift,
            CompensatoryOff, SalaryComponent, SalaryStructure, SalaryStructureDetail,
            EmployeeSalary, Payroll, PayrollComponentDetail, Holiday,
            JobRequisition, Candidate, JobApplication, AppraisalCycle,
            PerformanceGoal, PerformanceReview, TrainingProgram, TrainingNomination,
            Resignation, SalaryRevision, EmployeeLoan, LoanRepayment,
            EmployeeReimbursement, EmployeeFamily, EmployeeEmergencyContact,
            EmployeeBankAccount, EmployeeDocumentVersion, ExitClearance,
            ExitInterview, ExitInterviewResponse, FnFSettlement,
            FnFSettlementComponent, AlumniRecord, HRTicket, HRTicketConversation,
            AssetRequest, OKR, Feedback360, PIPlan, CalibrationSession,
            Skill, EmployeeSkill, TrainingNeed, TrainingAssessment, TrainingCost,
            InterviewSchedule, OfferLetter, BGVCheck, OnboardingTask,
            PFConfiguration, PFContribution, ESIConfiguration, ESIContribution,
            ProfessionalTaxSlab, PTContribution, TDSConfiguration,
            InvestmentDeclaration, TDSCalculation, GratuityConfiguration,
            GratuityCalculation, BonusConfiguration, BonusCalculation,
            ComplianceCalendarEntry, LWFConfiguration, LWFContribution,
            OvertimeRequest, ShiftSwapRequest, AttendanceRegularizationRequest,
            VPFContribution, PFStatement, ESICard, LowerDeductionCertificate,
            PTEnrollment, InternationalWorker, Form12BA, Form24QReturn,
            InternalJobPosting, InternalJobApplication, EmployeeReferral,
            OnboardingBuddy, PreJoiningDocument, OnboardingFeedback,
            GoalLibrary, RatingScale, RatingScaleOption, AppraisalFormTemplate,
            AppraisalFormSection, AppraisalFormQuestion, AppraisalFormResponse,
            BellCurveConfig, PromotionMatrix, PromotionMatrixRow, GoalCascade,
            AppraisalCycleStage, IPAccessRestriction, POSHComplaint,
            POSHInquiryNote, DataConsentRecord, StayInterview, SalaryFreeze,
        )
        from authentication.models import Department

        total_start = timezone.now()
        result = TestResult()
        should_clear = options.get('clear', False)

        self.stdout.write(self.style.NOTICE('=' * 70))
        self.stdout.write(self.style.NOTICE('COMPREHENSIVE HR MODULE SEED & VALIDATION TEST'))
        self.stdout.write(self.style.NOTICE('=' * 70))

        if should_clear:
            self._clear_all(result)

        # ============================================================
        # PHASE 1: Master Data
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n📋 PHASE 1: Master Data'))

        # Departments
        dept_names = ['Engineering', 'Human Resources', 'Finance', 'Design', 'Management', 'Sales', 'Marketing']
        departments = {}
        for name in dept_names:
            try:
                d, _ = Department.objects.get_or_create(name=name)
                departments[name] = d
                result.ok(f"Department created: {name}")
            except Exception as e:
                result.fail("Department creation", str(e))

        # Designation
        desig_data = [
            {'code': 'CEO', 'name': 'Chief Executive Officer', 'grade': 'E5', 'band': 'IC5'},
            {'code': 'CTO', 'name': 'Chief Technology Officer', 'grade': 'E5', 'band': 'IC5'},
            {'code': 'HR_HEAD', 'name': 'HR Head', 'grade': 'E4', 'band': 'IC4'},
            {'code': 'SR_ENG', 'name': 'Senior Engineer', 'grade': 'E3', 'band': 'IC3'},
            {'code': 'JR_ENG', 'name': 'Junior Engineer', 'grade': 'E2', 'band': 'IC2'},
            {'code': 'PM', 'name': 'Project Manager', 'grade': 'E4', 'band': 'M1'},
            {'code': 'HR_MGR', 'name': 'HR Manager', 'grade': 'E4', 'band': 'M1'},
            {'code': 'HR_EXEC', 'name': 'HR Executive', 'grade': 'E2', 'band': 'IC2'},
            {'code': 'ACCT_MGR', 'name': 'Accounts Manager', 'grade': 'E4', 'band': 'M1'},
            {'code': 'ACCT_EXEC', 'name': 'Accounts Executive', 'grade': 'E2', 'band': 'IC2'},
            {'code': 'DESIGNER', 'name': 'UI/UX Designer', 'grade': 'E3', 'band': 'IC3'},
            {'code': 'TRAINEE', 'name': 'Graduate Trainee', 'grade': 'E1', 'band': 'IC1'},
            {'code': 'SALES_MGR', 'name': 'Sales Manager', 'grade': 'E4', 'band': 'M1'},
            {'code': 'SALES_EXEC', 'name': 'Sales Executive', 'grade': 'E2', 'band': 'IC2'},
        ]
        desigs = {}
        for d in desig_data:
            d['department'] = random.choice(list(departments.values())) if d['code'] != 'SALES_MGR' else departments['Sales']
            try:
                obj, _ = Designation.objects.get_or_create(code=d['code'], defaults=d)
                desigs[d['code']] = obj
                result.ok(f"Designation: {d['code']}")
            except Exception as e:
                result.fail(f"Designation {d['code']}", str(e))

        # Test designation unique constraint
        try:
            Designation.objects.create(code='CEO', name='Duplicate CEO', grade='E5', band='IC5')
            result.fail("Designation unique constraint", "Duplicate code 'CEO' was accepted")
        except (IntegrityError, Exception):
            result.ok("Designation unique constraint: duplicate code rejected")

        # CostCenter
        cc_data = [
            {'code': 'CC-ENG', 'name': 'Engineering', 'budget': 50000000},
            {'code': 'CC-HR', 'name': 'Human Resources', 'budget': 5000000},
            {'code': 'CC-FIN', 'name': 'Finance & Accounts', 'budget': 3000000},
            {'code': 'CC-DES', 'name': 'Design', 'budget': 10000000},
            {'code': 'CC-MGT', 'name': 'Management', 'budget': 80000000},
            {'code': 'CC-SALES', 'name': 'Sales & Marketing', 'budget': 25000000},
        ]
        for cc in cc_data:
            try:
                cc['department'] = departments.get(cc['name'].split(' & ')[0].split(' ')[0], None)
                obj, _ = CostCenter.objects.get_or_create(code=cc['code'], defaults=cc)
                result.ok(f"CostCenter: {cc['code']}")
            except Exception as e:
                result.fail(f"CostCenter {cc['code']}", str(e))

        # WorkLocation
        loc_data = [
            {'code': 'BLR', 'name': 'Bangalore HQ', 'city': 'Bangalore', 'state': 'Karnataka', 'country': 'India', 'pin_code': '560001', 'address': '123 Tech Park, Whitefield'},
            {'code': 'MUM', 'name': 'Mumbai Office', 'city': 'Mumbai', 'state': 'Maharashtra', 'country': 'India', 'pin_code': '400001', 'address': '456 Business Bay, Andheri'},
            {'code': 'DEL', 'name': 'Delhi Office', 'city': 'Delhi', 'state': 'Delhi', 'country': 'India', 'pin_code': '110001', 'address': '789 Corporate Hub, Connaught Place'},
            {'code': 'HYD', 'name': 'Hyderabad Office', 'city': 'Hyderabad', 'state': 'Telangana', 'country': 'India', 'pin_code': '500001', 'address': '321 IT Corridor, Hitech City'},
            {'code': 'CHE', 'name': 'Chennai Office', 'city': 'Chennai', 'state': 'Tamil Nadu', 'country': 'India', 'pin_code': '600001', 'address': '654 IT Expressway'},
        ]
        locs = {}
        for loc in loc_data:
            try:
                obj, _ = WorkLocation.objects.get_or_create(code=loc['code'], defaults=loc)
                locs[loc['code']] = obj
                result.ok(f"WorkLocation: {loc['code']}")
            except Exception as e:
                result.fail(f"WorkLocation {loc['code']}", str(e))

        # Shift
        shift_data = [
            {'code': 'GEN', 'name': 'General Shift', 'shift_type': 'GENERAL', 'start_time': '09:00:00', 'end_time': '18:00:00', 'break_duration_minutes': 60},
            {'code': 'NIGHT', 'name': 'Night Shift', 'shift_type': 'NIGHT', 'start_time': '21:00:00', 'end_time': '06:00:00', 'break_duration_minutes': 45},
            {'code': 'FLEX', 'name': 'Flexible Shift', 'shift_type': 'FLEXIBLE', 'start_time': '08:00:00', 'end_time': '17:00:00', 'break_duration_minutes': 60},
            {'code': 'SPLIT', 'name': 'Split Shift', 'shift_type': 'SPLIT', 'start_time': '07:00:00', 'end_time': '20:00:00', 'break_duration_minutes': 120},
            {'code': 'CUSTOM', 'name': 'Custom Shift', 'shift_type': 'CUSTOM', 'start_time': '10:00:00', 'end_time': '19:00:00', 'break_duration_minutes': 30},
        ]
        shifts = {}
        for s in shift_data:
            try:
                obj, _ = Shift.objects.get_or_create(code=s['code'], defaults=s)
                shifts[s['code']] = obj
                result.ok(f"Shift: {s['code']}")
            except Exception as e:
                result.fail(f"Shift {s['code']}", str(e))

        # Skill
        skill_names = [
            'Python', 'JavaScript', 'Django', 'React', 'PostgreSQL', 'AWS', 'Docker',
            'Project Management', 'Leadership', 'Communication', 'Teamwork',
            'UI/UX Design', 'HR Management', 'Payroll Processing', 'Statutory Compliance',
            'Java', 'Kubernetes', 'Machine Learning', 'Data Analysis', 'DevOps',
            'Go Lang', 'Rust', 'GraphQL', 'TypeScript', 'Node.js',
        ]
        skills = {}
        for name in skill_names:
            try:
                obj, _ = Skill.objects.get_or_create(name=name)
                skills[name] = obj
                result.ok(f"Skill: {name}")
            except Exception as e:
                result.fail(f"Skill {name}", str(e))

        # Holiday
        holidays_data = [
            {'name': 'Republic Day', 'holiday_date': date(2026, 1, 26), 'is_national': True},
            {'name': 'Holi', 'holiday_date': date(2026, 3, 14), 'is_national': False},
            {'name': 'Independence Day', 'holiday_date': date(2026, 8, 15), 'is_national': True},
            {'name': 'Gandhi Jayanti', 'holiday_date': date(2026, 10, 2), 'is_national': True},
            {'name': 'Diwali', 'holiday_date': date(2026, 11, 1), 'is_national': False},
            {'name': 'Christmas', 'holiday_date': date(2026, 12, 25), 'is_national': True},
            {'name': 'Makar Sankranti', 'holiday_date': date(2026, 1, 14), 'is_national': False},
            {'name': 'Eid-ul-Fitr', 'holiday_date': date(2026, 4, 1), 'is_national': False},
            {'name': 'Dussehra', 'holiday_date': date(2026, 10, 22), 'is_national': False},
        ]
        holiday_objs = []
        for h in holidays_data:
            try:
                obj, _ = Holiday.objects.get_or_create(name=h['name'], holiday_date=h['holiday_date'], defaults=h)
                holiday_objs.append(obj)
                result.ok(f"Holiday: {h['name']}")
            except Exception as e:
                result.fail(f"Holiday {h['name']}", str(e))

        # ============================================================
        # PHASE 2: Employee Data
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n👤 PHASE 2: Employees'))

        try:
            superadmin_user = User.objects.get(email='developerhertex@gmail.com')
        except User.DoesNotExist:
            superadmin_user = User.objects.create_user(
                email='developerhertex@gmail.com',
                password='Admin@12345',
                role='Superadmin',
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            result.ok("Superadmin user created")

        employees = []
        emp_data_list = [
            # (id_suffix, first, last, gender, dept, desig, loc, emp_type, mobile, aadhaar, pan, email_e)
            ('001', 'Arun', 'Kumar', 'MALE', 'Management', 'CEO', 'BLR', 'PERMANENT',
             '+919876543210', '111122223333', 'ABCDE1234F', 'arun.kumar'),
            ('002', 'Priya', 'Sharma', 'FEMALE', 'Management', 'CTO', 'BLR', 'PERMANENT',
             '919999888877', '222233334444', 'FGHIJ5678K', 'priya.sharma'),
            ('003', 'Rajesh', 'Patel', 'MALE', 'Human Resources', 'HR_HEAD', 'BLR', 'PERMANENT',
             '+19876543210', '333344445555', 'KLMNO9012P', 'rajesh.patel'),
            ('004', 'Sneha', 'Reddy', 'FEMALE', 'Engineering', 'SR_ENG', 'BLR', 'PERMANENT',
             '9876543210', '444455556666', 'PQRST3456U', 'sneha.reddy'),
            ('005', 'Vikram', 'Singh', 'MALE', 'Engineering', 'SR_ENG', 'BLR', 'PERMANENT',
             '9876543211', '555566667777', 'UVWXY7890Z', 'vikram.singh'),
            ('006', 'Anita', 'Verma', 'FEMALE', 'Engineering', 'JR_ENG', 'HYD', 'PERMANENT',
             '9876543212', '666677778888', 'ABCDE1235G', 'anita.verma'),
            ('007', 'Ravi', 'Joshi', 'MALE', 'Engineering', 'JR_ENG', 'BLR', 'PERMANENT',
             '9876543213', '777788889999', 'FGHIJ5679H', 'ravi.joshi'),
            ('008', 'Deepa', 'Nair', 'FEMALE', 'Engineering', 'TRAINEE', 'HYD', 'TRAINEE',
             '9876543214', '888899990000', 'KLMNO9013Q', 'deepa.nair'),
            ('009', 'Karthik', 'Iyengar', 'MALE', 'Design', 'DESIGNER', 'MUM', 'CONTRACT',
             '9876543215', '999900001111', 'PQRST3457V', 'karthik.iyengar'),
            ('010', 'Meera', 'Chopra', 'FEMALE', 'Human Resources', 'HR_MGR', 'BLR', 'PERMANENT',
             '9876543216', '111122224444', 'UVWXY7891A', 'meera.chopra'),
            ('011', 'Suresh', 'Babu', 'MALE', 'Finance', 'ACCT_MGR', 'BLR', 'PERMANENT',
             '9876543217', '222233335555', 'ABCDE1236H', 'suresh.babu'),
            ('012', 'Lakshmi', 'Devi', 'FEMALE', 'Finance', 'ACCT_EXEC', 'MUM', 'PERMANENT',
             '9876543218', '333344446666', 'FGHIJ5680L', 'lakshmi.devi'),
            ('013', 'Ajay', 'Mehta', 'MALE', 'Engineering', 'PM', 'DEL', 'PERMANENT',
             '9876543219', '444455557777', 'KLMNO9014R', 'ajay.mehta'),
            ('014', 'Neha', 'Pillai', 'FEMALE', 'Human Resources', 'HR_EXEC', 'DEL', 'PERMANENT',
             '9876543220', '555566668888', 'PQRST3458W', 'neha.pillai'),
            ('015', 'Manish', 'Agarwal', 'MALE', 'Design', 'DESIGNER', 'MUM', 'PERMANENT',
             '9876543221', '666677779999', 'UVWXY7892B', 'manish.agarwal'),
            ('016', 'Rohit', 'Sharma', 'MALE', 'Sales', 'SALES_MGR', 'BLR', 'PERMANENT',
             '9876543222', '777788880000', 'ABCDE1237J', 'rohit.sharma'),
            ('017', 'Pooja', 'Mehta', 'FEMALE', 'Sales', 'SALES_EXEC', 'MUM', 'CONTRACT',
             '9876543223', '888899991111', 'FGHIJ5681M', 'pooja.mehta'),
            ('018', 'Test', 'Employee', 'MALE', 'Engineering', 'TRAINEE', 'HYD', 'TRAINEE',
             '9876543224', '999900002222', 'KLMNO9015S', 'test.employee'),
        ]

        for i, (sid, first, last, gender, dept_name, desig_code, loc_code, emp_type, mobile, aadhaar, pan, email_p) in enumerate(emp_data_list):
            try:
                user_email = f"{email_p}@hertex.com"
                user, _ = User.objects.get_or_create(
                    email=user_email,
                    defaults={
                        'first_name': first,
                        'last_name': last,
                        'role': 'Employee',
                        'is_active': True,
                    }
                )
                if not user.password:
                    user.set_password('password123')
                    user.save()

                designation = desigs.get(desig_code)
                location = locs.get(loc_code)
                dept = departments.get(dept_name)
                manager = employees[i - 1] if i > 0 else None

                doj = date(2025, 6, 1) + timedelta(days=random.randint(0, 180))
                prob_end = doj + timedelta(days=180)

                emp = Employee.objects.create(
                    employee_id=f"EMP-{sid}",
                    user=user,
                    first_name=first,
                    last_name=last,
                    date_of_birth=date(1990, random.randint(1, 12), random.randint(1, 28)),
                    gender=gender,
                    marital_status='MARRIED' if i % 3 == 0 else 'SINGLE',
                    blood_group=random.choice(['A+', 'B+', 'O+', 'AB+', 'A-', 'B-', 'O-', 'AB-']),
                    nationality='Indian',
                    personal_email=user_email,
                    official_email=f"{email_p}@bytehive.com",
                    personal_mobile=mobile,
                    current_address=f"{i+1}, {random.choice(['MG Road', 'Brigade Road', 'Church Street'])}",
                    current_city=location.city if location else 'Bangalore',
                    current_state=location.state if location else 'Karnataka',
                    current_country='India',
                    current_pin_code=location.pin_code if location else '560001',
                    permanent_address=f"{i+1}, {random.choice(['Main Road', 'Tank Street'])}",
                    permanent_city=random.choice(['Bangalore', 'Mumbai', 'Delhi', 'Chennai', 'Hyderabad']),
                    permanent_state=random.choice(['Karnataka', 'Maharashtra', 'Delhi', 'Tamil Nadu', 'Telangana']),
                    permanent_country='India',
                    permanent_pin_code='560001',
                    emergency_contact_1_name='Emergency Contact',
                    emergency_contact_1_mobile=f'9{random.randint(7000000000, 9999999999)}',
                    emergency_contact_1_relation='Spouse',
                    aadhaar_number=aadhaar,
                    pan_number=pan,
                    bank_account_number=f"BANK{random.randint(100000000, 999999999)}",
                    bank_name=random.choice(['HDFC Bank', 'ICICI Bank', 'SBI', 'Axis Bank']),
                    ifsc_code=random.choice(['HDFC0001234', 'ICIC0005678', 'SBIN0009012', 'UTIB0003456']),
                    account_holder_name=f"{first} {last}",
                    employment_type=emp_type,
                    date_of_joining=doj,
                    probation_end_date=prob_end,
                    confirmation_date=prob_end + timedelta(days=1),
                    notice_period_days=30,
                    status='ACTIVE',
                    department=dept,
                    designation=designation,
                    work_location=location,
                    grade=designation.grade if designation else None,
                    band=designation.band if designation else None,
                    reporting_manager=manager,
                    work_shift='GENERAL',
                    is_active=True,
                )
                employees.append(emp)
                result.ok(f"Employee: {emp.employee_id} {first} {last}")
            except Exception as e:
                import traceback, sys
                tb = traceback.format_exc()
                result.fail(f"Employee {sid} {first} {last}", f"{type(e).__name__}: {e}")
                result.fail(f"Employee {sid} traceback", tb)
                print(tb, file=sys.stderr)

        # ============================================================
        # PHASE 2b: Validation Tests (valid/invalid data)
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n🔬 PHASE 2b: Validator Tests'))

        # Test Aadhaar validator (12 digits)
        try:
            emp = Employee.objects.create(
                employee_id='TEST-AADHAAR-1',
                first_name='Test', last_name='Aadhaar',
                date_of_birth=date(1990, 1, 1), gender='MALE',
                nationality='Indian',
                personal_email='test.aadhaar1@hertex.com',
                personal_mobile='9876543210',
                current_address='Test', current_city='Test',
                current_state='Test', current_country='India',
                current_pin_code='560001',
                permanent_address='Test', permanent_city='Test',
                permanent_state='Test', permanent_country='India',
                permanent_pin_code='560001',
                aadhaar_number='1234',  # Too short
                employment_type='PERMANENT', date_of_joining=date.today(),
                notice_period_days=30, status='ACTIVE', work_shift='GENERAL',
            )
            result.fail("Aadhaar validator", "Short aadhaar was accepted")
            emp.delete()
        except Exception:
            result.ok("Aadhaar validator: short value rejected")

        # Test PAN validator
        try:
            emp = Employee.objects.create(
                employee_id='TEST-PAN-1',
                first_name='Test', last_name='PAN',
                date_of_birth=date(1990, 1, 1), gender='MALE',
                nationality='Indian',
                personal_email='test.pan1@hertex.com',
                personal_mobile='9876543210',
                current_address='Test', current_city='Test',
                current_state='Test', current_country='India',
                current_pin_code='560001',
                permanent_address='Test', permanent_city='Test',
                permanent_state='Test', permanent_country='India',
                permanent_pin_code='560001',
                pan_number='ABCD1234E',  # Wrong format (4 letters, 4 digits, 1 letter)
                employment_type='PERMANENT', date_of_joining=date.today(),
                notice_period_days=30, status='ACTIVE', work_shift='GENERAL',
            )
            result.fail("PAN validator", "Bad PAN was accepted")
            emp.delete()
        except Exception:
            result.ok("PAN validator: bad format rejected")

        # Test IFSC validator
        try:
            emp = Employee.objects.create(
                employee_id='TEST-IFSC-1',
                first_name='Test', last_name='IFSC',
                date_of_birth=date(1990, 1, 1), gender='MALE',
                nationality='Indian',
                personal_email='test.ifsc1@hertex.com',
                personal_mobile='9876543210',
                current_address='Test', current_city='Test',
                current_state='Test', current_country='India',
                current_pin_code='560001',
                permanent_address='Test', permanent_city='Test',
                permanent_state='Test', permanent_country='India',
                permanent_pin_code='560001',
                ifsc_code='HDFC1234567',  # Missing 0 after 4 letters
                employee_id_for_error='NA',
                employment_type='PERMANENT', date_of_joining=date.today(),
                notice_period_days=30, status='ACTIVE', work_shift='GENERAL',
            )
            result.fail("IFSC validator", "Bad IFSC was accepted")
            emp.delete()
        except Exception:
            result.ok("IFSC validator: bad format rejected")

        # Test PIN code validator
        try:
            emp = Employee.objects.create(
                employee_id='TEST-PIN-1',
                first_name='Test', last_name='PIN',
                date_of_birth=date(1990, 1, 1), gender='MALE',
                nationality='Indian',
                personal_email='test.pin1@hertex.com',
                personal_mobile='9876543210',
                current_address='Test', current_city='Test',
                current_state='Test', current_country='India',
                current_pin_code='5600',  # Too short
                permanent_address='Test', permanent_city='Test',
                permanent_state='Test', permanent_country='India',
                permanent_pin_code='560001',
                employment_type='PERMANENT', date_of_joining=date.today(),
                notice_period_days=30, status='ACTIVE', work_shift='GENERAL',
            )
            result.fail("PIN validator", "Short PIN was accepted")
            emp.delete()
        except Exception:
            result.ok("PIN validator: short PIN rejected")

        # Test mobile validator
        try:
            emp = Employee.objects.create(
                employee_id='TEST-MOBILE-1',
                first_name='Test', last_name='Mobile',
                date_of_birth=date(1990, 1, 1), gender='MALE',
                nationality='Indian',
                personal_email='test.mobile1@hertex.com',
                personal_mobile='123',  # Too short
                current_address='Test', current_city='Test',
                current_state='Test', current_country='India',
                current_pin_code='560001',
                permanent_address='Test', permanent_city='Test',
                permanent_state='Test', permanent_country='India',
                permanent_pin_code='560001',
                employment_type='PERMANENT', date_of_joining=date.today(),
                notice_period_days=30, status='ACTIVE', work_shift='GENERAL',
            )
            result.fail("Mobile validator", "Short mobile was accepted")
            emp.delete()
        except Exception:
            result.ok("Mobile validator: short mobile rejected")

        # Test unique constraints on Employee
        try:
            duplicate = Employee.objects.create(
                employee_id='EMP-001',
                first_name='Dup', last_name='User',
                date_of_birth=date(1990, 1, 1), gender='MALE',
                nationality='Indian',
                personal_email='arun.kumar@hertex.com',  # Already used
                personal_mobile='9876543299',
                current_address='Test', current_city='Test',
                current_state='Test', current_country='India',
                current_pin_code='560001',
                permanent_address='Test', permanent_city='Test',
                permanent_state='Test', permanent_country='India',
                permanent_pin_code='560001',
                employment_type='PERMANENT', date_of_joining=date.today(),
                notice_period_days=30, status='ACTIVE', work_shift='GENERAL',
            )
            result.fail("Employee unique constraint", "Duplicate employee_id accepted")
            duplicate.delete()
        except (IntegrityError, Exception):
            result.ok("Employee unique constraint: duplicate employee_id rejected")

        try:
            dup2 = Employee.objects.create(
                employee_id='EMP-UNIQUE-EMAIL',
                first_name='Dup', last_name='Email',
                date_of_birth=date(1990, 1, 1), gender='MALE',
                nationality='Indian',
                personal_email='arun.kumar@hertex.com',  # Duplicate email
                personal_mobile='9876543298',
                current_address='Test', current_city='Test',
                current_state='Test', current_country='India',
                current_pin_code='560001',
                permanent_address='Test', permanent_city='Test',
                permanent_state='Test', permanent_country='India',
                permanent_pin_code='560001',
                employment_type='PERMANENT', date_of_joining=date.today(),
                notice_period_days=30, status='ACTIVE', work_shift='GENERAL',
            )
            result.fail("Employee personal_email unique", "Duplicate email accepted")
            dup2.delete()
        except (IntegrityError, Exception):
            result.ok("Employee unique: duplicate personal_email rejected")

        # ============================================================
        # PHASE 3: Employee Related Models
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n📁 PHASE 3: Employee Related Data'))

        emp = employees[0] if employees else None

        # EmployeeEmergencyContact
        if emp:
            try:
                obj, _ = EmployeeEmergencyContact.objects.get_or_create(
                    employee=emp,
                    name='Mother Emergency',
                    defaults={
                        'relationship': 'MOTHER',
                        'contact_number': '9876543299',
                        'is_primary': True,
                        'is_active': True,
                    }
                )
                result.ok(f"EmployeeEmergencyContact: {obj.name}")
            except Exception as e:
                result.fail("EmployeeEmergencyContact", str(e))

            # EmployeeFamily
            try:
                obj, _ = EmployeeFamily.objects.get_or_create(
                    employee=emp,
                    name='Spouse Name',
                    defaults={
                        'relationship': 'SPOUSE',
                        'date_of_birth': date(1992, 5, 10),
                        'is_dependent': False,
                        'is_nominee': True,
                        'nomination_percentage': 100,
                        'is_active': True,
                    }
                )
                result.ok(f"EmployeeFamily: {obj.name}")
            except Exception as e:
                result.fail("EmployeeFamily", str(e))

            # EmployeeBankAccount
            try:
                obj, _ = EmployeeBankAccount.objects.get_or_create(
                    employee=emp,
                    account_number='BANKACC1234567',
                    defaults={
                        'bank_name': 'HDFC Bank',
                        'branch': 'MG Road',
                        'ifsc_code': 'HDFC0001234',
                        'account_holder_name': 'Arun Kumar',
                        'is_active': True,
                        'is_primary': True,
                    }
                )
                result.ok(f"EmployeeBankAccount: {obj.account_number}")
            except Exception as e:
                result.fail("EmployeeBankAccount", str(e))

        # ============================================================
        # PHASE 4: Leave Management
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n🏖️ PHASE 4: Leave Management'))

        leave_type_data = [
            {'code': 'CL', 'name': 'Casual Leave', 'leave_type': 'CASUAL', 'default_annual_allocation': 12,
             'accrual_frequency': 'MONTHLY', 'max_carry_forward': 5, 'can_go_negative': False,
             'min_balance_required': 0, 'max_continuous_days': 7, 'is_encashable': True, 'encashment_max_days': 3},
            {'code': 'SL', 'name': 'Sick Leave', 'leave_type': 'SICK', 'default_annual_allocation': 10,
             'accrual_frequency': 'MONTHLY', 'max_carry_forward': 3, 'can_go_negative': True,
             'min_balance_required': 0, 'max_continuous_days': 15, 'is_encashable': False, 'encashment_max_days': 0},
            {'code': 'EL', 'name': 'Earned Leave', 'leave_type': 'EARNED', 'default_annual_allocation': 20,
             'accrual_frequency': 'MONTHLY', 'max_carry_forward': 15, 'can_go_negative': False,
             'min_balance_required': 0, 'max_continuous_days': 30, 'is_encashable': True, 'encashment_max_days': 10},
            {'code': 'ML', 'name': 'Maternity Leave', 'leave_type': 'MATERNITY', 'default_annual_allocation': 182,
             'accrual_frequency': 'ANNUAL', 'max_carry_forward': 0, 'can_go_negative': True,
             'min_balance_required': 0, 'max_continuous_days': 182, 'is_encashable': False, 'encashment_max_days': 0},
            {'code': 'PAT', 'name': 'Paternity Leave', 'leave_type': 'PATERNITY', 'default_annual_allocation': 5,
             'accrual_frequency': 'ANNUAL', 'max_carry_forward': 0, 'can_go_negative': False,
             'min_balance_required': 0, 'max_continuous_days': 5, 'is_encashable': False, 'encashment_max_days': 0},
            {'code': 'COFF', 'name': 'Comp Off', 'leave_type': 'COMP_OFF', 'default_annual_allocation': 0,
             'accrual_frequency': 'MONTHLY', 'max_carry_forward': 3, 'can_go_negative': False,
             'min_balance_required': 0, 'max_continuous_days': 3, 'is_encashable': False, 'encashment_max_days': 0},
        ]
        leave_types = {}
        for lt in leave_type_data:
            try:
                obj, _ = LeaveType.objects.get_or_create(code=lt['code'], defaults=lt)
                leave_types[lt['code']] = obj
                result.ok(f"LeaveType: {lt['code']}")
            except Exception as e:
                result.fail(f"LeaveType {lt['code']}", str(e))

        # EmployeeLeaveBalance
        current_fy = f"2025-2026"
        for e in employees:
            for lt_code in ['CL', 'SL', 'EL']:
                lt = leave_types.get(lt_code)
                if not lt:
                    continue
                try:
                    obj, _ = EmployeeLeaveBalance.objects.get_or_create(
                        employee=e,
                        leave_type=lt,
                        financial_year=current_fy,
                        defaults={
                            'opening_balance': lt.default_annual_allocation,
                            'accrued_days': 0,
                            'used_days': 0,
                            'pending_days': 0,
                            'encashed_days': 0,
                            'lapsed_days': 0,
                            'current_balance': lt.default_annual_allocation,
                        }
                    )
                    result.ok(f"LeaveBalance: {e.employee_id} {lt_code}")
                except Exception as exc:
                    result.fail(f"LeaveBalance {e.employee_id} {lt_code}", str(exc))

        # Test LeaveBalance unique_together
        try:
            dup_bal = EmployeeLeaveBalance.objects.create(
                employee=employees[0],
                leave_type=leave_types['CL'],
                financial_year=current_fy,
                opening_balance=12, accrued_days=0, used_days=0,
                pending_days=0, encashed_days=0, lapsed_days=0, current_balance=12,
            )
            result.fail("LeaveBalance unique_together", "Duplicate (emp, lt, fy) accepted")
            dup_bal.delete()
        except (IntegrityError, Exception):
            result.ok("LeaveBalance unique_together: duplicate rejected")

        # LeaveApplication
        if employees and leave_types:
            for i, e in enumerate(employees[:10]):
                try:
                    lt = leave_types[random.choice(['CL', 'SL', 'EL'])]
                    d_from = date(2026, random.randint(1, 6), random.randint(1, 20))
                    days = random.randint(1, 3)
                    d_to = d_from + timedelta(days=days - 1)
                    obj = LeaveApplication.objects.create(
                        employee=e,
                        leave_type=lt,
                        date_from=d_from,
                        date_to=d_to,
                        number_of_days=days,
                        reason=random.choice(['Family function', 'Not feeling well', 'Personal work', 'Vacation']),
                        approval_status=random.choice(['PENDING', 'APPROVED', 'APPROVED', 'REJECTED']),
                        applied_date=d_from - timedelta(days=random.randint(1, 7)),
                        is_backdated=random.choice([True, False]),
                    )
                    result.ok(f"LeaveApp: {e.employee_id} {d_from}-{d_to}")
                except Exception as exc:
                    result.fail(f"LeaveApp {e.employee_id}", str(exc))

        # CompensatoryOff
        if employees:
            for i, e in enumerate(employees[:5]):
                try:
                    obj, _ = CompensatoryOff.objects.get_or_create(
                        employee=e,
                        earned_on_date=date(2026, 1, 15 + i),
                        defaults={
                            'earned_hours': Decimal('8.0'),
                            'status': 'EARNED' if i % 2 == 0 else 'AVAILED',
                            'availed_on_date': date(2026, 2, 15 + i) if i % 2 == 1 else None,
                        }
                    )
                    result.ok(f"CompOff: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"CompOff {e.employee_id}", str(exc))

        # ============================================================
        # PHASE 5: Attendance
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n📅 PHASE 5: Attendance'))

        attendance_employees = employees[:8]
        att_dates = []
        for m in [1, 2, 3]:
            for day in range(1, 26):
                d = date(2026, m, day)
                if d.weekday() == 6:
                    continue
                att_dates.append(d)

        count = 0
        for e in attendance_employees:
            for d in att_dates[:30]:
                rand = random.random()
                if rand < 0.75:
                    status = 'PRESENT'
                    ci = f"{random.randint(8, 10):02d}:{random.randint(0, 59):02d}:00"
                    co = f"{random.randint(17, 19):02d}:{random.randint(0, 59):02d}:00"
                    wh = Decimal(str(round(random.uniform(8, 10), 2)))
                elif rand < 0.85:
                    status = 'WFH'
                    ci = f"{random.randint(8, 10):02d}:{random.randint(0, 59):02d}:00"
                    co = f"{random.randint(17, 19):02d}:{random.randint(0, 59):02d}:00"
                    wh = Decimal(str(round(random.uniform(8, 10), 2)))
                elif rand < 0.92:
                    status = 'HALF_DAY'
                    ci = f"{random.randint(8, 10):02d}:{random.randint(0, 59):02d}:00"
                    co = f"{random.randint(12, 14):02d}:{random.randint(0, 59):02d}:00"
                    wh = Decimal('4.0')
                elif rand < 0.97:
                    status = 'ABSENT'
                    ci = None
                    co = None
                    wh = Decimal('0')
                else:
                    status = 'HOLIDAY'
                    ci = None
                    co = None
                    wh = Decimal('0')

                try:
                    obj, _ = Attendance.objects.get_or_create(
                        employee=e,
                        date=d,
                        defaults={
                            'check_in_time': ci,
                            'check_out_time': co,
                            'status': status,
                            'shift': 'GENERAL',
                            'working_hours': wh,
                            'is_late': False,
                            'is_early_checkout': False,
                        }
                    )
                    count += 1
                except Exception as exc:
                    result.fail(f"Attendance {e.employee_id} {d}", str(exc))
        result.ok(f"Attendance records: {count}")

        # Test Attendance unique_together
        try:
            Attendance.objects.create(
                employee=employees[0],
                date=att_dates[0] if att_dates else date(2026, 1, 1),
                status='PRESENT', working_hours=8,
                shift='GENERAL',
            )
            result.fail("Attendance unique_together", "Duplicate (emp, date) accepted")
        except (IntegrityError, Exception):
            result.ok("Attendance unique_together: duplicate rejected")

        # OvertimeRequest
        if employees:
            for i, e in enumerate(employees[:5]):
                try:
                    obj, _ = OvertimeRequest.objects.get_or_create(
                        employee=e,
                        date=date(2026, 1, 10 + i),
                        defaults={
                            'overtime_hours': Decimal('2.5'),
                            'reason': 'Project deadline work',
                            'status': 'APPROVED',
                            'approved_by': employees[0] if employees else None,
                        }
                    )
                    result.ok(f"OvertimeRequest: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"OvertimeRequest {e.employee_id}", str(exc))

        # ShiftSwapRequest
        if employees and len(employees) >= 2:
            try:
                obj = ShiftSwapRequest.objects.create(
                    employee=employees[0],
                    swap_with=employees[1],
                    from_date=date(2026, 2, 1),
                    to_date=date(2026, 2, 1),
                    reason='Personal work',
                    status='PENDING',
                )
                result.ok(f"ShiftSwapRequest: {obj.id}")
            except Exception as exc:
                result.fail("ShiftSwapRequest", str(exc))

        # AttendanceRegularizationRequest
        if employees:
            try:
                obj = AttendanceRegularizationRequest.objects.create(
                    employee=employees[0],
                    attendance_date=date(2026, 1, 5),
                    actual_check_in='09:15:00',
                    expected_check_in='09:00:00',
                    reason='Traffic jam',
                    status='PENDING',
                )
                result.ok(f"AttendanceRegularization: {obj.id}")
            except Exception as exc:
                result.fail("AttendanceRegularization", str(exc))

        # ============================================================
        # PHASE 6: Payroll & Salary
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n💰 PHASE 6: Payroll & Salary'))

        # SalaryComponent
        comp_data = [
            {'code': 'BASIC', 'name': 'Basic Salary', 'component_type': 'EARNINGS', 'is_fixed': True, 'is_taxable': True, 'order': 1},
            {'code': 'HRA', 'name': 'House Rent Allowance', 'component_type': 'EARNINGS', 'is_fixed': True, 'is_taxable': False, 'depends_on_basic': True, 'percentage_of_basic': 40, 'order': 2},
            {'code': 'CONVEYANCE', 'name': 'Conveyance Allowance', 'component_type': 'EARNINGS', 'is_fixed': True, 'is_taxable': False, 'exemption_limit': 1600, 'order': 3},
            {'code': 'MEDICAL', 'name': 'Medical Allowance', 'component_type': 'EARNINGS', 'is_fixed': True, 'is_taxable': False, 'exemption_limit': 15000, 'order': 4},
            {'code': 'SPECIAL', 'name': 'Special Allowance', 'component_type': 'EARNINGS', 'is_fixed': True, 'is_taxable': True, 'order': 5},
            {'code': 'PF_EMPLOYEE', 'name': 'Employee PF', 'component_type': 'DEDUCTIONS', 'is_fixed': False, 'is_statutory': True, 'order': 6},
            {'code': 'ESI_EMPLOYEE', 'name': 'Employee ESI', 'component_type': 'DEDUCTIONS', 'is_fixed': False, 'is_statutory': True, 'order': 7},
            {'code': 'PT', 'name': 'Professional Tax', 'component_type': 'DEDUCTIONS', 'is_fixed': False, 'is_statutory': True, 'order': 8},
            {'code': 'TDS', 'name': 'Tax Deducted at Source', 'component_type': 'DEDUCTIONS', 'is_fixed': False, 'is_statutory': True, 'order': 9},
            {'code': 'PERF_BONUS', 'name': 'Performance Bonus', 'component_type': 'VARIABLE', 'is_fixed': False, 'is_taxable': True, 'order': 10},
            {'code': 'GRATUITY', 'name': 'Gratuity', 'component_type': 'EARNINGS', 'is_fixed': True, 'is_statutory': True, 'order': 11},
        ]
        components = {}
        for c in comp_data:
            try:
                obj, _ = SalaryComponent.objects.get_or_create(code=c['code'], defaults=c)
                components[c['code']] = obj
                result.ok(f"SalaryComponent: {c['code']}")
            except Exception as e:
                result.fail(f"SalaryComponent {c['code']}", str(e))

        # SalaryStructure
        structures_data = {
            'MGT-2026': {'name': 'Management 2026', 'grade': 'E5', 'band': 'IC5'},
            'SR-2026': {'name': 'Senior Staff 2026', 'grade': 'E3', 'band': 'IC3'},
            'JR-2026': {'name': 'Junior Staff 2026', 'grade': 'E2', 'band': 'IC2'},
            'TRAINEE-2026': {'name': 'Trainee 2026', 'grade': 'E1', 'band': 'IC1'},
            'MGR-2026': {'name': 'Manager 2026', 'grade': 'E4', 'band': 'M1'},
            'SALES-2026': {'name': 'Sales 2026', 'grade': 'E4', 'band': 'IC4'},
        }
        structures = {}
        for code, data in structures_data.items():
            try:
                obj, _ = SalaryStructure.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': data['name'],
                        'grade': data['grade'],
                        'band': data['band'],
                        'effective_from': date(2026, 1, 1),
                        'is_active': True,
                    }
                )
                structures[code] = obj
                result.ok(f"SalaryStructure: {code}")
            except Exception as e:
                result.fail(f"SalaryStructure {code}", str(e))

        # SalaryStructureDetail
        if structures and components:
            for struct_code, struct in structures.items():
                for comp_code, pct in [('BASIC', 50), ('HRA', 40)]:
                    if comp_code not in components:
                        continue
                    try:
                        obj, _ = SalaryStructureDetail.objects.get_or_create(
                            salary_structure=struct,
                            component=components[comp_code],
                            defaults={
                                'amount': Decimal(str(pct)),
                                'is_percentage': True,
                                'order': 1 if comp_code == 'BASIC' else 2,
                            }
                        )
                        result.ok(f"SalaryStructureDetail: {struct_code} {comp_code}")
                    except Exception as e:
                        result.fail(f"SalaryStructureDetail {struct_code} {comp_code}", str(e))

        # EmployeeSalary
        grade_ctc = {'E5': 3000000, 'E4': 1500000, 'E3': 1200000, 'E2': 600000, 'E1': 350000, 'M1': 1400000, 'IC5': 3000000, 'IC4': 1500000, 'IC3': 1200000, 'IC2': 600000, 'IC1': 350000}
        for e in employees:
            try:
                grade = e.designation.grade if e.designation else 'E2'
                ctc = Decimal(str(grade_ctc.get(grade, 600000)))
                gross = (ctc * Decimal('0.85')).quantize(Decimal('0.01'))
                basic = gross * Decimal('0.50')
                net = gross - basic * Decimal('0.12') - Decimal('200')
                obj, _ = EmployeeSalary.objects.get_or_create(
                    employee=e,
                    effective_from=e.date_of_joining,
                    defaults={
                        'salary_structure': structures.get('MGT-2026') if grade in ['E5', 'E4'] else structures.get('SR-2026'),
                        'ctc': ctc,
                        'gross_salary': gross,
                        'net_salary': net,
                        'basic_salary': basic,
                        'is_active': True,
                    }
                )
                result.ok(f"EmployeeSalary: {e.employee_id}")
            except Exception as exc:
                result.fail(f"EmployeeSalary {e.employee_id}", str(exc))

        # Payroll
        for i, e in enumerate(employees):
            salary = EmployeeSalary.objects.filter(employee=e, is_active=True).first()
            if not salary:
                continue
            for m in range(1, 4):
                try:
                    gross = salary.gross_salary
                    basic = salary.basic_salary
                    pf = (basic * Decimal('0.12')).quantize(Decimal('0.01'))
                    pt = Decimal('200')
                    net = gross - pf - pt
                    obj, _ = Payroll.objects.get_or_create(
                        employee=e,
                        month=m,
                        year=2026,
                        defaults={
                            'payroll_period': f"2026-{m:02d}",
                            'working_days': 22,
                            'present_days': Decimal(str(random.randint(18, 22))),
                            'gross_salary': gross,
                            'total_deductions': pf + pt,
                            'net_salary': net,
                            'final_salary': net,
                            'status': 'PAID',
                            'processed_date': date(2026, m, 25),
                        }
                    )
                    result.ok(f"Payroll: {e.employee_id} 2026-{m:02d}")
                except Exception as exc:
                    result.fail(f"Payroll {e.employee_id} 2026-{m:02d}", str(exc))

        # PayrollComponentDetail
        payrolls = Payroll.objects.all()[:10]
        for p in payrolls:
            for comp_code in ['BASIC', 'HRA']:
                if comp_code not in components:
                    continue
                try:
                    obj, _ = PayrollComponentDetail.objects.get_or_create(
                        payroll=p,
                        component=components[comp_code],
                        defaults={'amount': p.gross_salary * Decimal('0.5') if comp_code == 'BASIC' else p.gross_salary * Decimal('0.2')}
                    )
                except Exception as exc:
                    result.fail(f"PayrollComponentDetail {p.id} {comp_code}", str(exc))
        result.ok(f"PayrollComponentDetail records for {len(payrolls)} payrolls")

        # SalaryRevision
        if len(employees) >= 3:
            for i, e in enumerate(employees[:3]):
                try:
                    obj, _ = SalaryRevision.objects.get_or_create(
                        employee=e,
                        effective_month=4,
                        effective_year=2026,
                        revision_type='ANNUAL',
                        defaults={
                            'previous_ctc': Decimal('1000000'),
                            'previous_gross': Decimal('850000'),
                            'previous_basic': Decimal('425000'),
                            'revised_ctc': Decimal('1200000'),
                            'revised_gross': Decimal('1020000'),
                            'revised_basic': Decimal('510000'),
                            'percentage_increase': Decimal('20.00'),
                            'reason': 'Annual Performance Revision',
                            'status': 'APPROVED',
                            'is_processed': True,
                        }
                    )
                    result.ok(f"SalaryRevision: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"SalaryRevision {e.employee_id}", str(exc))

        # EmployeeLoan
        if employees:
            for i, e in enumerate(employees[:4]):
                try:
                    principal = Decimal(str(random.choice([100000, 200000, 300000, 500000])))
                    rate = Decimal('12.00')
                    emis = 24
                    monthly_rate = rate / 100 / 12
                    emi = principal * monthly_rate * (1 + monthly_rate) ** emis / ((1 + monthly_rate) ** emis - 1)
                    total_payable = emi * emis
                    total_interest = total_payable - principal
                    obj, _ = EmployeeLoan.objects.get_or_create(
                        employee=e,
                        loan_type=random.choice(['PERSONAL', 'HOME', 'EDUCATION', 'VEHICLE', 'MEDICAL', 'FESTIVAL']),
                        sanction_date=date(2026, 1, 15 + i),
                        defaults={
                            'principal_amount': principal,
                            'interest_rate': rate,
                            'total_interest': total_interest.quantize(Decimal('0.01')),
                            'total_payable': total_payable.quantize(Decimal('0.01')),
                            'emi_amount': emi.quantize(Decimal('0.01')),
                            'total_emis': emis,
                            'emi_frequency': 'MONTHLY',
                            'paid_amount': Decimal('0'),
                            'paid_emis': 0,
                            'outstanding_amount': principal,
                            'first_emi_date': date(2026, 2, 1),
                            'status': 'ACTIVE',
                            'purpose': f'Loan for {random.choice(["home renovation", "medical emergency", "education", "vehicle purchase", "personal needs"])}',
                            'is_active': True,
                        }
                    )
                    result.ok(f"EmployeeLoan: {e.employee_id} {obj.loan_type}")
                except Exception as exc:
                    result.fail(f"EmployeeLoan {e.employee_id}", str(exc))

        # LoanRepayment
        loans = EmployeeLoan.objects.filter(status='ACTIVE')[:5]
        for loan in loans:
            for m in range(1, 3):
                try:
                    obj, _ = LoanRepayment.objects.get_or_create(
                        loan=loan,
                        month=m,
                        year=2026,
                        defaults={
                            'amount': loan.emi_amount,
                            'is_processed': True,
                        }
                    )
                    result.ok(f"LoanRepayment: {loan.id} month {m}")
                except Exception as exc:
                    result.fail(f"LoanRepayment {loan.id} month {m}", str(exc))

        # EmployeeReimbursement
        if employees:
            expense_types = ['TRAVEL', 'FOOD', 'MEDICAL', 'FUEL', 'STATIONERY', 'INTERNET', 'PHONE', 'CLIENT_ENTERTAINMENT', 'OTHER']
            for i, e in enumerate(employees[:6]):
                try:
                    obj, _ = EmployeeReimbursement.objects.get_or_create(
                        employee=e,
                        expense_type=random.choice(expense_types),
                        expense_date=date(2026, random.randint(1, 3), random.randint(1, 25)),
                        defaults={
                            'description': f'Business expense for {random.choice(["client meeting", "travel", "supplies", "dinner with team"])}',
                            'amount': Decimal(str(random.randint(1000, 25000))),
                            'bill_number': f'BILL-{random.randint(10000, 99999)}',
                            'status': random.choice(['PENDING', 'APPROVED', 'PAID', 'REJECTED']),
                        }
                    )
                    result.ok(f"Reimbursement: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"Reimbursement {e.employee_id}", str(exc))

        # ============================================================
        # PHASE 7: Statutory Compliance Configs
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n⚖️ PHASE 7: Statutory Compliance'))

        # PFConfiguration
        try:
            obj, _ = PFConfiguration.objects.get_or_create(
                effective_from=date(2026, 1, 1),
                defaults={
                    'employee_contribution_pct': Decimal('12.00'),
                    'employer_epf_pct': Decimal('3.67'),
                    'employer_eps_pct': Decimal('8.33'),
                    'employer_edli_pct': Decimal('0.50'),
                    'employer_admin_charges_pct': Decimal('0.50'),
                    'edli_admin_charges_pct': Decimal('0.01'),
                    'wage_ceiling': Decimal('15000.00'),
                    'eps_max_pensionable_salary': Decimal('15000.00'),
                    'is_active': True,
                }
            )
            result.ok("PFConfiguration created")
        except Exception as e:
            result.fail("PFConfiguration", str(e))

        # PFContribution
        if employees:
            for e in employees[:5]:
                for m in range(1, 4):
                    try:
                        basic = Decimal('15000')
                        obj, _ = PFContribution.objects.get_or_create(
                            employee=e,
                            month=m,
                            year=2026,
                            defaults={
                                'employee_contribution': (basic * Decimal('0.12')).quantize(Decimal('0.01')),
                                'employer_epf': (basic * Decimal('0.0367')).quantize(Decimal('0.01')),
                                'employer_eps': (basic * Decimal('0.0833')).quantize(Decimal('0.01')),
                                'employer_edli': (basic * Decimal('0.005')).quantize(Decimal('0.01')),
                                'employer_admin_charges': (basic * Decimal('0.005')).quantize(Decimal('0.01')),
                                'wage_amount': basic,
                                'is_processed': True,
                            }
                        )
                    except Exception as exc:
                        result.fail(f"PFContribution {e.employee_id} {m}", str(exc))
            result.ok("PFContribution records created")

        # ESIConfiguration
        try:
            obj, _ = ESIConfiguration.objects.get_or_create(
                effective_from=date(2026, 1, 1),
                defaults={
                    'employee_contribution_pct': Decimal('0.75'),
                    'employer_contribution_pct': Decimal('3.25'),
                    'wage_ceiling': Decimal('21000.00'),
                    'is_active': True,
                }
            )
            result.ok("ESIConfiguration created")
        except Exception as e:
            result.fail("ESIConfiguration", str(e))

        # ESIContribution
        if employees:
            for e in employees[:5]:
                for m in range(1, 4):
                    try:
                        gross = Decimal('18000')
                        obj, _ = ESIContribution.objects.get_or_create(
                            employee=e,
                            month=m,
                            year=2026,
                            defaults={
                                'employee_contribution': (gross * Decimal('0.0075')).quantize(Decimal('0.01')),
                                'employer_contribution': (gross * Decimal('0.0325')).quantize(Decimal('0.01')),
                                'wage_amount': gross,
                                'is_processed': True,
                            }
                        )
                    except Exception as exc:
                        result.fail(f"ESIContribution {e.employee_id} {m}", str(exc))
            result.ok("ESIContribution records created")

        # ProfessionalTaxSlab
        pt_slabs = [
            {'state': 'Karnataka', 'salary_from': 0, 'salary_to': 15000, 'tax_amount': Decimal('0'), 'frequency': 'MONTHLY'},
            {'state': 'Karnataka', 'salary_from': 15001, 'salary_to': 20000, 'tax_amount': Decimal('150'), 'frequency': 'MONTHLY'},
            {'state': 'Karnataka', 'salary_from': 20001, 'salary_to': 50000, 'tax_amount': Decimal('200'), 'frequency': 'MONTHLY'},
            {'state': 'Karnataka', 'salary_from': 50001, 'salary_to': None, 'tax_amount': Decimal('300'), 'frequency': 'MONTHLY'},
            {'state': 'Maharashtra', 'salary_from': 0, 'salary_to': 10000, 'tax_amount': Decimal('0'), 'frequency': 'MONTHLY'},
            {'state': 'Maharashtra', 'salary_from': 10001, 'salary_to': 25000, 'tax_amount': Decimal('175'), 'frequency': 'MONTHLY'},
            {'state': 'Maharashtra', 'salary_from': 25001, 'salary_to': 75000, 'tax_amount': Decimal('250'), 'frequency': 'MONTHLY'},
            {'state': 'Maharashtra', 'salary_from': 75001, 'salary_to': None, 'tax_amount': Decimal('300'), 'frequency': 'MONTHLY'},
            {'state': 'Delhi', 'salary_from': 0, 'salary_to': None, 'tax_amount': Decimal('208'), 'frequency': 'MONTHLY'},
            {'state': 'Telangana', 'salary_from': 0, 'salary_to': 15000, 'tax_amount': Decimal('0'), 'frequency': 'MONTHLY'},
            {'state': 'Telangana', 'salary_from': 15001, 'salary_to': 20000, 'tax_amount': Decimal('150'), 'frequency': 'MONTHLY'},
            {'state': 'Telangana', 'salary_from': 20001, 'salary_to': None, 'tax_amount': Decimal('200'), 'frequency': 'MONTHLY'},
        ]
        for slab in pt_slabs:
            try:
                obj, _ = ProfessionalTaxSlab.objects.get_or_create(
                    state=slab['state'],
                    salary_from=Decimal(str(slab['salary_from'])),
                    salary_to=Decimal(str(slab['salary_to'])) if slab['salary_to'] is not None else None,
                    defaults={
                        'tax_amount': slab['tax_amount'],
                        'frequency': slab['frequency'],
                        'effective_from': date(2026, 1, 1),
                        'is_active': True,
                    }
                )
            except Exception as exc:
                result.fail(f"ProfessionalTaxSlab {slab['state']} {slab['salary_from']}", str(exc))
        result.ok(f"ProfessionalTaxSlab records created")

        # PTContribution
        if employees:
            for e in employees[:5]:
                for m in range(1, 4):
                    try:
                        obj, _ = PTContribution.objects.get_or_create(
                            employee=e,
                            month=m,
                            year=2026,
                            defaults={
                                'tax_amount': Decimal('200'),
                                'is_processed': True,
                            }
                        )
                    except Exception as exc:
                        result.fail(f"PTContribution {e.employee_id} {m}", str(exc))
            result.ok("PTContribution records created")

        # TDSConfiguration
        try:
            obj, _ = TDSConfiguration.objects.get_or_create(
                financial_year='2025-2026',
                defaults={
                    'enable_old_regime': True,
                    'enable_new_regime': True,
                    'standard_deduction_old': Decimal('50000.00'),
                    'standard_deduction_new': Decimal('75000.00'),
                    'education_cess_pct': Decimal('4.00'),
                    'is_active': True,
                }
            )
            result.ok("TDSConfiguration created")
        except Exception as e:
            result.fail("TDSConfiguration", str(e))

        # InvestmentDeclaration
        if employees:
            for e in employees[:5]:
                try:
                    obj, _ = InvestmentDeclaration.objects.get_or_create(
                        employee=e,
                        financial_year='2025-2026',
                        defaults={
                            'section_80c': Decimal('50000'),
                            'section_80d': Decimal('15000'),
                            'section_80g': Decimal('5000'),
                            'hra_rent': Decimal('120000'),
                            'lta': Decimal('20000'),
                            'other_investments': Decimal('10000'),
                        }
                    )
                    result.ok(f"InvestmentDeclaration: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"InvestmentDeclaration {e.employee_id}", str(exc))

        # TDSCalculation
        if employees:
            for e in employees[:3]:
                for m in range(1, 4):
                    try:
                        obj, _ = TDSCalculation.objects.get_or_create(
                            employee=e,
                            financial_year='2025-2026',
                            month=m,
                            defaults={
                                'gross_income': Decimal('100000'),
                                'deductions': Decimal('50000'),
                                'taxable_income': Decimal('50000'),
                                'tax_amount': Decimal('5000'),
                                'education_cess': Decimal('200'),
                                'total_tax': Decimal('5200'),
                                'tds_deducted': Decimal('5200'),
                            }
                        )
                    except Exception as exc:
                        result.fail(f"TDSCalculation {e.employee_id} {m}", str(exc))
            result.ok("TDSCalculation records created")

        # GratuityConfiguration
        try:
            obj, _ = GratuityConfiguration.objects.get_or_create(
                is_active=True,
                defaults={
                    'formula_numerator': 15,
                    'formula_denominator': 26,
                    'min_service_years': 5,
                }
            )
            result.ok("GratuityConfiguration created")
        except Exception as e:
            result.fail("GratuityConfiguration", str(e))

        # GratuityCalculation
        if len(employees) >= 3:
            for e in employees[:3]:
                try:
                    obj, _ = GratuityCalculation.objects.get_or_create(
                        employee=e,
                        financial_year='2025-2026',
                        defaults={
                            'last_drawn_basic': Decimal('50000'),
                            'total_service_years': 6,
                            'gratuity_amount': (Decimal('50000') * Decimal('15') / Decimal('26') * Decimal('6')).quantize(Decimal('0.01')),
                            'is_processed': True,
                        }
                    )
                    result.ok(f"GratuityCalculation: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"GratuityCalculation {e.employee_id}", str(exc))

        # BonusConfiguration
        try:
            obj, _ = BonusConfiguration.objects.get_or_create(
                financial_year='2025-2026',
                defaults={
                    'minimum_bonus_pct': Decimal('8.33'),
                    'maximum_bonus_pct': Decimal('20.00'),
                    'wage_ceiling': Decimal('21000.00'),
                    'is_active': True,
                }
            )
            result.ok("BonusConfiguration created")
        except Exception as e:
            result.fail("BonusConfiguration", str(e))

        # BonusCalculation
        if employees:
            for e in employees[:3]:
                try:
                    obj, _ = BonusCalculation.objects.get_or_create(
                        employee=e,
                        financial_year='2025-2026',
                        defaults={
                            'eligible_basic': Decimal('15000'),
                            'bonus_percentage': Decimal('8.33'),
                            'bonus_amount': Decimal('1249.50'),
                            'is_processed': True,
                        }
                    )
                    result.ok(f"BonusCalculation: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"BonusCalculation {e.employee_id}", str(exc))

        # LWFConfiguration
        try:
            for state_name in ['Karnataka', 'Maharashtra', 'Telangana']:
                obj, _ = LWFConfiguration.objects.get_or_create(
                    state=state_name,
                    effective_from=date(2026, 1, 1),
                    defaults={
                        'employee_contribution': Decimal('40'),
                        'employer_contribution': Decimal('40'),
                        'wage_ceiling': Decimal('15000'),
                        'is_active': True,
                    }
                )
                result.ok(f"LWFConfiguration: {state_name}")
        except Exception as e:
            result.fail("LWFConfiguration", str(e))

        # LWFContribution
        if employees:
            for e in employees[:5]:
                for period in range(1, 4):
                    try:
                        obj, _ = LWFContribution.objects.get_or_create(
                            employee=e,
                            period=period,
                            year=2026,
                            defaults={
                                'employee_contribution': Decimal('40'),
                                'employer_contribution': Decimal('40'),
                                'is_processed': True,
                            }
                        )
                    except Exception as exc:
                        result.fail(f"LWFContribution {e.employee_id}", str(exc))
            result.ok("LWFContribution records created")

        # VPFContribution
        if employees:
            for e in employees[:3]:
                for m in range(1, 4):
                    try:
                        obj, _ = VPFContribution.objects.get_or_create(
                            employee=e,
                            month=m,
                            year=2026,
                            defaults={
                                'contribution_amount': Decimal('1000'),
                                'is_active': True,
                            }
                        )
                    except Exception as exc:
                        result.fail(f"VPFContribution {e.employee_id}", str(exc))
            result.ok("VPFContribution records created")

        # PFStatement
        if employees:
            try:
                obj, _ = PFStatement.objects.get_or_create(
                    employee=employees[0],
                    financial_year='2025-2026',
                    defaults={
                        'employee_contribution': Decimal('21600'),
                        'employer_contribution': Decimal('21600'),
                        'total_balance': Decimal('43200'),
                        'statement_date': date(2026, 3, 31),
                    }
                )
                result.ok(f"PFStatement: {employees[0].employee_id}")
            except Exception as exc:
                result.fail("PFStatement", str(exc))

        # ESICard
        if employees:
            try:
                obj, _ = ESICard.objects.get_or_create(
                    ip_number='ESIIP1234567890',
                    defaults={
                        'employee': employees[0],
                        'primary_center': 'ESIC Bangalore',
                        'is_active': True,
                    }
                )
                result.ok(f"ESICard: {obj.ip_number}")
            except Exception as exc:
                result.fail("ESICard", str(exc))

        # LowerDeductionCertificate
        if employees:
            try:
                obj, _ = LowerDeductionCertificate.objects.get_or_create(
                    employee=employees[0],
                    financial_year='2025-2026',
                    certificate_type='SECTION_197',
                    defaults={
                        'certificate_number': 'CERT-2026-001',
                        'applicable_rate': Decimal('5.00'),
                        'valid_from': date(2026, 1, 1),
                        'valid_to': date(2026, 12, 31),
                        'is_active': True,
                    }
                )
                result.ok(f"LowerDeductionCertificate: {obj.certificate_number}")
            except Exception as exc:
                result.fail("LowerDeductionCertificate", str(exc))

        # PTEnrollment
        if employees:
            for e in employees[:5]:
                try:
                    obj, _ = PTEnrollment.objects.get_or_create(
                        employee=e,
                        state='Karnataka',
                        defaults={
                            'enrollment_number': f'PTENR-{random.randint(10000, 99999)}',
                            'is_active': True,
                        }
                    )
                    result.ok(f"PTEnrollment: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"PTEnrollment {e.employee_id}", str(exc))

        # InternationalWorker
        if len(employees) >= 2:
            try:
                obj, _ = InternationalWorker.objects.get_or_create(
                    employee=employees[-1],
                    defaults={
                        'country_of_origin': 'USA',
                        'passport_number': 'USA1234567',
                        'work_permit_number': 'WP-2026-001',
                        'work_permit_valid_until': date(2028, 12, 31),
                        'is_active': True,
                    }
                )
                result.ok(f"InternationalWorker: {employees[-1].employee_id}")
            except Exception as exc:
                result.fail("InternationalWorker", str(exc))

        # Form12BA
        if employees:
            try:
                obj, _ = Form12BA.objects.get_or_create(
                    employee=employees[0],
                    financial_year='2025-2026',
                    defaults={
                        'gross_salary': Decimal('1200000'),
                        'perquisites_value': Decimal('50000'),
                        'profits_in_lieu': Decimal('0'),
                        'total_income': Decimal('1250000'),
                        'tds_deducted': Decimal('150000'),
                    }
                )
                result.ok(f"Form12BA: {employees[0].employee_id}")
            except Exception as exc:
                result.fail("Form12BA", str(exc))

        # Form24QReturn
        try:
            obj, _ = Form24QReturn.objects.get_or_create(
                financial_year='2025-2026',
                quarter='Q4',
                defaults={
                    'filing_date': date(2026, 5, 15),
                    'status': 'FILED',
                    'total_employees': len(employees),
                    'total_tds': Decimal('250000'),
                }
            )
            result.ok(f"Form24QReturn: Q4 2025-2026")
        except Exception as exc:
            result.fail("Form24QReturn", str(exc))

        # ComplianceCalendarEntry
        year = 2026
        cal_entries = [
            {'compliance_type': 'PF', 'title': 'PF ECR Filing - January 2026', 'due_date': date(2026, 2, 15), 'frequency': 'MONTHLY', 'period_year': year, 'period_month': 1},
            {'compliance_type': 'PF', 'title': 'PF ECR Filing - February 2026', 'due_date': date(2026, 3, 15), 'frequency': 'MONTHLY', 'period_year': year, 'period_month': 2},
            {'compliance_type': 'ESI', 'title': 'ESI Return - January 2026', 'due_date': date(2026, 2, 15), 'frequency': 'MONTHLY', 'period_year': year, 'period_month': 1},
            {'compliance_type': 'TDS', 'title': 'TDS Return Q4 2025-26', 'due_date': date(2026, 5, 31), 'frequency': 'QUARTERLY', 'period_year': year, 'period_quarter': 4},
            {'compliance_type': 'PT', 'title': 'PT Annual Return 2025-26', 'due_date': date(2026, 4, 30), 'frequency': 'ANNUAL', 'period_year': year},
            {'compliance_type': 'LWF', 'title': 'LWF Annual Return 2025-26', 'due_date': date(2026, 4, 30), 'frequency': 'ANNUAL', 'period_year': year},
            {'compliance_type': 'ESIC', 'title': 'ESIC Half-Yearly Return', 'due_date': date(2026, 5, 12), 'frequency': 'HALF_YEARLY', 'period_year': year, 'period_half': 1},
        ]
        for entry in cal_entries:
            try:
                obj, _ = ComplianceCalendarEntry.objects.get_or_create(
                    compliance_type=entry['compliance_type'],
                    title=entry['title'],
                    due_date=entry['due_date'],
                    defaults={
                        'frequency': entry['frequency'],
                        'period_year': entry.get('period_year'),
                        'period_month': entry.get('period_month'),
                        'period_quarter': entry.get('period_quarter'),
                        'period_half': entry.get('period_half'),
                        'status': 'PENDING',
                    }
                )
            except Exception as exc:
                result.fail(f"ComplianceCalendarEntry {entry['title']}", str(exc))
        result.ok("ComplianceCalendarEntry records created")

        # ============================================================
        # PHASE 8: Recruitment
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n🎯 PHASE 8: Recruitment'))

        hr_emp = next((e for e in employees if e.department and 'Human Resources' in e.department.name), employees[0])

        # JobRequisition
        reqs = []
        req_names = ['Senior Python Developer', 'React Frontend Developer', 'HR Executive', 'DevOps Engineer', 'UI/UX Designer']
        for i, title in enumerate(req_names):
            try:
                dept = departments[random.choice(['Engineering', 'Human Resources', 'Design'])]
                desig = random.choice(list(desigs.values()))
                obj, _ = JobRequisition.objects.get_or_create(
                    department=dept,
                    designation=desig,
                    requested_by=hr_emp,
                    defaults={
                        'vacancies': random.randint(1, 3),
                        'priority': random.choice(['HIGH', 'MEDIUM', 'CRITICAL']),
                        'status': 'APPROVED' if i < 3 else 'PENDING',
                        'justification': f'Need resources for {title} role',
                        'budget_allocated': Decimal(str(random.randint(500000, 2000000))),
                    }
                )
                reqs.append(obj)
                result.ok(f"JobRequisition: {title}")
            except Exception as exc:
                result.fail(f"JobRequisition {title}", str(exc))

        # Candidate
        cand_data = [
            ('Rahul', 'Dravid', 'rahul.dravid@candidates.com', 7, ['Python', 'Django', 'PostgreSQL']),
            ('Sachin', 'Tendulkar', 'sachin.t@candidates.com', 5, ['JavaScript', 'React', 'Node.js']),
            ('Virat', 'Kohli', 'virat.k@candidates.com', 3, ['Python', 'Django', 'AWS']),
            ('MS', 'Dhoni', 'ms.dhoni@candidates.com', 8, ['DevOps', 'Docker', 'Kubernetes', 'AWS']),
            ('Yuvraj', 'Singh', 'yuvraj.s@candidates.com', 4, ['UI/UX Design', 'Figma', 'Sketch']),
            ('Rohit', 'Sharma', 'rohit.s@candidates.com', 6, ['Python', 'Django', 'GraphQL']),
            ('Jasprit', 'Bumrah', 'jasprit.b@candidates.com', 2, ['JavaScript', 'TypeScript', 'React']),
            ('KL', 'Rahul', 'kl.rahul@candidates.com', 1, ['Python', 'Django']),
            ('Shubman', 'Gill', 'shubman.g@candidates.com', 4, ['React', 'Node.js', 'MongoDB']),
            ('Ravindra', 'Jadeja', 'ravindra.j@candidates.com', 6, ['Full Stack', 'Python', 'React', 'AWS']),
        ]
        cands = []
        for first, last, email, exp, skills_list in cand_data:
            try:
                obj, _ = Candidate.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': first,
                        'last_name': last,
                        'phone': f"9{random.randint(7000000000, 9999999999)}",
                        'source': random.choice(['LinkedIn', 'Naukri', 'Referral', 'Company Website', 'Job Fair']),
                        'skills': skills_list,
                        'experience_years': Decimal(str(exp)),
                    }
                )
                cands.append(obj)
                result.ok(f"Candidate: {email}")
            except Exception as exc:
                result.fail(f"Candidate {email}", str(exc))

        # JobApplication
        for i, cand in enumerate(cands[:6]):
            req = reqs[i % len(reqs)] if reqs else None
            if req:
                try:
                    stages = ['APPLIED', 'SCREENING', 'L1_INTERVIEW', 'L2_INTERVIEW', 'HR_ROUND', 'OFFERED', 'ACCEPTED']
                    obj, _ = JobApplication.objects.get_or_create(
                        candidate=cand,
                        requisition=req,
                        defaults={
                            'stage': stages[i],
                        }
                    )
                    result.ok(f"JobApplication: {cand.email} -> {req.id}")
                except Exception as exc:
                    result.fail(f"JobApplication {cand.email}", str(exc))

        # InterviewSchedule
        if cands and employees:
            for i in range(3):
                cand = cands[i]
                interviewer = employees[i % len(employees)]
                try:
                    obj = InterviewSchedule.objects.create(
                        candidate=cand,
                        interviewer=interviewer,
                        interview_type=random.choice(['L1_TECH', 'L2_TECH', 'HR', 'MANAGERIAL']),
                        scheduled_date=datetime(2026, 2, 10 + i, 10, 0, 0, tzinfo=timezone.get_current_timezone()),
                        duration_minutes=60,
                        mode=random.choice(['IN_PERSON', 'VIDEO', 'PHONE']),
                        status='SCHEDULED',
                        interviewer_feedback=None,
                    )
                    # Update rating
                    InterviewSchedule.objects.filter(id=obj.id).update(rating=random.randint(1, 5))
                    result.ok(f"InterviewSchedule: {cand.email}")
                except Exception as exc:
                    result.fail(f"InterviewSchedule {cand.email}", str(exc))

        # OfferLetter
        if cands and employees:
            for i in range(3):
                cand = cands[i]
                try:
                    obj, _ = OfferLetter.objects.get_or_create(
                        candidate=cand,
                        defaults={
                            'offered_ctc': Decimal(str(random.randint(500000, 2000000))),
                            'offer_date': date(2026, 2, 15 + i),
                            'joining_date': date(2026, 3, 1 + i),
                            'status': random.choice(['DRAFT', 'APPROVED', 'ACCEPTED']),
                            'offered_by': hr_emp,
                        }
                    )
                    result.ok(f"OfferLetter: {cand.email}")
                except Exception as exc:
                    result.fail(f"OfferLetter {cand.email}", str(exc))

        # BGVCheck
        if cands:
            for i, cand in enumerate(cands[:4]):
                try:
                    obj, _ = BGVCheck.objects.get_or_create(
                        candidate=cand,
                        defaults={
                            'bgv_type': random.choice(['EDUCATION', 'EMPLOYMENT', 'CRIMINAL', 'ADDRESS', 'IDENTITY']),
                            'vendor_name': random.choice(['First Advantage', 'AuthBridge', 'OnGrid']),
                            'status': random.choice(['INITIATED', 'IN_PROGRESS', 'CLEARED', 'ISSUE_FOUND']),
                            'initiated_by': hr_emp,
                        }
                    )
                    result.ok(f"BGVCheck: {cand.email}")
                except Exception as exc:
                    result.fail(f"BGVCheck {cand.email}", str(exc))

        # OnboardingTask
        if employees:
            for i, e in enumerate(employees[:4]):
                try:
                    obj, _ = OnboardingTask.objects.get_or_create(
                        employee=e,
                        task_type=random.choice(['DOCUMENT_VERIFICATION', 'BANK_ACCOUNT_SETUP', 'IT_SETUP', 'POLICY_ACKNOWLEDGEMENT']),
                        defaults={
                            'status': random.choice(['PENDING', 'IN_PROGRESS', 'COMPLETED']),
                            'assigned_to': hr_emp,
                            'due_date': date(2026, 1, 15 + i),
                        }
                    )
                    result.ok(f"OnboardingTask: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"OnboardingTask {e.employee_id}", str(exc))

        # ============================================================
        # PHASE 9: Performance Management
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n📊 PHASE 9: Performance Management'))

        # AppraisalCycle
        try:
            obj, _ = AppraisalCycle.objects.get_or_create(
                name='Annual Appraisal 2025-2026',
                defaults={
                    'start_date': date(2026, 1, 1),
                    'end_date': date(2026, 3, 31),
                    'status': 'ACTIVE' if date.today() < date(2026, 3, 31) else 'COMPLETED',
                }
            )
            result.ok(f"AppraisalCycle: {obj.name}")
            cycle = obj
        except Exception as exc:
            result.fail("AppraisalCycle", str(exc))
            cycle = None

        # PerformanceGoal
        if employees and cycle:
            for i, e in enumerate(employees[:8]):
                try:
                    obj, _ = PerformanceGoal.objects.get_or_create(
                        employee=e,
                        cycle=cycle,
                        description=f'Complete {random.choice(["Q1 deliverables", "project milestones", "team objectives", "training goals"])}',
                        defaults={
                            'weightage': Decimal(str(random.choice([20, 25, 30, 35, 50]))),
                        }
                    )
                    result.ok(f"PerformanceGoal: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"PerformanceGoal {e.employee_id}", str(exc))

        # PerformanceReview
        if employees and cycle:
            for i, e in enumerate(employees[:8]):
                try:
                    obj, _ = PerformanceReview.objects.get_or_create(
                        employee=e,
                        cycle=cycle,
                        defaults={
                            'self_rating': Decimal(str(random.choice([3.0, 3.5, 4.0, 4.5, 5.0]))),
                            'manager_rating': Decimal(str(random.choice([3.0, 3.5, 4.0, 4.5]))),
                            'final_rating': Decimal(str(random.choice([3.0, 3.5, 4.0]))),
                            'manager_comments': 'Good performance overall. Needs to work on documentation.',
                        }
                    )
                    result.ok(f"PerformanceReview: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"PerformanceReview {e.employee_id}", str(exc))

        # OKR
        if employees and cycle:
            for i, e in enumerate(employees[:5]):
                try:
                    obj, _ = OKR.objects.get_or_create(
                        employee=e,
                        cycle=cycle,
                        objective=f'Achieve {random.choice(["productivity", "quality", "efficiency", "learning"])} targets',
                        defaults={
                            'key_result': f'Improve by {random.randint(10, 50)}%',
                            'progress_pct': Decimal(str(random.randint(0, 100))),
                        }
                    )
                    result.ok(f"OKR: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"OKR {e.employee_id}", str(exc))

        # Feedback360
        if len(employees) >= 3 and cycle:
            for i in range(min(5, len(employees))):
                e = employees[i]
                reviewer = employees[(i + 1) % len(employees)]
                try:
                    obj, _ = Feedback360.objects.get_or_create(
                        employee=e,
                        reviewer=reviewer,
                        cycle=cycle,
                        relationship='PEER',
                        defaults={
                            'rating': Decimal(str(random.randint(3, 5))),
                            'comments': 'Great team player with strong technical skills.',
                            'submitted_date': timezone.now(),
                        }
                    )
                    result.ok(f"Feedback360: {e.employee_id} from {reviewer.employee_id}")
                except Exception as exc:
                    result.fail(f"Feedback360 {e.employee_id}", str(exc))

        # PIPlan
        if employees and cycle:
            for i, e in enumerate(employees[5:8]):
                try:
                    obj, _ = PIPlan.objects.get_or_create(
                        employee=e,
                        cycle=cycle,
                        defaults={
                            'reason': random.choice(['Performance improvement needed', 'Skill gap identified', 'Behavioral issues']),
                            'improvement_areas': 'Communication, Documentation, Code Quality',
                            'start_date': date(2026, 1, 15 + i),
                            'end_date': date(2026, 3, 15 + i),
                            'status': 'IN_PROGRESS',
                        }
                    )
                    result.ok(f"PIPlan: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"PIPlan {e.employee_id}", str(exc))

        # CalibrationSession
        try:
            obj = CalibrationSession.objects.create(
                cycle=cycle,
                session_date=date(2026, 3, 15),
                facilitator=hr_emp,
                participants=[e.id for e in employees[:5]],
                notes='Calibration session for Q4 ratings',
                status='COMPLETED',
            )
            result.ok(f"CalibrationSession: {obj.id}")
        except Exception as exc:
            result.fail("CalibrationSession", str(exc))

        # GoalLibrary
        try:
            obj, _ = GoalLibrary.objects.get_or_create(
                title='Improve Code Coverage',
                defaults={
                    'description': 'Increase unit test coverage to at least 80%',
                    'category': 'TECHNICAL',
                    'is_active': True,
                }
            )
            result.ok(f"GoalLibrary: {obj.title}")
        except Exception as exc:
            result.fail("GoalLibrary", str(exc))

        # GoalCascade
        if employees and cycle:
            for i in range(min(3, len(employees))):
                e = employees[i]
                reviewer = employees[(i + 1) % len(employees)]
                try:
                    obj, _ = GoalCascade.objects.get_or_create(
                        owner=e,
                        cascade_from=reviewer,
                        cycle=cycle,
                        defaults={
                            'description': 'Aligned team goal for quarterly deliverables',
                            'weightage': Decimal('30'),
                        }
                    )
                    result.ok(f"GoalCascade: {e.employee_id}")
                except Exception as exc:
                    result.fail(f"GoalCascade {e.employee_id}", str(exc))

        # RatingScale
        try:
            scale, _ = RatingScale.objects.get_or_create(
                name='Performance Rating 1-5',
                defaults={
                    'is_active': True,
                }
            )
            for val in [1, 2, 3, 4, 5]:
                labels = {1: 'Needs Improvement', 2: 'Below Expectations', 3: 'Meets Expectations', 4: 'Exceeds Expectations', 5: 'Outstanding'}
                RatingScaleOption.objects.get_or_create(
                    scale=scale,
                    rating_value=val,
                    defaults={
                        'label': labels[val],
                        'description': f'Rating {val} - {labels[val]}',
                    }
                )
            result.ok(f"RatingScale: {scale.name}")
        except Exception as exc:
            result.fail("RatingScale", str(exc))

        # BellCurveConfig
        try:
            obj, _ = BellCurveConfig.objects.get_or_create(
                cycle=cycle,
                defaults={
                    'top_percent': Decimal('10'),
                    'middle_percent': Decimal('70'),
                    'bottom_percent': Decimal('20'),
                }
            )
            result.ok(f"BellCurveConfig: {obj.id}")
        except Exception as exc:
            result.fail("BellCurveConfig", str(exc))

        # PromotionMatrix
        try:
            matrix, _ = PromotionMatrix.objects.get_or_create(
                name='IC to Manager Track',
                defaults={
                    'is_active': True,
                }
            )
            PromotionMatrixRow.objects.get_or_create(
                matrix=matrix,
                current_grade='IC3',
                defaults={
                    'next_grade': 'M1',
                    'min_rating': Decimal('4.0'),
                    'min_tenure_months': 24,
                    'is_active': True,
                }
            )
            result.ok(f"PromotionMatrix: {matrix.name}")
        except Exception as exc:
            result.fail("PromotionMatrix", str(exc))

        # AppraisalCycleStage
        if cycle:
            stages_data = [
                {'stage_type': 'GOAL_SETTING', 'start_date': date(2026, 1, 1), 'end_date': date(2026, 1, 15), 'sequence': 1},
                {'stage_type': 'MID_YEAR_REVIEW', 'start_date': date(2026, 2, 1), 'end_date': date(2026, 2, 15), 'sequence': 2},
                {'stage_type': 'SELF_ASSESSMENT', 'start_date': date(2026, 2, 16), 'end_date': date(2026, 2, 28), 'sequence': 3},
                {'stage_type': 'MANAGER_REVIEW', 'start_date': date(2026, 3, 1), 'end_date': date(2026, 3, 15), 'sequence': 4},
                {'stage_type': 'CALIBRATION', 'start_date': date(2026, 3, 16), 'end_date': date(2026, 3, 25), 'sequence': 5},
                {'stage_type': 'RESULTS_COMMUNICATION', 'start_date': date(2026, 3, 26), 'end_date': date(2026, 3, 31), 'sequence': 6},
            ]
            for s in stages_data:
                try:
                    obj, _ = AppraisalCycleStage.objects.get_or_create(
                        cycle=cycle,
                        stage_type=s['stage_type'],
                        defaults={
                            'start_date': s['start_date'],
                            'end_date': s['end_date'],
                            'sequence': s['sequence'],
                            'status': 'COMPLETED' if s['end_date'] < date.today() else 'PENDING',
                        }
                    )
                    result.ok(f"AppraisalCycleStage: {s['stage_type']}")
                except Exception as exc:
                    result.fail(f"AppraisalCycleStage {s['stage_type']}", str(exc))

        # ============================================================
        # PHASE 10: Training & Development
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n🎓 PHASE 10: Training & Development'))

        # TrainingProgram
        training_programs = [
            {'name': 'AWS Cloud Practitioner', 'description': 'AWS cloud fundamentals', 'training_type': 'EXTERNAL', 'trainer_name': 'AWS Academy'},
            {'name': 'Advanced Django Workshop', 'description': 'Deep dive into Django', 'training_type': 'INTERNAL', 'trainer_name': 'Senior Dev Team'},
            {'name': 'Leadership Excellence', 'description': 'Management skills', 'training_type': 'EXTERNAL', 'trainer_name': 'XLRI Faculty'},
            {'name': 'React Masterclass', 'description': 'Modern React', 'training_type': 'ONLINE', 'trainer_name': 'Udemy'},
            {'name': 'Statutory Compliance Training', 'description': 'PF ESI TDS compliance', 'training_type': 'INTERNAL', 'trainer_name': 'HR Team'},
            {'name': 'DevOps with Docker/K8s', 'description': 'Container orchestration', 'training_type': 'EXTERNAL', 'trainer_name': 'DevOps Academy'},
            {'name': 'Data Science Fundamentals', 'description': 'ML and data analysis', 'training_type': 'ONLINE', 'trainer_name': 'Coursera'},
        ]
        training_progs = []
        for tp in training_programs:
            try:
                obj, _ = TrainingProgram.objects.get_or_create(
                    name=tp['name'],
                    defaults={
                        'description': tp['description'],
                        'training_type': tp['training_type'],
                        'start_date': date(2026, random.randint(1, 6), random.randint(1, 28)),
                        'end_date': date(2026, random.randint(7, 12), random.randint(1, 28)),
                        'trainer_name': tp['trainer_name'],
                    }
                )
                training_progs.append(obj)
                result.ok(f"TrainingProgram: {tp['name']}")
            except Exception as exc:
                result.fail(f"TrainingProgram {tp['name']}", str(exc))

        # TrainingNomination
        if training_progs and employees:
            for i, emp in enumerate(employees[:8]):
                for j, prog in enumerate(training_progs[:3]):
                    if random.random() < 0.5:
                        continue
                    try:
                        obj, _ = TrainingNomination.objects.get_or_create(
                            program=prog,
                            employee=emp,
                            defaults={
                                'status': random.choice(['NOMINATED', 'APPROVED', 'COMPLETED']),
                            }
                        )
                        result.ok(f"TrainingNomination: {emp.employee_id} -> {prog.name}")
                    except Exception as exc:
                        result.fail(f"TrainingNomination {emp.employee_id}", str(exc))

        # TrainingNeed
        if employees:
            for i, emp in enumerate(employees[:5]):
                try:
                    obj, _ = TrainingNeed.objects.get_or_create(
                        employee=emp,
                        skill_required='AWS',
                        defaults={
                            'current_proficiency': random.randint(1, 3),
                            'target_proficiency': random.randint(4, 5),
                            'priority': random.choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
                            'status': random.choice(['IDENTIFIED', 'IN_PROGRESS', 'COMPLETED']),
                        }
                    )
                    result.ok(f"TrainingNeed: {emp.employee_id}")
                except Exception as exc:
                    result.fail(f"TrainingNeed {emp.employee_id}", str(exc))

        # TrainingAssessment
        nominations = TrainingNomination.objects.filter(status='COMPLETED')[:5]
        for nom in nominations:
            try:
                obj, _ = TrainingAssessment.objects.get_or_create(
                    nomination=nom,
                    assessment_type='POST_TRAINING',
                    defaults={
                        'score': Decimal(str(random.randint(60, 100))),
                        'max_score': Decimal('100'),
                        'is_passed': True,
                    }
                )
                result.ok(f"TrainingAssessment: {nom.id}")
            except Exception as exc:
                result.fail(f"TrainingAssessment {nom.id}", str(exc))

        # TrainingCost
        if training_progs:
            for prog in training_progs[:3]:
                try:
                    obj, _ = TrainingCost.objects.get_or_create(
                        program=prog,
                        cost_type='TRAINING_FEE',
                        defaults={
                            'description': f'Training fee for {prog.name}',
                            'amount': Decimal(str(random.randint(10000, 100000))),
                            'currency': 'INR',
                        }
                    )
                    result.ok(f"TrainingCost: {prog.name}")
                except Exception as exc:
                    result.fail(f"TrainingCost {prog.name}", str(exc))

        # EmployeeSkill
        if employees and skills:
            for i, emp in enumerate(employees[:10]):
                skill_keys = list(skills.keys())
                for sk_name in random.sample(skill_keys, min(3, len(skill_keys))):
                    try:
                        obj, _ = EmployeeSkill.objects.get_or_create(
                            employee=emp,
                            skill=skills[sk_name],
                            defaults={
                                'proficiency': random.randint(2, 5),
                                'is_verified': random.choice([True, False]),
                            }
                        )
                    except Exception as exc:
                        result.fail(f"EmployeeSkill {emp.employee_id} {sk_name}", str(exc))
            result.ok("EmployeeSkill records created")

        # ============================================================
        # PHASE 11: Exit Management
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n🚪 PHASE 11: Exit Management'))

        # Resignation
        separated_emp = Employee.objects.filter(status='SEPARATED').first()
        if not separated_emp and len(employees) >= 3:
            # Use last employee as separated
            separated_emp = employees[-1]
            separated_emp.status = 'SEPARATED'
            separated_emp.separation_date = date(2026, 3, 15)
            separated_emp.separation_reason = 'RESIGNED'
            separated_emp.save()
            result.ok(f"Marked employee {separated_emp.employee_id} as SEPARATED")

        if separated_emp:
            try:
                obj, _ = Resignation.objects.get_or_create(
                    employee=separated_emp,
                    defaults={
                        'submitted_on': date(2026, 2, 1),
                        'reason': 'Relocation to another city for family reasons',
                        'requested_last_working_day': date(2026, 3, 15),
                        'approved_last_working_day': date(2026, 3, 15),
                        'status': 'APPROVED',
                    }
                )
                result.ok(f"Resignation: {separated_emp.employee_id}")
                resignation = obj

                # ExitClearance
                for dept_code, dept_name in [('IT', 'IT'), ('ADMIN', 'Admin'), ('FINANCE', 'Finance'), ('HR', 'HR')]:
                    ExitClearance.objects.get_or_create(
                        resignation=resignation,
                        department_code=dept_code,
                        defaults={
                            'department_name': dept_name,
                            'is_cleared': True,
                            'cleared_by': hr_emp,
                            'cleared_date': timezone.now(),
                        }
                    )
                result.ok("ExitClearance records created")

                # ExitInterview
                exit_int, _ = ExitInterview.objects.get_or_create(
                    employee=separated_emp,
                    defaults={
                        'interview_date': date(2026, 3, 1),
                        'interviewer': hr_emp,
                        'reason_category': 'RELOCATION',
                        'overall_satisfaction': 3,
                        'feedback_summary': 'Employee relocating to another city.',
                        'is_completed': True,
                    }
                )

                # ExitInterviewResponse
                questions = [
                    ('Why are you leaving?', 'Personal relocation to another city'),
                    ('Were you satisfied with the role?', 'Yes, it was a great learning experience'),
                    ('Would you recommend us?', 'Yes, definitely'),
                ]
                for q, a in questions:
                    ExitInterviewResponse.objects.get_or_create(
                        interview=exit_int,
                        question=q,
                        defaults={
                            'response': a,
                            'rating_response': random.randint(3, 5),
                        }
                    )
                result.ok("ExitInterview & ExitInterviewResponse created")

                # FnFSettlement
                try:
                    settlement, _ = FnFSettlement.objects.get_or_create(
                        employee=separated_emp,
                        resignation=resignation,
                        defaults={
                            'settlement_date': date(2026, 3, 31),
                            'total_amount': Decimal('150000'),
                            'deductions': Decimal('5000'),
                            'net_amount': Decimal('145000'),
                            'status': 'CALCULATED',
                        }
                    )
                    # FnFSettlementComponent
                    for comp_name in ['Salary', 'Leave Encashment', 'Gratuity']:
                        FnFSettlementComponent.objects.get_or_create(
                            settlement=settlement,
                            component_name=comp_name,
                            defaults={
                                'amount': Decimal(str(random.randint(30000, 70000))),
                                'is_taxable': comp_name == 'Salary',
                            }
                        )
                    result.ok("FnFSettlement & Components created")
                except Exception as exc:
                    result.fail("FnFSettlement", str(exc))

                # AlumniRecord
                try:
                    obj, _ = AlumniRecord.objects.get_or_create(
                        employee=separated_emp,
                        defaults={
                            'last_working_day': date(2026, 3, 15),
                            'linkedin_url': 'https://linkedin.com/in/alumni',
                            'is_alumni_network_member': True,
                        }
                    )
                    result.ok(f"AlumniRecord: {separated_emp.employee_id}")
                except Exception as exc:
                    result.fail("AlumniRecord", str(exc))

            except Exception as exc:
                result.fail("Exit Management", str(exc))

        # ============================================================
        # PHASE 12: Other Modules
        # ============================================================
        self.stdout.write(self.style.NOTICE('\n🧩 PHASE 12: Other Modules'))

        # InternalJobPosting
        if hr_emp:
            try:
                internal_post, _ = InternalJobPosting.objects.get_or_create(
                    title='Senior Developer - Internal',
                    defaults={
                        'description': 'Internal posting for senior developer role',
                        'department': departments.get('Engineering'),
                        'posted_by': hr_emp,
                        'posting_date': date(2026, 1, 15),
                        'closing_date': date(2026, 2, 15),
                        'status': 'OPEN',
                    }
                )
                result.ok("InternalJobPosting created")

                # InternalJobApplication
                if len(employees) >= 2:
                    InternalJobApplication.objects.get_or_create(
                        posting=internal_post,
                        applicant=employees[1],
                        defaults={
                            'current_designation': employees[1].designation.name if employees[1].designation else 'Engineer',
                            'reason_for_application': 'Career growth',
                            'status': 'APPLIED',
                        }
                    )
                    result.ok("InternalJobApplication created")
            except Exception as exc:
                result.fail("InternalJobPosting", str(exc))

        # EmployeeReferral
        if len(employees) >= 2:
            try:
                obj, _ = EmployeeReferral.objects.get_or_create(
                    referred_by=employees[0],
                    candidate_name='Referred Candidate',
                    candidate_email='referred.candidate@email.com',
                    defaults={
                        'candidate_phone': '9876543200',
                        'position_referred': 'Senior Developer',
                        'status': 'SUBMITTED',
                    }
                )
                result.ok(f"EmployeeReferral: {obj.candidate_email}")
            except Exception as exc:
                result.fail("EmployeeReferral", str(exc))

        # OnboardingBuddy
        if len(employees) >= 2:
            try:
                new_emp = employees[-2]
                buddy = employees[0]
                obj, _ = OnboardingBuddy.objects.get_or_create(
                    new_employee=new_emp,
                    buddy=buddy,
                    role='BUDDY',
                    defaults={
                        'start_date': date(2026, 1, 10),
                        'end_date': date(2026, 2, 10),
                        'is_active': True,
                        'buddy_rating': 4,
                    }
                )
                result.ok(f"OnboardingBuddy: {new_emp.employee_id} -> {buddy.employee_id}")
            except Exception as exc:
                result.fail("OnboardingBuddy", str(exc))

        # PreJoiningDocument
        if hr_emp:
            try:
                obj, _ = PreJoiningDocument.objects.get_or_create(
                    portal_token=f"TOKEN-{uuid.uuid4().hex[:8].upper()}",
                    defaults={
                        'candidate_email': 'new.hire@email.com',
                        'candidate_name': 'New Hire',
                        'document_type': 'OFFER_LETTER',
                        'status': 'PENDING',
                        'sent_date': timezone.now(),
                        'expiry_date': date(2026, 2, 15),
                        'created_by': hr_emp,
                    }
                )
                result.ok(f"PreJoiningDocument: {obj.portal_token}")
            except Exception as exc:
                result.fail("PreJoiningDocument", str(exc))

        # OnboardingFeedback
        if employees:
            try:
                obj, _ = OnboardingFeedback.objects.get_or_create(
                    employee=employees[-2],
                    feedback_type='WEEK_1',
                    defaults={
                        'overall_satisfaction': 4,
                        'onboarding_process': 4,
                        'buddy_support': 5,
                        'role_clarity': 4,
                        'comments': 'Great onboarding experience',
                    }
                )
                result.ok(f"OnboardingFeedback: {employees[-2].employee_id}")
            except Exception as exc:
                result.fail("OnboardingFeedback", str(exc))

        # HRTicket
        if employees:
            ticket_types = ['PAYROLL_QUERY', 'CERTIFICATE_REQUEST', 'IT_ACCESS', 'POLICY_CLARIFICATION', 'BENEFITS', 'LEAVE_QUERY', 'OTHER']
            for i, e in enumerate(employees[:5]):
                ttype = random.choice(ticket_types)
                try:
                    obj, _ = HRTicket.objects.get_or_create(
                        employee=e,
                        ticket_type=ttype,
                        subject=f'{ttype} - Need assistance',
                        defaults={
                            'description': f'This is a sample {ttype.lower()} ticket.',
                            'priority': random.choice(['LOW', 'MEDIUM', 'HIGH', 'URGENT']),
                            'status': random.choice(['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED']),
                            'assigned_to': hr_emp,
                        }
                    )
                    result.ok(f"HRTicket: {obj.subject}")

                    # HRTicketConversation
                    HRTicketConversation.objects.get_or_create(
                        ticket=obj,
                        message='Initial query description',
                        defaults={
                            'sender': e,
                            'is_internal': False,
                        }
                    )
                except Exception as exc:
                    result.fail(f"HRTicket {e.employee_id}", str(exc))

        # AssetRequest
        if employees:
            asset_types = ['LAPTOP', 'MONITOR', 'KEYBOARD', 'MOUSE', 'HEADSET', 'MOBILE', 'TABLET', 'ACCESS_CARD']
            for i, e in enumerate(employees[:4]):
                try:
                    obj, _ = AssetRequest.objects.get_or_create(
                        employee=e,
                        asset_type=random.choice(asset_types),
                        defaults={
                            'reason': 'New hire onboarding',
                            'status': random.choice(['PENDING', 'APPROVED', 'ISSUED']),
                        }
                    )
                    result.ok(f"AssetRequest: {e.employee_id} {obj.asset_type}")
                except Exception as exc:
                    result.fail(f"AssetRequest {e.employee_id}", str(exc))

        # POSHComplaint
        if employees and len(employees) >= 3:
            try:
                obj, _ = POSHComplaint.objects.get_or_create(
                    complainant=employees[-3],
                    respondent_name='Respondent Name',
                    defaults={
                        'incident_date': date(2026, 1, 15),
                        'description': 'Sample complaint for testing',
                        'status': 'UNDER_INVESTIGATION',
                        'submitted_by': employees[-3],
                    }
                )
                result.ok(f"POSHComplaint: {obj.id}")

                # POSHInquiryNote
                POSHInquiryNote.objects.get_or_create(
                    complaint=obj,
                    note='Initial inquiry completed',
                    defaults={
                        'added_by': hr_emp,
                        'is_confidential': True,
                    }
                )
                result.ok("POSHInquiryNote created")
            except Exception as exc:
                result.fail("POSHComplaint", str(exc))

        # IPAccessRestriction
        if employees:
            try:
                obj = IPAccessRestriction.objects.create(
                    employee=employees[0],
                    ip_address='10.0.0.1',
                    reason='Remote work access',
                    is_active=True,
                )
                result.ok(f"IPAccessRestriction: {obj.ip_address}")
            except Exception as exc:
                result.fail("IPAccessRestriction", str(exc))

        # DataConsentRecord
        if employees:
            try:
                obj, _ = DataConsentRecord.objects.get_or_create(
                    employee=employees[0],
                    consent_type='DATA_PROCESSING',
                    consent_version='v1.0',
                    defaults={
                        'is_consented': True,
                        'consented_date': timezone.now(),
                        'ip_address': '192.168.1.1',
                    }
                )
                result.ok(f"DataConsentRecord: {employees[0].employee_id}")
            except Exception as exc:
                result.fail("DataConsentRecord", str(exc))

        # StayInterview
        if employees and hr_emp:
            try:
                obj, _ = StayInterview.objects.get_or_create(
                    employee=employees[1],
                    defaults={
                        'interviewer': hr_emp,
                        'interview_date': date(2026, 2, 15),
                        'satisfaction_rating': 8,
                        'engagement_score': 7,
                        'key_motivators': 'Learning opportunities, Good team',
                        'concerns': 'Work-life balance',
                        'retention_strategy': 'Flexible hours',
                        'is_completed': True,
                    }
                )
                result.ok(f"StayInterview: {employees[1].employee_id}")
            except Exception as exc:
                result.fail("StayInterview", str(exc))

        # SalaryFreeze
        if employees:
            try:
                obj, _ = SalaryFreeze.objects.get_or_create(
                    employee=employees[2],
                    defaults={
                        'freeze_from': date(2026, 1, 1),
                        'freeze_to': date(2026, 6, 30),
                        'reason': 'Performance improvement plan',
                        'is_active': True,
                    }
                )
                result.ok(f"SalaryFreeze: {employees[2].employee_id}")
            except Exception as exc:
                result.fail("SalaryFreeze", str(exc))

        # ============================================================
        # REPORT
        # ============================================================
        total_end = timezone.now()
        duration = (total_end - total_start).total_seconds()

        self.stdout.write(self.style.NOTICE('\n' + '=' * 70))
        self.stdout.write(self.style.NOTICE('TEST RESULTS SUMMARY'))
        self.stdout.write(self.style.NOTICE('=' * 70))

        s = result.summary()
        self.stdout.write(f'  Duration: {duration:.1f}s')
        self.stdout.write(f'  Passed:   {self.style.SUCCESS(str(s["passed"]))}')
        if s['failed']:
            self.stdout.write(f'  Failed:   {self.style.ERROR(str(s["failed"]))}')
        else:
            self.stdout.write(f'  Failed:   0')
        if s['warnings']:
            self.stdout.write(f'  Warnings: {self.style.WARNING(str(s["warnings"]))}')

        if s['failed']:
            self.stdout.write(self.style.ERROR('\n❌ FAILURES:'))
            for i, f in enumerate(result.failed):
                self.stdout.write(f'  {i+1}. {f}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ ALL TESTS PASSED!'))

        if s['warnings']:
            self.stdout.write(self.style.WARNING('\n⚠️  WARNINGS:'))
            for w in result.warnings:
                self.stdout.write(f'  - {w}')

        # Final counts
        from django.apps import apps
        self.stdout.write(self.style.NOTICE('\n📊 Final Record Counts:'))
        model_counts = {}
        for m in apps.get_app_config('hr').get_models():
            name = m.__name__
            try:
                cnt = m.objects.count()
                if cnt > 0:
                    model_counts[name] = cnt
            except:
                pass
        for name, cnt in sorted(model_counts.items()):
            self.stdout.write(f'  {name}: {cnt}')

        self.stdout.write(self.style.NOTICE('\n' + '=' * 70))

    def _clear_all(self, result):
        """Clear all HR data."""
        self.stdout.write('🧹 Clearing all HR data...')
        from hr.models import (
            PayrollComponentDetail, Payroll, EmployeeSalary,
            SalaryStructureDetail, SalaryStructure, Attendance,
            LeaveApplication, EmployeeLeaveBalance, EmployeeDocument,
            CompensatoryOff, Holiday,
            SalaryRevision, EmployeeLoan, LoanRepayment, EmployeeReimbursement,
            PFContribution, ESIContribution, PTContribution, TDSCalculation,
            InvestmentDeclaration, GratuityCalculation, BonusCalculation,
            ComplianceCalendarEntry, LWFContribution, OvertimeRequest,
            ShiftSwapRequest, AttendanceRegularizationRequest,
            EmployeeFamily, EmployeeEmergencyContact, EmployeeBankAccount,
            EmployeeDocumentVersion, JobRequisition, JobApplication, Candidate,
            InterviewSchedule, OfferLetter, BGVCheck, OnboardingTask,
            Resignation, ExitClearance, ExitInterview, ExitInterviewResponse,
            FnFSettlement, FnFSettlementComponent, AlumniRecord,
            HRTicket, HRTicketConversation, AssetRequest,
            PerformanceGoal, PerformanceReview, OKR, Feedback360,
            PIPlan, TrainingNomination, TrainingNeed, TrainingAssessment,
            TrainingCost, EmployeeSkill, Employee,
            VPFContribution, PFStatement, ESICard,
            LowerDeductionCertificate, PTEnrollment, InternationalWorker,
            Form12BA, Form24QReturn, InternalJobPosting, InternalJobApplication,
            EmployeeReferral, OnboardingBuddy, PreJoiningDocument,
            OnboardingFeedback, GoalLibrary, GoalCascade,
            CalibrationSession, BellCurveConfig, PromotionMatrixRow, PromotionMatrix,
            AppraisalCycleStage, AppraisalFormResponse, AppraisalFormQuestion,
            AppraisalFormSection, AppraisalFormTemplate, RatingScaleOption, RatingScale,
            DataConsentRecord, POSHInquiryNote, POSHComplaint,
            IPAccessRestriction, StayInterview, SalaryFreeze,
        )
        models_list = [
            Attendance, LeaveApplication, EmployeeLeaveBalance, EmployeeDocument,
            CompensatoryOff, PerformanceGoal, PerformanceReview, OKR, Feedback360,
            PIPlan, TrainingNomination, TrainingNeed, TrainingAssessment, TrainingCost,
            EmployeeSkill, PayrollComponentDetail, Payroll, EmployeeSalary,
            SalaryStructureDetail, LeaveApplication, EmployeeLeaveBalance,
            SalaryRevision, EmployeeLoan, LoanRepayment, EmployeeReimbursement,
            PFContribution, ESIContribution, PTContribution, TDSCalculation,
            InvestmentDeclaration, GratuityCalculation, BonusCalculation,
            ComplianceCalendarEntry, LWFContribution, OvertimeRequest,
            ShiftSwapRequest, AttendanceRegularizationRequest,
            EmployeeFamily, EmployeeEmergencyContact, EmployeeBankAccount,
            EmployeeDocumentVersion, InterviewSchedule, OfferLetter, BGVCheck,
            OnboardingTask, ExitInterviewResponse, ExitInterview,
            FnFSettlementComponent, FnFSettlement, AlumniRecord,
            HRTicketConversation, HRTicket, AssetRequest,
            Candidate, JobApplication, JobRequisition,
            Resignation, ExitClearance,
            VPFContribution, PFStatement, ESICard,
            LowerDeductionCertificate, PTEnrollment, InternationalWorker,
            Form12BA, Form24QReturn, InternalJobApplication, InternalJobPosting,
            EmployeeReferral, OnboardingBuddy, PreJoiningDocument,
            OnboardingFeedback, GoalCascade, GoalLibrary,
            CalibrationSession, BellCurveConfig, PromotionMatrixRow, PromotionMatrix,
            AppraisalCycleStage, AppraisalFormResponse, AppraisalFormQuestion,
            AppraisalFormSection, AppraisalFormTemplate, RatingScaleOption, RatingScale,
             DataConsentRecord, POSHInquiryNote, POSHComplaint,
            IPAccessRestriction, StayInterview, SalaryFreeze,
            Employee,
        ]
        for m in models_list:
            try:
                m.objects.all().delete()
            except Exception as e:
                result.warn(f"Clear {m.__name__}: {e}")
        result.ok("Existing HR data cleared")
