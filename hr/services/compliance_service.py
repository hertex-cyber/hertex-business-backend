"""
Statutory Compliance Service — PF ECR, ESI Returns, PT Challans, Gratuity, Bonus

Handles:
- PF ECR generation (EPFO ECR format)
- ESI return generation
- Professional Tax challan calculation per state
- LWF computation
- Bonus calculation under Payment of Bonus Act
- Gratuity calculation under Payment of Gratuity Act
- Compliance calendar auto-population with alerts
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Tuple

from django.db import transaction
from django.db.models import Sum, Q

from hr.models import (
    Employee, EmployeeSalary, Payroll, PayrollComponentDetail, SalaryComponent,
    PFConfiguration, PFContribution, ESIConfiguration, ESIContribution,
    ProfessionalTaxSlab, PTContribution,
    TDSConfiguration, TDSCalculation, InvestmentDeclaration,
    GratuityConfiguration, GratuityCalculation,
    BonusConfiguration, BonusCalculation,
    ComplianceCalendarEntry,
    Attendance
)


def get_financial_year(target_date: date = None) -> str:
    if target_date is None:
        target_date = date.today()
    if target_date.month >= 4:
        return f"{target_date.year}-{target_date.year + 1}"
    return f"{target_date.year - 1}-{target_date.year}"


class PFComplianceService:
    """Provident Fund compliance calculation and ECR generation."""

    def __init__(self, month: int, year: int):
        self.month = month
        self.year = year
        self.config = PFConfiguration.objects.filter(is_active=True).order_by('-effective_from').first()

    def calculate_pf(self, employee: Employee, basic_da: Decimal, gross_salary: Decimal) -> dict:
        """Calculate PF contributions for a single employee."""
        if not self.config:
            return self._zero_pf()

        # Check eligibility: basic+DA <= wage ceiling
        wage = min(basic_da, self.config.wage_ceiling)

        employee_pf = (wage * self.config.employee_contribution_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        employer_epf = (wage * self.config.employer_epf_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # EPS capped at pensionable salary
        eps_wage = min(wage, self.config.eps_max_pensionable_salary)
        employer_eps = (eps_wage * self.config.employer_eps_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        employer_edli = (wage * self.config.employer_edli_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        employer_admin = (wage * self.config.employer_admin_charges_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        edli_admin = (wage * self.config.edli_admin_charges_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Adjust EPF so that EPF + EPS + EDLI = employer total
        total_employer = employer_epf + employer_eps + employer_edli + employer_admin + edli_admin

        return {
            'employee_pf': employee_pf,
            'employer_epf': employer_epf,
            'employer_eps': employer_eps,
            'employer_edli': employer_edli,
            'employer_admin_charges': employer_admin,
            'edli_admin_charges': edli_admin,
            'total_employee': employee_pf,
            'total_employer': total_employer,
            'basic_da': wage,
            'uan': employee.pan_number or '',  # UAN would be stored on employee
        }

    def _zero_pf(self) -> dict:
        return {
            'employee_pf': Decimal('0'), 'employer_epf': Decimal('0'),
            'employer_eps': Decimal('0'), 'employer_edli': Decimal('0'),
            'employer_admin_charges': Decimal('0'), 'edli_admin_charges': Decimal('0'),
            'total_employee': Decimal('0'), 'total_employer': Decimal('0'),
            'basic_da': Decimal('0'), 'uan': '',
        }

    @transaction.atomic
    def process_all(self) -> dict:
        """Process PF for all eligible employees."""
        processed = 0
        errors = []

        payrolls = Payroll.objects.filter(month=self.month, year=self.year, status__in=['PROCESSED', 'APPROVED', 'PAID'])
        for payroll in payrolls.select_related('employee'):
            try:
                basic_da = PayrollComponentDetail.objects.filter(
                    payroll=payroll,
                    component__code__in=['BASIC', 'BASIC_DA', 'BASIC_SALARY']
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

                result = self.calculate_pf(payroll.employee, basic_da, payroll.gross_salary)

                PFContribution.objects.update_or_create(
                    employee=payroll.employee,
                    month=self.month,
                    year=self.year,
                    defaults={
                        'payroll': payroll,
                        'basic_da': result['basic_da'],
                        'gross_salary': payroll.gross_salary,
                        'employee_pf': result['employee_pf'],
                        'employer_epf': result['employer_epf'],
                        'employer_eps': result['employer_eps'],
                        'employer_edli': result['employer_edli'],
                        'employer_admin_charges': result['employer_admin_charges'],
                        'edli_admin_charges': result['edli_admin_charges'],
                        'total_employee_contribution': result['total_employee'],
                        'total_employer_contribution': result['total_employer'],
                    }
                )
                processed += 1
            except Exception as e:
                errors.append({'employee_id': str(payroll.employee.id), 'error': str(e)})

        return {'processed': processed, 'errors': errors, 'month': self.month, 'year': self.year}

    def generate_ecr_data(self) -> dict:
        """Generate ECR data in EPFO-compatible format."""
        contributions = PFContribution.objects.filter(month=self.month, year=self.year).select_related('employee')
        rows = []
        for c in contributions:
            emp = c.employee
            rows.append({
                'employee_id': emp.employee_id,
                'uan': c.uan or emp.aadhaar_number or '',
                'name': emp.get_full_name(),
                'basic_da': float(c.basic_da),
                'employee_pf': float(c.employee_pf),
                'employer_epf': float(c.employer_epf),
                'employer_eps': float(c.employer_eps),
                'employer_edli': float(c.employer_edli),
                'employer_admin': float(c.employer_admin_charges),
                'edli_admin': float(c.edli_admin_charges),
                'total_employee': float(c.total_employee_contribution),
                'total_employer': float(c.total_employer_contribution),
            })
        totals = contributions.aggregate(
            total_employee=Sum('total_employee_contribution'),
            total_employer=Sum('total_employer_contribution'),
            member_count=Sum('id'),
        )
        return {
            'month': self.month,
            'year': self.year,
            'establishment': {
                'est_code': 'YOUR_EST_CODE',
                'est_name': 'ByteHive Technologies',
            },
            'members': rows,
            'summary': {
                'total_members': contributions.count(),
                'total_employee_contribution': float(totals['total_employee'] or 0),
                'total_employer_contribution': float(totals['total_employer'] or 0),
                'grand_total': float((totals['total_employee'] or 0) + (totals['total_employer'] or 0)),
            }
        }


class ESIComplianceService:
    """ESI compliance calculation."""

    def __init__(self, month: int, year: int):
        self.month = month
        self.year = year
        self.config = ESIConfiguration.objects.filter(is_active=True).order_by('-effective_from').first()

    def calculate_esi(self, employee: Employee, gross_salary: Decimal) -> dict:
        """Calculate ESI contributions."""
        if not self.config or gross_salary > self.config.wage_ceiling:
            return {'employee_contribution': Decimal('0'), 'employer_contribution': Decimal('0'),
                    'total': Decimal('0'), 'is_eligible': False}

        emp_contrib = (gross_salary * self.config.employee_contribution_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        employer_contrib = (gross_salary * self.config.employer_contribution_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = emp_contrib + employer_contrib

        return {
            'employee_contribution': emp_contrib,
            'employer_contribution': employer_contrib,
            'total': total,
            'is_eligible': True,
        }

    @transaction.atomic
    def process_all(self) -> dict:
        """Process ESI for all eligible employees."""
        processed = 0
        errors = []
        payrolls = Payroll.objects.filter(month=self.month, year=self.year, status__in=['PROCESSED', 'APPROVED', 'PAID'])
        for payroll in payrolls.select_related('employee'):
            try:
                result = self.calculate_esi(payroll.employee, payroll.gross_salary)
                if result['is_eligible']:
                    ESIContribution.objects.update_or_create(
                        employee=payroll.employee,
                        month=self.month,
                        year=self.year,
                        defaults={
                            'payroll': payroll,
                            'gross_salary': payroll.gross_salary,
                            'employee_contribution': result['employee_contribution'],
                            'employer_contribution': result['employer_contribution'],
                            'total_contribution': result['total'],
                        }
                    )
                    processed += 1
            except Exception as e:
                errors.append({'employee_id': str(payroll.employee.id), 'error': str(e)})
        return {'processed': processed, 'errors': errors}


class PTComplianceService:
    """Professional Tax compliance per state."""

    def __init__(self, month: int, year: int):
        self.month = month
        self.year = year

    def calculate_pt(self, employee: Employee, gross_salary: Decimal) -> Decimal:
        """Calculate Professional Tax based on state slabs."""
        state = (employee.work_location.state if employee.work_location else 'Karnataka')

        slab = ProfessionalTaxSlab.objects.filter(
            state__iexact=state,
            salary_from__lte=gross_salary,
            is_active=True,
        ).filter(
            Q(salary_to__gte=gross_salary) | Q(salary_to__isnull=True)
        ).order_by('-salary_from').first()

        if slab:
            return slab.tax_amount
        return Decimal('0')

    @transaction.atomic
    def process_all(self) -> dict:
        """Process PT for all employees."""
        processed = 0
        payrolls = Payroll.objects.filter(month=self.month, year=self.year, status__in=['PROCESSED', 'APPROVED', 'PAID'])
        for payroll in payrolls.select_related('employee'):
            pt_amount = self.calculate_pt(payroll.employee, payroll.gross_salary)
            if pt_amount > 0:
                state = payroll.employee.work_location.state if payroll.employee.work_location else 'Karnataka'
                PTContribution.objects.update_or_create(
                    employee=payroll.employee,
                    month=self.month,
                    year=self.year,
                    defaults={
                        'payroll': payroll,
                        'gross_salary': payroll.gross_salary,
                        'pt_amount': pt_amount,
                        'state': state,
                    }
                )
                processed += 1
        return {'processed': processed}


class GratuityComplianceService:
    """Gratuity calculation and monthly provisioning."""

    def calculate_gratuity(self, employee: Employee, exit_date: date = None) -> dict:
        """Calculate gratuity for an employee."""
        config = GratuityConfiguration.objects.filter(is_active=True).order_by('-effective_from').first()
        if not config:
            return {'amount': Decimal('0'), 'eligible': False, 'years': 0}

        end_date = exit_date or date.today()
        doj = employee.date_of_joining
        years_served = (end_date - doj).days / 365.25

        if years_served < config.min_service_years:
            return {'amount': Decimal('0'), 'eligible': False, 'years': years_served}

        salary = EmployeeSalary.objects.filter(employee=employee, is_active=True).order_by('-effective_from').first()
        if not salary:
            return {'amount': Decimal('0'), 'eligible': False, 'years': years_served}

        # Gratuity = (Last drawn Basic+DA) * (15/26) * Years of service
        basic_da = salary.basic_salary
        amount = (basic_da * Decimal(str(config.formula_numerator)) / Decimal(str(config.formula_denominator))) * \
                 Decimal(str(round(years_served)))
        monthly_provision = amount / Decimal(str(round(years_served * 12))) if years_served > 0 else Decimal('0')

        return {
            'amount': amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'monthly_provision': monthly_provision.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'eligible': True,
            'years': round(years_served, 2),
        }

    def provision_all(self) -> dict:
        """Monthly gratuity provisioning for all eligible employees."""
        processed = 0
        active_employees = Employee.objects.filter(status__in=['ACTIVE', 'ONBOARDING', 'ON_LEAVE'])
        for emp in active_employees:
            result = self.calculate_gratuity(emp)
            if result['eligible']:
                GratuityCalculation.objects.update_or_create(
                    employee=emp,
                    defaults={
                        'date_of_joining': emp.date_of_joining,
                        'date_of_exit': date.today(),
                        'years_of_service': result['years'],
                        'is_eligible': True,
                        'last_drawn_basic_da': EmployeeSalary.objects.filter(
                            employee=emp, is_active=True
                        ).order_by('-effective_from').first().basic_salary,
                        'gratuity_amount': result['amount'],
                        'monthly_provision_amount': result['monthly_provision'],
                    }
                )
                processed += 1
        return {'provisioned': processed}


class BonusComplianceService:
    """Bonus calculation under Payment of Bonus Act."""

    def calculate_bonus(self, employee: Employee, financial_year: str) -> dict:
        """Calculate annual bonus."""
        config = BonusConfiguration.objects.filter(financial_year=financial_year, is_active=True).first()
        if not config:
            return {'amount': Decimal('0'), 'eligible': False}

        salary = EmployeeSalary.objects.filter(employee=employee, is_active=True).order_by('-effective_from').first()
        if not salary or salary.gross_salary > config.wage_ceiling:
            return {'amount': Decimal('0'), 'eligible': False}

        # Minimum bonus: 8.33% of eligible salary
        bonus_pct = max(config.minimum_bonus_pct, min(config.maximum_bonus_pct, Decimal('8.33')))
        bonus_amount = (salary.gross_salary * bonus_pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'amount': bonus_amount,
            'percentage': bonus_pct,
            'eligible': True,
        }

    @transaction.atomic
    def process_all(self, financial_year: str) -> dict:
        """Process bonus for all eligible employees."""
        processed = 0
        active_employees = Employee.objects.filter(status='ACTIVE')
        for emp in active_employees:
            result = self.calculate_bonus(emp, financial_year)
            if result['eligible']:
                BonusCalculation.objects.update_or_create(
                    employee=emp,
                    financial_year=financial_year,
                    defaults={
                        'eligible_salary': EmployeeSalary.objects.filter(
                            employee=emp, is_active=True
                        ).order_by('-effective_from').first().gross_salary,
                        'bonus_percentage': result['percentage'],
                        'bonus_amount': result['amount'],
                    }
                )
                processed += 1
        return {'processed': processed}


class ComplianceCalendarService:
    """Compliance calendar auto-population with alerts."""

    COMPLIANCE_EVENTS = {
        'PF': {
            'title': 'PF ECR Filing',
            'description': 'Monthly PF ECR filing - due date 15th of next month',
            'frequency': 'MONTHLY',
            'due_day': 15,
        },
        'PF_CHALLAN': {
            'title': 'PF Challan Payment',
            'description': 'Monthly PF contribution payment - due date 15th of next month',
            'frequency': 'MONTHLY',
            'due_day': 15,
        },
        'ESI': {
            'title': 'ESI Return Filing',
            'description': 'Half-yearly ESI return filing',
            'frequency': 'HALF_YEARLY',
            'months': [4, 10],  # April and October
        },
        'ESI_CHALLAN': {
            'title': 'ESI Challan Payment',
            'description': 'Monthly ESI contribution payment - due date 15th of next month',
            'frequency': 'MONTHLY',
            'due_day': 15,
        },
        'PT': {
            'title': 'Professional Tax Challan',
            'description': 'Monthly Professional Tax payment - due date 15th of next month',
            'frequency': 'MONTHLY',
            'due_day': 15,
        },
        'TDS': {
            'title': 'TDS Return Filing (Q1/Q2/Q3/Q4)',
            'description': 'Quarterly TDS return filing - Form 24Q',
            'frequency': 'QUARTERLY',
            'due_dates': {
                'Q1': (7, 31),  # Jul 31
                'Q2': (10, 31),  # Oct 31
                'Q3': (1, 31),   # Jan 31
                'Q4': (5, 31),   # May 31
            }
        },
        'LWF': {
            'title': 'Labour Welfare Fund',
            'description': 'LWF contribution filing - varies by state',
            'frequency': 'HALF_YEARLY',
            'months': [6, 12],
        },
        'FORM_16': {
            'title': 'Form 16 Issuance Deadline',
            'description': 'Issue Form 16 to all employees',
            'frequency': 'ANNUAL',
            'due_month': 6,  # June
            'due_day': 15,
        },
    }

    @transaction.atomic
    def populate_calendar(self, year: int) -> list:
        """Auto-populate compliance calendar for a given year."""
        entries = []
        for comp_type, config_data in self.COMPLIANCE_EVENTS.items():
            if config_data['frequency'] == 'MONTHLY':
                for month in range(1, 13):
                    due_date = date(year, month, config_data['due_day'])
                    month_end = date(year, month, 1) + timedelta(days=32)
                    month_end = month_end.replace(day=1) - timedelta(days=1)
                    self._create_entry(comp_type, f"{config_data['title']} - {date(year, month, 1).strftime('%B %Y')}",
                                       config_data['description'], due_date, 'MONTHLY', year)
            elif config_data['frequency'] == 'QUARTERLY':
                quarters = {'Q1': (7, 31), 'Q2': (10, 31), 'Q3': (1, 31), 'Q4': (5, 31)}
                for q, (m, d) in quarters.items():
                    due_date = date(year, m, d)
                    self._create_entry(comp_type, f"{config_data['title'].replace('Q1/Q2/Q3/Q4', q)} - {year}",
                                       config_data['description'], due_date, 'QUARTERLY', year)
            elif config_data['frequency'] == 'HALF_YEARLY':
                for month in config_data.get('months', []):
                    due_date = date(year, month, 15)
                    period = f"Jan-Jun {year}" if month == 6 else f"Jul-Dec {year}"
                    self._create_entry(comp_type, f"{config_data['title']} - {period}",
                                       config_data['description'], due_date, 'HALF_YEARLY', year)
            elif config_data['frequency'] == 'ANNUAL':
                due_date = date(year, config_data.get('due_month', 6), config_data.get('due_day', 15))
                self._create_entry(comp_type, f"{config_data['title']} - FY {year-1}-{year}",
                                   config_data['description'], due_date, 'ANNUAL', year)
            entries.append(comp_type)
        return entries

    def _create_entry(self, comp_type, title, description, due_date, frequency, year):
        ComplianceCalendarEntry.objects.get_or_create(
            compliance_type=comp_type.split('_')[0] if '_' in comp_type else comp_type,
            title=title,
            due_date=due_date,
            defaults={
                'description': description,
                'frequency': frequency,
                'period_year': year,
                'status': 'PENDING',
            }
        )

    def get_upcoming_alerts(self, days: int = 15) -> list:
        """Get upcoming compliance alerts."""
        from datetime import date, timedelta
        today = date.today()
        cutoff = today + timedelta(days=days)
        events = ComplianceCalendarEntry.objects.filter(
            due_date__gte=today,
            due_date__lte=cutoff,
            status='PENDING',
        ).order_by('due_date')
        return [
            {
                'id': str(e.id),
                'type': e.compliance_type,
                'title': e.title,
                'due_date': e.due_date,
                'days_remaining': (e.due_date - today).days,
            }
            for e in events
        ]

    def get_overdue(self) -> list:
        """Get overdue compliance items."""
        today = date.today()
        events = ComplianceCalendarEntry.objects.filter(
            due_date__lt=today,
            status='PENDING',
        ).order_by('due_date')
        return [
            {
                'id': str(e.id),
                'type': e.compliance_type,
                'title': e.title,
                'due_date': e.due_date,
                'days_overdue': (today - e.due_date).days,
            }
            for e in events
        ]
