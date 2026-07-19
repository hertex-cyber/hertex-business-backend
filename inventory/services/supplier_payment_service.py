"""
Supplier Payment Service — handles payment workflow, invoice allocation,
outstanding balance tracking, history logging, and notifications.

Workflow:
  DRAFT -> submit() -> PENDING_APPROVAL -> approve() -> APPROVED
                                        -> post() -> POSTED -> complete() -> COMPLETED
  DRAFT/PENDING_APPROVAL -> cancel() -> CANCELLED
  APPROVED/POSTED/COMPLETED -> void() -> VOIDED

Rules:
  - Allocated amount cannot exceed invoice outstanding balance.
  - Total allocated amount cannot exceed payment total_amount.
  - Posting updates invoice outstanding balances.
  - Completing marks invoice payment status (PARTIALLY_PAID/PAID).
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from inventory.models import (
    InventorySupplierPayment, InventorySupplierPaymentAllocation,
    InventorySupplierPaymentHistory, InventorySupplierPaymentAttachment,
    InventorySupplierInvoice,
)
from inventory.services.notification_service import InventoryNotificationService


def _log_history(payment, action, from_status, to_status, user, remarks=''):
    InventorySupplierPaymentHistory.objects.create(
        payment=payment,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def _update_invoice_payment_status(invoice):
    """Update an invoice's payment_status/status based on its allocations."""
    total_allocated = InventorySupplierPaymentAllocation.objects.filter(
        supplier_invoice=invoice,
        payment__status__in=['APPROVED', 'POSTED', 'COMPLETED'],
    ).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0')

    old_payment_status = invoice.payment_status
    if total_allocated >= invoice.grand_total:
        invoice.payment_status = 'PAID'
        if invoice.status not in ('CANCELLED', 'VOIDED'):
            invoice.status = 'PAID'
    elif total_allocated > 0:
        invoice.payment_status = 'PARTIALLY_PAID'
        if invoice.status not in ('CANCELLED', 'VOIDED', 'PAID'):
            invoice.status = 'PARTIALLY_PAID'
    else:
        invoice.payment_status = 'UNPAID'

    invoice.outstanding_amount = (invoice.grand_total - total_allocated).quantize(Decimal('0.0001'))
    invoice.save(update_fields=['payment_status', 'status', 'outstanding_amount'])


def _update_payment_allocated_amounts(payment):
    """Recalculate allocated/unallocated amounts for a payment."""
    total_alloc = InventorySupplierPaymentAllocation.objects.filter(
        payment=payment
    ).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0')

    payment.allocated_amount = total_alloc
    payment.unallocated_amount = (payment.total_amount - total_alloc).quantize(Decimal('0.0001'))
    payment.save(update_fields=['allocated_amount', 'unallocated_amount'])


@transaction.atomic
def create_payment(data, user=None):
    tenant_id = data.get('tenant_id')
    if not tenant_id:
        raise ValueError("tenant_id is required.")

    payment = InventorySupplierPayment.objects.create(
        tenant_id=tenant_id,
        payment_number=data.get('payment_number', ''),
        payment_date=data.get('payment_date', timezone.now().date()),
        supplier_id=data.get('supplier'),
        supplier_name=data.get('supplier_name', ''),
        payment_method=data.get('payment_method', 'Bank Transfer'),
        bank_account=data.get('bank_account', ''),
        reference_number=data.get('reference_number', ''),
        currency=data.get('currency', 'INR'),
        exchange_rate=Decimal(str(data.get('exchange_rate', 1))),
        total_amount=Decimal(str(data.get('total_amount', 0))),
        allocated_amount=0,
        unallocated_amount=Decimal(str(data.get('total_amount', 0))),
        status='DRAFT',
        remarks=data.get('remarks', ''),
        created_by=user,
        updated_by=user,
    )

    # Create allocations if provided
    allocations = data.get('allocations', [])
    total_allocated = Decimal('0')
    for alloc in allocations:
        invoice_id = alloc.get('supplier_invoice')
        amount = Decimal(str(alloc.get('allocated_amount', 0)))
        if amount <= 0:
            continue
        invoice = InventorySupplierInvoice.objects.get(id=invoice_id)
        avail = invoice.outstanding_amount
        if amount > avail:
            raise ValueError(
                f"Allocation {amount} exceeds outstanding {avail} for invoice {invoice.invoice_number}"
            )
        InventorySupplierPaymentAllocation.objects.create(
            payment=payment,
            supplier_invoice=invoice,
            allocated_amount=amount,
            remarks=alloc.get('remarks', ''),
        )
        total_allocated += amount

    if total_allocated > payment.total_amount:
        raise ValueError(f"Total allocation {total_allocated} exceeds payment amount {payment.total_amount}")

    _update_payment_allocated_amounts(payment)
    _log_history(payment, 'CREATED', '', 'DRAFT', user)
    InventoryNotificationService.notify_supplier_payment_event('created', payment)
    return payment


