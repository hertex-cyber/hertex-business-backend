"""
Purchase Return Business Logic Service
========================================
Handles all state transitions and business rules for Purchase Returns.

Workflow:
  DRAFT -> submit() -> PENDING_APPROVAL -> approve() -> APPROVED
                                            -> reject() -> REJECTED
  APPROVED -> return_to_supplier() -> RETURNED -> complete() -> COMPLETED
  DRAFT/PENDING_APPROVAL/APPROVED -> cancel() -> CANCELLED

Rules:
  - Return qty must not exceed GRN received qty minus already-returned
  - Stock ledger updated on RETURNED (PURCHASE_RETURN, outbound)
  - Items can only be added/edited in DRAFT
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from inventory.models import (
    InventoryPurchaseReturn, InventoryPurchaseReturnItem,
    InventoryPurchaseReturnHistory, InventoryPurchaseReturnAttachment,
    InventoryGoodsReceiptItem, InventoryItem, PurchaseOrderItem,
)
from inventory.services.stock_engine import create_ledger_entry
from inventory.services.notification_service import InventoryNotificationService


def _create_history(return_obj, action, from_status, to_status, user=None, remarks=''):
    InventoryPurchaseReturnHistory.objects.create(
        purchase_return=return_obj,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def _calculate_totals(return_obj):
    items = return_obj.items.all()
    subtotal = sum(item.return_quantity * item.unit_cost for item in items)
    tax_amount = sum(item.total_amount - (item.return_quantity * item.unit_cost) for item in items)
    return_obj.subtotal = subtotal
    return_obj.tax_amount = tax_amount
    return_obj.total_amount = subtotal + tax_amount
    return_obj.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])


def _validate_return_quantity(goods_receipt_item_id, return_quantity, exclude_return_id=None):
    grn_item = InventoryGoodsReceiptItem.objects.select_related('item').get(id=goods_receipt_item_id)
    qs = InventoryPurchaseReturnItem.objects.filter(
        goods_receipt_item_id=goods_receipt_item_id,
        purchase_return__status__in=['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'RETURNED', 'COMPLETED'],
    )
    if exclude_return_id:
        qs = qs.exclude(purchase_return_id=exclude_return_id)
    already_returned = qs.aggregate(total=Sum('return_quantity'))['total'] or Decimal('0')
    remaining = grn_item.received_quantity - already_returned
    if return_quantity > remaining:
        available = grn_item.item.item_code if grn_item.item else str(grn_item.id)
        raise ValueError(
            f"Cannot return {return_quantity} of item '{available}'. "
            f"Only {remaining} remaining (received: {grn_item.received_quantity}, "
            f"already returned: {already_returned})."
        )
    return grn_item


@transaction.atomic
def create_return(return_data, items_data, user=None):
    return_number = return_data.get('return_number', '').strip()
    if not return_number:
        raise ValueError("Return number is required.")
    tenant_id = return_data.get('tenant_id')
    if not tenant_id:
        raise ValueError("tenant_id is required.")

    return_obj = InventoryPurchaseReturn.objects.create(
        tenant_id=tenant_id,
        return_number=return_number,
        return_date=return_data.get('return_date', timezone.now().date()),
        supplier_id=return_data.get('supplier'),
        supplier_name=return_data.get('supplier_name', ''),
        purchase_order_id=return_data.get('purchase_order'),
        goods_receipt_id=return_data.get('goods_receipt'),
        supplier_invoice_id=return_data.get('supplier_invoice'),
        return_reason=return_data.get('return_reason', ''),
        status='DRAFT',
        subtotal=0,
        tax_amount=0,
        total_amount=0,
        remarks=return_data.get('remarks', ''),
        created_by=user,
        updated_by=user,
    )

    for item_data in items_data:
        grn_item_id = item_data.get('goods_receipt_item')
        return_qty = Decimal(str(item_data.get('return_quantity', 0)))
        if grn_item_id:
            _validate_return_quantity(grn_item_id, return_qty)
            grn_item = InventoryGoodsReceiptItem.objects.get(id=grn_item_id)
            received_qty = grn_item.received_quantity
            unit_cost = item_data.get('unit_cost', grn_item.unit_price)
        else:
            received_qty = Decimal(str(item_data.get('received_quantity', 0)))
            unit_cost = Decimal(str(item_data.get('unit_cost', 0)))

        tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
        line_total = (return_qty * unit_cost) * (Decimal('1') + tax_rate / Decimal('100'))

        InventoryPurchaseReturnItem.objects.create(
            purchase_return=return_obj,
            item_id=item_data['item'],
            goods_receipt_item_id=grn_item_id,
            received_quantity=received_qty,
            return_quantity=return_qty,
            damaged_quantity=Decimal(str(item_data.get('damaged_quantity', 0))),
            unit_cost=unit_cost,
            tax_rate=tax_rate,
            total_amount=line_total,
            remarks=item_data.get('remarks', ''),
        )

    _calculate_totals(return_obj)
    _create_history(return_obj, 'CREATED', '', 'DRAFT', user)
    InventoryNotificationService.notify_purchase_return_event('created', return_obj)
    return return_obj


@transaction.atomic
def update_return(return_obj, return_data, items_data, user=None):
    if return_obj.status != 'DRAFT':
        raise ValueError("Only draft returns can be edited.")

    for field in ['return_date', 'supplier', 'supplier_name', 'purchase_order',
                  'goods_receipt', 'supplier_invoice', 'return_reason', 'remarks']:
        if field in return_data:
            setattr(return_obj, field, return_data[field])
    return_obj.updated_by = user
    return_obj.save()

    if items_data is not None:
        return_obj.items.all().delete()
        for item_data in items_data:
            grn_item_id = item_data.get('goods_receipt_item')
            return_qty = Decimal(str(item_data.get('return_quantity', 0)))
            if grn_item_id:
                _validate_return_quantity(grn_item_id, return_qty, exclude_return_id=return_obj.id)
                grn_item = InventoryGoodsReceiptItem.objects.get(id=grn_item_id)
                received_qty = grn_item.received_quantity
                unit_cost = item_data.get('unit_cost', grn_item.unit_price)
            else:
                received_qty = Decimal(str(item_data.get('received_quantity', 0)))
                unit_cost = Decimal(str(item_data.get('unit_cost', 0)))

            tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
            line_total = (return_qty * unit_cost) * (Decimal('1') + tax_rate / Decimal('100'))

            InventoryPurchaseReturnItem.objects.create(
                purchase_return=return_obj,
                item_id=item_data['item'],
                goods_receipt_item_id=grn_item_id,
                received_quantity=received_qty,
                return_quantity=return_qty,
                damaged_quantity=Decimal(str(item_data.get('damaged_quantity', 0))),
                unit_cost=unit_cost,
                tax_rate=tax_rate,
                total_amount=line_total,
                remarks=item_data.get('remarks', ''),
            )

    _calculate_totals(return_obj)
    _create_history(return_obj, 'UPDATED', 'DRAFT', 'DRAFT', user)
    return return_obj


@transaction.atomic
def submit_return(return_obj, user=None):
    if return_obj.status != 'DRAFT':
        raise ValueError("Only draft returns can be submitted.")
    if return_obj.items.count() == 0:
        raise ValueError("Cannot submit a return with no items.")

    return_obj.status = 'PENDING_APPROVAL'
    return_obj.updated_by = user
    return_obj.save(update_fields=['status', 'updated_by'])
    _create_history(return_obj, 'SUBMITTED', 'DRAFT', 'PENDING_APPROVAL', user)
    InventoryNotificationService.notify_purchase_return_event('submitted', return_obj)
    return return_obj


@transaction.atomic
def approve_return(return_obj, user=None, notes=''):
    if return_obj.status != 'PENDING_APPROVAL':
        raise ValueError("Only returns pending approval can be approved.")

    return_obj.status = 'APPROVED'
    return_obj.approved_by = user
    return_obj.approved_at = timezone.now()
    return_obj.approval_notes = notes
    return_obj.updated_by = user
    return_obj.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_notes', 'updated_by'])
    _create_history(return_obj, 'APPROVED', 'PENDING_APPROVAL', 'APPROVED', user, notes)
    InventoryNotificationService.notify_purchase_return_event('approved', return_obj)
    return return_obj


@transaction.atomic
def reject_return(return_obj, user=None, notes=''):
    if return_obj.status != 'PENDING_APPROVAL':
        raise ValueError("Only returns pending approval can be rejected.")

    return_obj.status = 'REJECTED'
    return_obj.approved_by = user
    return_obj.approved_at = timezone.now()
    return_obj.approval_notes = notes
    return_obj.updated_by = user
    return_obj.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_notes', 'updated_by'])
    _create_history(return_obj, 'REJECTED', 'PENDING_APPROVAL', 'REJECTED', user, notes)
    InventoryNotificationService.notify_purchase_return_event('rejected', return_obj)
    return return_obj


@transaction.atomic
def return_to_supplier(return_obj, user=None):
    """
    Execute the actual return to supplier.
    Creates stock ledger entries (PURCHASE_RETURN, OUT) for each item.
    """
    if return_obj.status != 'APPROVED':
        raise ValueError("Only approved returns can be processed.")

    # Lock items being returned
    items = return_obj.items.select_related('item').all()
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=return_obj.tenant_id
        ).select_for_update()
    )

    return_obj.status = 'RETURNED'
    return_obj.processed_by = user
    return_obj.processed_at = timezone.now()
    return_obj.updated_by = user
    return_obj.save(update_fields=['status', 'processed_by', 'processed_at', 'updated_by'])

    for item in items:
        location_id = None
        if return_obj.goods_receipt:
            grn = return_obj.goods_receipt
            location_id = grn.location_id if hasattr(grn, 'location_id') else None

        create_ledger_entry(
            tenant_id=return_obj.tenant_id,
            item_id=item.item_id,
            transaction_type='PURCHASE_RETURN',
            quantity=-item.return_quantity,
            location_id=location_id,
            unit_cost=item.unit_cost,
            total_cost=item.unit_cost * item.return_quantity,
            reference_type='PURCHASE_RETURN',
            reference_id=str(return_obj.id),
            description=f"Purchase Return {return_obj.return_number}: {item.item.item_code} x {item.return_quantity}",
            created_by=user,
        )

        if item.goods_receipt_item_id:
            InventoryGoodsReceiptItem.objects.filter(id=item.goods_receipt_item_id).update(
                returned_quantity=F('returned_quantity') + item.return_quantity
            )

    _create_history(return_obj, 'RETURNED', 'APPROVED', 'RETURNED', user)
    InventoryNotificationService.notify_purchase_return_event('returned', return_obj)
    return return_obj


@transaction.atomic
def complete_return(return_obj, user=None):
    if return_obj.status != 'RETURNED':
        raise ValueError("Only returned returns can be completed.")

    return_obj.status = 'COMPLETED'
    return_obj.completed_by = user
    return_obj.completed_at = timezone.now()
    return_obj.updated_by = user
    return_obj.save(update_fields=['status', 'completed_by', 'completed_at', 'updated_by'])
    _create_history(return_obj, 'COMPLETED', 'RETURNED', 'COMPLETED', user)
    InventoryNotificationService.notify_purchase_return_event('completed', return_obj)
    return return_obj


@transaction.atomic
def cancel_return(return_obj, user=None, remarks=''):
    if return_obj.status not in ['DRAFT', 'PENDING_APPROVAL', 'APPROVED']:
        raise ValueError(
            "Only draft, pending approval, or approved returns can be cancelled."
        )

    return_obj.status = 'CANCELLED'
    return_obj.updated_by = user
    return_obj.remarks = (return_obj.remarks or '') + f"\nCancelled: {remarks}".strip()
    return_obj.save(update_fields=['status', 'updated_by', 'remarks'])
    _create_history(return_obj, 'CANCELLED', return_obj.status, 'CANCELLED', user, remarks)
    InventoryNotificationService.notify_purchase_return_event('cancelled', return_obj)
    return return_obj


def get_history(return_obj):
    return return_obj.history.select_related('performed_by').order_by('-timestamp')
