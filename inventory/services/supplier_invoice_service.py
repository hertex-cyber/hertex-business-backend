"""
Supplier Invoice (Purchase Bill) Service — handles invoice workflow,
GRN integration, payment tracking, history logging, and notifications.

Workflow:
    DRAFT → PENDING_APPROVAL → APPROVED → POSTED → PARTIALLY_PAID → PAID
                                                   → CANCELLED
                                                   → VOIDED

Business Rules:
1. Invoice quantity cannot exceed received quantity on GRN items.
2. Cannot invoice cancelled GRNs.
3. Support multiple GRNs per invoice.
4. Prevent duplicate invoicing of the same received quantity.
5. Automatically calculate totals, taxes and discounts.
6. Automatically update outstanding balance.
7. Integrate with Accounts Payable (payments.Payment).
8. Record complete audit history.
9. Generate notifications.
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from inventory.models import (
    InventorySupplierInvoice, InventorySupplierInvoiceItem,
    InventorySupplierInvoiceHistory, InventorySupplierInvoiceAttachment,
    InventoryGoodsReceipt, InventoryGoodsReceiptItem,
    PurchaseOrder,
)
from inventory.services.notification_service import InventoryNotificationService


def _log_history(invoice, action, from_status, to_status, user, remarks=''):
    """Create a history entry for an invoice action."""
    InventorySupplierInvoiceHistory.objects.create(
        invoice=invoice,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def _calculate_line_total(qty, unit_price, tax_rate, discount_rate):
    """Calculate line total: (qty * unit_price) * (1 + tax_rate/100) * (1 - discount_rate/100)"""
    qty = Decimal(str(qty))
    price = Decimal(str(unit_price))
    tax = Decimal(str(tax_rate))
    discount = Decimal(str(discount_rate))
    subtotal = qty * price
    tax_mult = (Decimal('100') + tax) / Decimal('100')
    discount_mult = (Decimal('100') - discount) / Decimal('100')
    return (subtotal * tax_mult * discount_mult).quantize(Decimal('0.0001'))


def _recalculate_invoice_totals(invoice):
    """Recalculate subtotal, grand_total, outstanding based on line items."""
    items = invoice.items.all()
    subtotal = sum((Decimal(str(i.quantity)) * Decimal(str(i.unit_price))) for i in items)
    line_totals = sum(i.line_total for i in items)
    grand_total = line_totals + invoice.shipping_charges + invoice.other_charges - invoice.discount_amount

    invoice.subtotal = subtotal.quantize(Decimal('0.0001'))
    invoice.grand_total = grand_total.quantize(Decimal('0.0001'))

    if invoice.outstanding_amount == 0 or invoice.status == 'DRAFT':
        invoice.outstanding_amount = grand_total.quantize(Decimal('0.0001'))

    invoice.save(update_fields=['subtotal', 'grand_total', 'outstanding_amount'])


def _update_payment_status(invoice):
    """Update payment status based on outstanding amount."""
    if invoice.outstanding_amount <= 0:
        invoice.payment_status = 'PAID'
        invoice.status = 'PAID'
    elif invoice.outstanding_amount < invoice.grand_total:
        invoice.payment_status = 'PARTIALLY_PAID'
        if invoice.status != 'PARTIALLY_PAID':
            invoice.status = 'PARTIALLY_PAID'
    else:
        invoice.payment_status = 'UNPAID'
    invoice.save(update_fields=['payment_status', 'status'])


def generate_invoice_number(tenant_id):
    """Generate a unique invoice number: SI-YYYYMMDD-XXXX"""
    from django.db.models import Max
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"SI-{today}-"
    last = InventorySupplierInvoice.objects.filter(
        tenant_id=tenant_id,
        invoice_number__startswith=prefix,
    ).aggregate(Max('invoice_number'))
    if last['invoice_number__max']:
        last_num = int(last['invoice_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


@transaction.atomic
def create_invoice(tenant_id, data, created_by):
    """Create a new Supplier Invoice in DRAFT status."""
    items_data = data.pop('items', [])
    grn_ids = data.pop('goods_receipts', [])

    supplier_id = data.get('supplier')
    supplier_name = ''
    if supplier_id:
        from contacts.models import Contact
        try:
            supplier = Contact.objects.get(id=supplier_id)
            supplier_name = supplier.name
        except Contact.DoesNotExist:
            pass

    invoice = InventorySupplierInvoice.objects.create(
        tenant_id=tenant_id,
        invoice_number=data.get('invoice_number') or generate_invoice_number(tenant_id),
        invoice_date=data.get('invoice_date', timezone.now().date()),
        due_date=data.get('due_date'),
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        supplier_invoice_number=data.get('supplier_invoice_number', ''),
        currency=data.get('currency', 'INR'),
        exchange_rate=Decimal(str(data.get('exchange_rate', 1))),
        purchase_order_id=data.get('purchase_order'),
        status='DRAFT',
        payment_status='UNPAID',
        subtotal=0,
        discount_amount=Decimal(str(data.get('discount_amount', 0))),
        tax_amount=Decimal(str(data.get('tax_amount', 0))),
        shipping_charges=Decimal(str(data.get('shipping_charges', 0))),
        other_charges=Decimal(str(data.get('other_charges', 0))),
        grand_total=0,
        outstanding_amount=0,
        remarks=data.get('remarks', ''),
        terms=data.get('terms', ''),
        created_by=created_by,
        updated_by=created_by,
    )

    if grn_ids:
        grns = InventoryGoodsReceipt.objects.filter(id__in=grn_ids, tenant_id=tenant_id)
        valid_grns = [g for g in grns if g.status not in ('CANCELLED',)]
        invoice.goods_receipts.set(valid_grns)

    for item_data in items_data:
        qty = Decimal(str(item_data.get('quantity', 1)))
        unit_price = Decimal(str(item_data.get('unit_price', 0)))
        tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
        discount_rate = Decimal(str(item_data.get('discount_rate', 0)))

        if qty <= 0:
            raise ValueError("Quantity must be greater than 0.")

        grn_item_id = item_data.get('goods_receipt_item')

        if grn_item_id:
            grn_item = InventoryGoodsReceiptItem.objects.select_related(
                'goods_receipt'
            ).get(id=grn_item_id)

            if grn_item.goods_receipt.status in ('CANCELLED',):
                raise ValueError(
                    f"Cannot invoice against cancelled GRN '{grn_item.goods_receipt.grn_number}'."
                )

            total_invoiced = InventorySupplierInvoiceItem.objects.filter(
                goods_receipt_item=grn_item,
                invoice__status__in=['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'POSTED', 'PARTIALLY_PAID', 'PAID'],
            ).exclude(invoice=invoice).aggregate(
                total=Sum('quantity')
            )['total'] or Decimal('0')

            if total_invoiced + qty > grn_item.received_quantity:
                raise ValueError(
                    f"Cannot invoice {qty} for item: received {grn_item.received_quantity}, "
                    f"already invoiced {total_invoiced}."
                )

        line_total = _calculate_line_total(qty, unit_price, tax_rate, discount_rate)

        InventorySupplierInvoiceItem.objects.create(
            invoice=invoice,
            item_id=item_data.get('item_id'),
            item_description=item_data.get('item_description', ''),
            goods_receipt_item_id=grn_item_id,
            quantity=qty,
            unit_price=unit_price,
            tax_rate=tax_rate,
            discount_rate=discount_rate,
            line_total=line_total,
            remarks=item_data.get('remarks', ''),
        )

    _recalculate_invoice_totals(invoice)
    _log_history(invoice, 'CREATED', '', 'DRAFT', created_by)
    InventoryNotificationService.notify_supplier_invoice_event('created', invoice)

    return invoice


@transaction.atomic
def update_invoice(invoice, data, user):
    """Update a DRAFT Supplier Invoice."""
    if invoice.status != 'DRAFT':
        raise ValueError(f"Cannot update an invoice in status '{invoice.status}'")

    items_data = data.pop('items', None)
    grn_ids = data.pop('goods_receipts', None)

    if 'invoice_date' in data:
        invoice.invoice_date = data['invoice_date']
    if 'due_date' in data:
        invoice.due_date = data['due_date']
    if 'supplier' in data:
        invoice.supplier_id = data['supplier']
        if data['supplier']:
            from contacts.models import Contact
            try:
                contact = Contact.objects.get(id=data['supplier'])
                invoice.supplier_name = contact.name
            except Contact.DoesNotExist:
                pass
    if 'supplier_invoice_number' in data:
        invoice.supplier_invoice_number = data['supplier_invoice_number']
    if 'currency' in data:
        invoice.currency = data['currency']
    if 'exchange_rate' in data:
        invoice.exchange_rate = Decimal(str(data['exchange_rate']))
    if 'purchase_order' in data:
        invoice.purchase_order_id = data['purchase_order']
    if 'discount_amount' in data:
        invoice.discount_amount = Decimal(str(data['discount_amount']))
    if 'tax_amount' in data:
        invoice.tax_amount = Decimal(str(data['tax_amount']))
    if 'shipping_charges' in data:
        invoice.shipping_charges = Decimal(str(data['shipping_charges']))
    if 'other_charges' in data:
        invoice.other_charges = Decimal(str(data['other_charges']))
    if 'remarks' in data:
        invoice.remarks = data['remarks']
    if 'terms' in data:
        invoice.terms = data['terms']

    invoice.updated_by = user
    invoice.save()

    if grn_ids is not None:
        grns = InventoryGoodsReceipt.objects.filter(id__in=grn_ids)
        valid_grns = [g for g in grns if g.status not in ('CANCELLED',)]
        invoice.goods_receipts.set(valid_grns)

    if items_data is not None:
        invoice.items.all().delete()
        for item_data in items_data:
            qty = Decimal(str(item_data.get('quantity', 1)))
            unit_price = Decimal(str(item_data.get('unit_price', 0)))
            tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
            discount_rate = Decimal(str(item_data.get('discount_rate', 0)))

            if qty <= 0:
                raise ValueError("Quantity must be greater than 0.")

            grn_item_id = item_data.get('goods_receipt_item')

            if grn_item_id:
                grn_item = InventoryGoodsReceiptItem.objects.select_related(
                    'goods_receipt'
                ).get(id=grn_item_id)

                if grn_item.goods_receipt.status in ('CANCELLED',):
                    raise ValueError(
                        f"Cannot invoice against cancelled GRN '{grn_item.goods_receipt.grn_number}'."
                    )

                total_invoiced = InventorySupplierInvoiceItem.objects.filter(
                    goods_receipt_item=grn_item,
                    invoice__status__in=[
                        'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'POSTED',
                        'PARTIALLY_PAID', 'PAID',
                    ],
                ).exclude(invoice=invoice).aggregate(
                    total=Sum('quantity')
                )['total'] or Decimal('0')

                if total_invoiced + qty > grn_item.received_quantity:
                    raise ValueError(
                        f"Cannot invoice {qty} for item: received {grn_item.received_quantity}, "
                        f"already invoiced {total_invoiced}."
                    )

            line_total = _calculate_line_total(qty, unit_price, tax_rate, discount_rate)

            InventorySupplierInvoiceItem.objects.create(
                invoice=invoice,
                item_id=item_data.get('item_id'),
                item_description=item_data.get('item_description', ''),
                goods_receipt_item_id=grn_item_id,
                quantity=qty,
                unit_price=unit_price,
                tax_rate=tax_rate,
                discount_rate=discount_rate,
                line_total=line_total,
                remarks=item_data.get('remarks', ''),
            )

    _recalculate_invoice_totals(invoice)
    _log_history(invoice, 'UPDATED', 'DRAFT', 'DRAFT', user)
    return invoice


@transaction.atomic
def submit_invoice(invoice, user):
    """Submit invoice for approval (DRAFT → PENDING_APPROVAL)."""
    if invoice.status != 'DRAFT':
        raise ValueError(f"Cannot submit an invoice in status '{invoice.status}'")

    if not invoice.items.exists():
        raise ValueError("Cannot submit an invoice with no items.")

    old_status = invoice.status
    invoice.status = 'PENDING_APPROVAL'
    invoice.updated_by = user
    invoice.save()

    _log_history(invoice, 'SUBMITTED', old_status, 'PENDING_APPROVAL', user)
    InventoryNotificationService.notify_supplier_invoice_event('submitted', invoice)

    return invoice


@transaction.atomic
def approve_invoice(invoice, user, notes=''):
    """Approve an invoice (PENDING_APPROVAL → APPROVED)."""
    if invoice.status != 'PENDING_APPROVAL':
        raise ValueError(f"Cannot approve an invoice in status '{invoice.status}'")

    old_status = invoice.status
    invoice.status = 'APPROVED'
    invoice.approved_by = user
    invoice.approved_at = timezone.now()
    invoice.approval_notes = notes
    invoice.updated_by = user
    invoice.save()

    _log_history(invoice, 'APPROVED', old_status, 'APPROVED', user, notes)
    InventoryNotificationService.notify_supplier_invoice_event('approved', invoice)

    return invoice


@transaction.atomic
def post_invoice(invoice, user):
    """Post an approved invoice (APPROVED → POSTED)."""
    if invoice.status != 'APPROVED':
        raise ValueError(f"Cannot post an invoice in status '{invoice.status}'")

    old_status = invoice.status
    invoice.status = 'POSTED'
    invoice.posted_by = user
    invoice.posted_at = timezone.now()
    invoice.updated_by = user
    invoice.save()

    _recalculate_invoice_totals(invoice)

    _log_history(invoice, 'POSTED', old_status, 'POSTED', user)
    InventoryNotificationService.notify_supplier_invoice_event('posted', invoice)

    return invoice


@transaction.atomic
def record_payment(invoice, user, amount, payment_method='Bank Transfer',
                   payment_date=None, reference='', remarks=''):
    """
    Record a payment against a posted/partially paid invoice.
    Creates a Payment record in the payments app.
    """
    if invoice.status not in ('POSTED', 'PARTIALLY_PAID'):
        raise ValueError(
            f"Cannot record payment against an invoice in status '{invoice.status}'"
        )

    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Payment amount must be greater than 0.")

    if amount > invoice.outstanding_amount:
        raise ValueError(
            f"Payment amount {amount} exceeds outstanding amount {invoice.outstanding_amount}."
        )

    # Create Payment record
    from payments.models import Payment
    Payment.objects.create(
        contact=invoice.supplier,
        amount=amount,
        payment_for=f"Supplier Invoice {invoice.invoice_number}",
        remarks=remarks or f"Payment for invoice {invoice.invoice_number}",
        invoice=invoice.invoice_number,
        payment_method=payment_method,
        recorded_by=user,
    )

    old_status = invoice.status
    invoice.outstanding_amount = (invoice.outstanding_amount - amount).quantize(Decimal('0.0001'))
    invoice.updated_by = user
    invoice.save(update_fields=['outstanding_amount', 'updated_by'])

    _update_payment_status(invoice)
    invoice.refresh_from_db()

    _log_history(
        invoice, 'PAYMENT_RECORDED', old_status, invoice.status,
        user, f"Payment of {amount} recorded via {payment_method}"
    )
    InventoryNotificationService.notify_supplier_invoice_event('payment_recorded', invoice)

    return invoice


@transaction.atomic
def cancel_invoice(invoice, user):
    """Cancel an invoice (DRAFT, PENDING_APPROVAL, or APPROVED only)."""
    if invoice.status not in ('DRAFT', 'PENDING_APPROVAL', 'APPROVED'):
        raise ValueError(f"Cannot cancel an invoice in status '{invoice.status}'")

    old_status = invoice.status
    invoice.status = 'CANCELLED'
    invoice.updated_by = user
    invoice.save()

    _log_history(invoice, 'CANCELLED', old_status, 'CANCELLED', user)
    InventoryNotificationService.notify_supplier_invoice_event('cancelled', invoice)

    return invoice


@transaction.atomic
def void_invoice(invoice, user):
    """
    Void a posted/paid invoice (POSTED, PARTIALLY_PAID, or PAID only).
    This reverses the invoice for accounting purposes.
    """
    if invoice.status not in ('POSTED', 'PARTIALLY_PAID', 'PAID'):
        raise ValueError(f"Cannot void an invoice in status '{invoice.status}'")

    old_status = invoice.status
    invoice.status = 'VOIDED'
    invoice.updated_by = user
    invoice.save()

    _log_history(invoice, 'VOIDED', old_status, 'VOIDED', user)
    InventoryNotificationService.notify_supplier_invoice_event('voided', invoice)

    return invoice


def get_history(invoice):
    """Get the audit trail for an invoice."""
    return InventorySupplierInvoiceHistory.objects.filter(
        invoice=invoice
    ).select_related('performed_by').order_by('-timestamp')