@transaction.atomic
def update_payment(payment, data, user=None):
    if payment.status != 'DRAFT':
        raise ValueError("Only draft payments can be edited.")

    for field in ['payment_date', 'supplier', 'supplier_name', 'payment_method',
                  'bank_account', 'reference_number', 'currency', 'exchange_rate',
                  'total_amount', 'remarks']:
        if field in data:
            setattr(payment, field, data[field])

    payment.updated_by = user
    payment.save()

    # Re-create allocations if provided
    if 'allocations' in data:
        payment.allocations.all().delete()
        total_allocated = Decimal('0')
        for alloc in data['allocations']:
            invoice_id = alloc.get('supplier_invoice')
            amount = Decimal(str(alloc.get('allocated_amount', 0)))
            if amount <= 0:
                continue
            invoice = InventorySupplierInvoice.objects.get(id=invoice_id)
            avail = invoice.outstanding_amount
            if amount > avail:
                raise ValueError(
                    f"Allocation {amount} exceeds outstanding {avail} for invoice {invoice.invoice_number}"
                )
            InventorySupplierPaymentAllocation.objects.create(
                payment=payment,
                supplier_invoice=invoice,
                allocated_amount=amount,
                remarks=alloc.get('remarks', ''),
            )
            total_allocated += amount

        if total_allocated > payment.total_amount:
            raise ValueError(f"Total allocation {total_allocated} exceeds payment amount {payment.total_amount}")

    _update_payment_allocated_amounts(payment)
    _log_history(payment, 'UPDATED', 'DRAFT', 'DRAFT', user)
    return payment


@transaction.atomic
def submit_payment(payment, user=None):
    if payment.status != 'DRAFT':
        raise ValueError("Only draft payments can be submitted.")
    payment.status = 'PENDING_APPROVAL'
    payment.updated_by = user
    payment.save(update_fields=['status', 'updated_by'])
    _log_history(payment, 'SUBMITTED', 'DRAFT', 'PENDING_APPROVAL', user)
    InventoryNotificationService.notify_supplier_payment_event('submitted', payment)
    return payment


@transaction.atomic
def approve_payment(payment, user=None, notes=''):
    if payment.status != 'PENDING_APPROVAL':
        raise ValueError("Only pending approval payments can be approved.")
    payment.status = 'APPROVED'
    payment.approved_by = user
    payment.approved_at = timezone.now()
    payment.approval_notes = notes
    payment.updated_by = user
    payment.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_notes', 'updated_by'])
    _log_history(payment, 'APPROVED', 'PENDING_APPROVAL', 'APPROVED', user, notes)
    InventoryNotificationService.notify_supplier_payment_event('approved', payment)
    return payment


@transaction.atomic
def post_payment(payment, user=None):
    """
    Post the payment — updates invoice outstanding balances and payment statuses.
    """
    if payment.status != 'APPROVED':
        raise ValueError("Only approved payments can be posted.")

    payment.status = 'POSTED'
    payment.posted_by = user
    payment.posted_at = timezone.now()
    payment.updated_by = user
    payment.save(update_fields=['status', 'posted_by', 'posted_at', 'updated_by'])

    # Update all allocated invoices
    for alloc in payment.allocations.select_related('supplier_invoice'):
        _update_invoice_payment_status(alloc.supplier_invoice)

    _log_history(payment, 'POSTED', 'APPROVED', 'POSTED', user)
    InventoryNotificationService.notify_supplier_payment_event('posted', payment)
    return payment


@transaction.atomic
def complete_payment(payment, user=None):
    if payment.status != 'POSTED':
        raise ValueError("Only posted payments can be completed.")
    payment.status = 'COMPLETED'
    payment.completed_by = user
    payment.completed_at = timezone.now()
    payment.updated_by = user
    payment.save(update_fields=['status', 'completed_by', 'completed_at', 'updated_by'])

    # Finalize invoice statuses
    for alloc in payment.allocations.select_related('supplier_invoice'):
        _update_invoice_payment_status(alloc.supplier_invoice)

    _log_history(payment, 'COMPLETED', 'POSTED', 'COMPLETED', user)
    InventoryNotificationService.notify_supplier_payment_event('completed', payment)
    return payment


@transaction.atomic
def allocate_payment(payment, allocations, user=None):
    """
    Add/replace allocations on an existing payment (DRAFT or PENDING_APPROVAL only).
    """
    if payment.status not in ('DRAFT', 'PENDING_APPROVAL'):
        raise ValueError("Only draft or pending approval payments can be allocated.")

    payment.allocations.all().delete()
    total_allocated = Decimal('0')
    for alloc in allocations:
        invoice_id = alloc.get('supplier_invoice')
        amount = Decimal(str(alloc.get('allocated_amount', 0)))
        if amount <= 0:
            continue
        invoice = InventorySupplierInvoice.objects.get(id=invoice_id)
        avail = invoice.outstanding_amount
        if amount > avail:
            raise ValueError(
                f"Allocation {amount} exceeds outstanding {avail} for invoice {invoice.invoice_number}"
            )
        InventorySupplierPaymentAllocation.objects.create(
            payment=payment,
            supplier_invoice=invoice,
            allocated_amount=amount,
            remarks=alloc.get('remarks', ''),
        )
        total_allocated += amount

    if total_allocated > payment.total_amount:
        raise ValueError(f"Total allocation {total_allocated} exceeds payment amount {payment.total_amount}")

    _update_payment_allocated_amounts(payment)
    _log_history(payment, 'UPDATED', payment.status, payment.status, user, 'Allocations updated')
    return payment


@transaction.atomic
def cancel_payment(payment, user=None, remarks=''):
    if payment.status not in ('DRAFT', 'PENDING_APPROVAL'):
        raise ValueError("Only draft or pending approval payments can be cancelled.")
    old_status = payment.status
    payment.status = 'CANCELLED'
    payment.updated_by = user
    payment.remarks = (payment.remarks or '') + f"\nCancelled: {remarks}".strip()
    payment.save(update_fields=['status', 'updated_by', 'remarks'])
    _log_history(payment, 'CANCELLED', old_status, 'CANCELLED', user, remarks)
    InventoryNotificationService.notify_supplier_payment_event('cancelled', payment)
    return payment


@transaction.atomic
def void_payment(payment, user=None, remarks=''):
    if payment.status not in ('APPROVED', 'POSTED', 'COMPLETED'):
        raise ValueError("Only approved, posted, or completed payments can be voided.")

    old_status = payment.status
    payment.status = 'VOIDED'
    payment.updated_by = user
    payment.remarks = (payment.remarks or '') + f"\nVoided: {remarks}".strip()
    payment.save(update_fields=['status', 'updated_by', 'remarks'])

    # Reverse invoice payment statuses
    for alloc in payment.allocations.select_related('supplier_invoice'):
        _update_invoice_payment_status(alloc.supplier_invoice)

    _log_history(payment, 'VOIDED', old_status, 'VOIDED', user, remarks)
    InventoryNotificationService.notify_supplier_payment_event('voided', payment)
    return payment


def get_history(payment):
    return payment.history.select_related('performed_by').order_by('-timestamp')


# ===========================================================================
# REPORTS
# ===========================================================================

def get_payment_register(tenant_id, filters=None):
    """Supplier Payment Register — list all payments with optional filters."""
    qs = InventorySupplierPayment.objects.filter(tenant_id=tenant_id)
    if filters:
        if filters.get('supplier'):
            qs = qs.filter(supplier_id=filters['supplier'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('payment_method'):
            qs = qs.filter(payment_method=filters['payment_method'])
        if filters.get('date_from'):
            qs = qs.filter(payment_date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(payment_date__lte=filters['date_to'])
    return qs.order_by('-payment_date')


def get_outstanding_payables(tenant_id, supplier_id=None):
    """Outstanding payables — all POSTED/PAID invoices with outstanding > 0."""
    qs = InventorySupplierInvoice.objects.filter(
        tenant_id=tenant_id,
        outstanding_amount__gt=0,
        status__in=['POSTED', 'PARTIALLY_PAID'],
    )
    if supplier_id:
        qs = qs.filter(supplier_id=supplier_id)
    return qs.order_by('due_date', 'invoice_date')


def get_payment_allocation_report(tenant_id, payment_id=None, invoice_id=None):
    """Payment allocation report."""
    qs = InventorySupplierPaymentAllocation.objects.filter(
        payment__tenant_id=tenant_id,
    ).select_related('payment', 'supplier_invoice')
    if payment_id:
        qs = qs.filter(payment_id=payment_id)
    if invoice_id:
        qs = qs.filter(supplier_invoice_id=invoice_id)
    return qs.order_by('-payment__payment_date')


def get_supplier_statement(tenant_id, supplier_id, date_from=None, date_to=None):
    """Supplier statement — invoices and payments for a supplier."""
    invoices = InventorySupplierInvoice.objects.filter(
        tenant_id=tenant_id, supplier_id=supplier_id,
    )
    payments = InventorySupplierPayment.objects.filter(
        tenant_id=tenant_id, supplier_id=supplier_id,
        status__in=['POSTED', 'COMPLETED'],
    )
    if date_from:
        invoices = invoices.filter(invoice_date__gte=date_from)
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        invoices = invoices.filter(invoice_date__lte=date_to)
        payments = payments.filter(payment_date__lte=date_to)

    transactions = []
    for inv in invoices:
        transactions.append({
            'date': inv.invoice_date,
            'type': 'INVOICE',
            'reference': inv.invoice_number,
            'debit': inv.grand_total,
            'credit': Decimal('0'),
            'balance': 0,
        })
    for pmt in payments:
        transactions.append({
            'date': pmt.payment_date,
            'type': 'PAYMENT',
            'reference': pmt.payment_number,
            'debit': Decimal('0'),
            'credit': pmt.total_amount,
            'balance': 0,
        })

    transactions.sort(key=lambda x: x['date'])
    balance = Decimal('0')
    for t in transactions:
        balance += t['debit'] - t['credit']
        t['balance'] = balance

    return transactions


def get_cash_flow_report(tenant_id, date_from, date_to):
    """Cash flow report — all payments within a period."""
    payments = InventorySupplierPayment.objects.filter(
        tenant_id=tenant_id,
        payment_date__gte=date_from,
        payment_date__lte=date_to,
        status__in=['POSTED', 'COMPLETED'],
    ).order_by('payment_date')

    total_by_method = {}
    daily_totals = {}
    for p in payments:
        method = p.payment_method
        total_by_method[method] = total_by_method.get(method, Decimal('0')) + p.total_amount
        day = str(p.payment_date)
        daily_totals[day] = daily_totals.get(day, Decimal('0')) + p.total_amount

    return {
        'total_payments': sum(p.total_amount for p in payments),
        'payment_count': payments.count(),
        'by_method': total_by_method,
        'daily_totals': daily_totals,
        'payments': list(payments.values(
            'payment_number', 'payment_date', 'supplier_name',
            'payment_method', 'total_amount', 'status'
        )),
    }
