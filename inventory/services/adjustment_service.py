"""
Adjustment Service — handles stock adjustment workflow, history logging, and notifications.

Every adjustment action:
1. Validates the state transition
2. Creates Stock Ledger entries (apply only)
3. Logs a history entry
4. Sends notifications to relevant parties

Never update stock quantities directly.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from inventory.models import (
    InventoryAdjustment, InventoryAdjustmentItem,
    InventoryAdjustmentHistory, InventoryAdjustmentReason,
    InventoryItem, StockLedger,
)
from inventory.services.stock_engine import (
    get_available_stock,
    create_ledger_entry,
)
from inventory.services.notification_service import InventoryNotificationService


def _log_history(adjustment, action, from_status, to_status, user, remarks=''):
    """Create a history entry for an adjustment action."""
    InventoryAdjustmentHistory.objects.create(
        adjustment=adjustment,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def generate_adjustment_number(tenant_id):
    """Generate a unique adjustment number: ADJ-YYYYMMDD-XXXX"""
    from django.db.models import Max
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"ADJ-{today}-"
    last = InventoryAdjustment.objects.filter(
        tenant_id=tenant_id,
        adjustment_number__startswith=prefix,
    ).aggregate(Max('adjustment_number'))
    if last['adjustment_number__max']:
        last_num = int(last['adjustment_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


@transaction.atomic
def create_adjustment(tenant_id, data, created_by):
    """Create a new adjustment in DRAFT status."""
    items_data = data.pop('items', [])

    reason = InventoryAdjustmentReason.objects.for_tenant(tenant_id).filter(
        id=data.get('reason')
    ).first()
    if not reason:
        raise ValueError("Adjustment reason not found.")

    adjustment = InventoryAdjustment.objects.create(
        tenant_id=tenant_id,
        adjustment_number=data.get('adjustment_number') or generate_adjustment_number(tenant_id),
        adjustment_date=data.get('adjustment_date', timezone.now().date()),
        location_id=data.get('location'),
        adjustment_type=reason.adjustment_type,
        reason=reason,
        status='DRAFT',
        remarks=data.get('remarks', ''),
        created_by=created_by,
        updated_by=created_by,
    )

    for item_data in items_data:
        # Get available stock at the time of creation
        available = get_available_stock(
            item_data['item_id'], tenant_id, adjustment.location_id
        )
        # adjustment_quantity is always positive in the API; type determines direction
        adj_qty = Decimal(str(item_data['adjustment_quantity']))
        if reason.adjustment_type == 'DECREASE':
            adj_qty = -adj_qty

        InventoryAdjustmentItem.objects.create(
            adjustment=adjustment,
            item_id=item_data['item_id'],
            available_quantity=available,
            adjustment_quantity=adj_qty,
            unit_id=item_data.get('unit'),
            remarks=item_data.get('remarks', ''),
        )

    # Log creation
    _log_history(adjustment, 'CREATED', '', 'DRAFT', created_by)

    # Notify on creation
    InventoryNotificationService.notify_adjustment_event('created', adjustment)

    return adjustment


@transaction.atomic
def update_adjustment(adjustment, data, user):
    """Update a DRAFT adjustment."""
    if adjustment.status != 'DRAFT':
        raise ValueError(f"Cannot update adjustment in status '{adjustment.status}'")

    items_data = data.pop('items', [])
    reason_id = data.get('reason')
    if reason_id:
        reason = InventoryAdjustmentReason.objects.for_tenant(adjustment.tenant_id).filter(
            id=reason_id
        ).first()
        if not reason:
            raise ValueError("Adjustment reason not found.")

        adjustment.adjustment_type = reason.adjustment_type
        adjustment.reason = reason

    if 'location' in data:
        adjustment.location_id = data['location']
    if 'adjustment_date' in data:
        adjustment.adjustment_date = data['adjustment_date']
    if 'remarks' in data:
        adjustment.remarks = data['remarks']

    adjustment.updated_by = user
    adjustment.save()

    # Replace items
    if items_data:
        adjustment.items.all().delete()
        for item_data in items_data:
            available = get_available_stock(
                item_data['item_id'], adjustment.tenant_id, adjustment.location_id
            )
            adj_qty = Decimal(str(item_data['adjustment_quantity']))
            if adjustment.adjustment_type == 'DECREASE':
                adj_qty = -adj_qty

            InventoryAdjustmentItem.objects.create(
                adjustment=adjustment,
                item_id=item_data['item_id'],
                available_quantity=available,
                adjustment_quantity=adj_qty,
                unit_id=item_data.get('unit'),
                remarks=item_data.get('remarks', ''),
            )

    _log_history(adjustment, 'UPDATED', 'DRAFT', 'DRAFT', user)
    return adjustment


@transaction.atomic
def submit_adjustment(adjustment, user):
    """Submit adjustment for approval."""
    if adjustment.status != 'DRAFT':
        raise ValueError(f"Cannot submit adjustment in status '{adjustment.status}'")

    # Validate stock availability for DECREASE adjustments
    if adjustment.adjustment_type == 'DECREASE':
        items = adjustment.items.select_related('item').all()
        item_ids = [i.item_id for i in items]
        locked_items = list(
            InventoryItem.objects.filter(
                id__in=item_ids, tenant_id=adjustment.tenant_id
            ).select_for_update()
        )
        for item in items:
            available = get_available_stock(
                item.item_id, adjustment.tenant_id, adjustment.location_id
            )
            required = abs(item.adjustment_quantity)
            if available < required:
                raise ValueError(
                    f"Insufficient stock for '{item.item.item_name}': "
                    f"available {available}, adjustment requires {required}"
                )

    old_status = adjustment.status
    adjustment.status = 'PENDING_APPROVAL'
    adjustment.updated_by = user
    adjustment.save()

    _log_history(adjustment, 'SUBMITTED', old_status, 'PENDING_APPROVAL', user)
    InventoryNotificationService.notify_adjustment_event('submitted', adjustment)

    return adjustment


@transaction.atomic
def approve_adjustment(adjustment, user, notes=''):
    """Approve an adjustment."""
    if adjustment.status != 'PENDING_APPROVAL':
        raise ValueError(f"Cannot approve adjustment in status '{adjustment.status}'")

    adjustment.status = 'APPROVED'
    adjustment.approved_by = user
    adjustment.approved_at = timezone.now()
    adjustment.approval_notes = notes
    adjustment.updated_by = user
    adjustment.save()

    _log_history(adjustment, 'APPROVED', 'PENDING_APPROVAL', 'APPROVED', user, notes)
    InventoryNotificationService.notify_adjustment_event('approved', adjustment)

    return adjustment


@transaction.atomic
def reject_adjustment(adjustment, user, notes=''):
    """Reject an adjustment."""
    if adjustment.status != 'PENDING_APPROVAL':
        raise ValueError(f"Cannot reject adjustment in status '{adjustment.status}'")

    adjustment.status = 'REJECTED'
    adjustment.approved_by = user
    adjustment.approved_at = timezone.now()
    adjustment.approval_notes = notes
    adjustment.updated_by = user
    adjustment.save()

    _log_history(adjustment, 'REJECTED', 'PENDING_APPROVAL', 'REJECTED', user, notes)
    InventoryNotificationService.notify_adjustment_event('rejected', adjustment)

    return adjustment


@transaction.atomic
def apply_adjustment(adjustment, user):
    """
    Apply an adjustment — creates stock ledger entries.
    
    INCREASE: Creates ADJUSTMENT_IN entries with positive quantity.
    DECREASE: Creates ADJUSTMENT_OUT entries with negative quantity.
    
    Never updates stock directly. The Stock Availability Engine recalculates from the ledger.
    """
    if adjustment.status != 'APPROVED':
        raise ValueError(f"Cannot apply adjustment in status '{adjustment.status}'")

    # Lock items before validation and ledger creation
    items = adjustment.items.select_related('item').all()
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=adjustment.tenant_id
        ).select_for_update()
    )

    # Validate stock again for DECREASE adjustments
    if adjustment.adjustment_type == 'DECREASE':
        for item in items:
            available = get_available_stock(
                item.item_id, adjustment.tenant_id, adjustment.location_id
            )
            required = abs(item.adjustment_quantity)
            if available < required:
                raise ValueError(
                    f"Insufficient stock for '{item.item.item_name}': "
                    f"available {available}, adjustment requires {required}"
                )

    # Create ledger entries for each item
    for item in items:
        transaction_type = 'ADJUSTMENT_IN' if adjustment.adjustment_type == 'INCREASE' else 'ADJUSTMENT_OUT'
        direction_label = "increase" if adjustment.adjustment_type == 'INCREASE' else "decrease"

        create_ledger_entry(
            tenant_id=adjustment.tenant_id,
            item_id=item.item_id,
            transaction_type=transaction_type,
            quantity=item.adjustment_quantity,  # positive for IN, negative for OUT
            location_id=adjustment.location_id,
            reference_type='ADJUSTMENT',
            reference_id=str(adjustment.adjustment_number),
            description=(
                f"Stock {direction_label} — {adjustment.reason.reason_name} "
                f"({adjustment.adjustment_number})"
            ),
            created_by=user,
        )

    adjustment.status = 'APPLIED'
    adjustment.applied_by = user
    adjustment.applied_at = timezone.now()
    adjustment.updated_by = user
    adjustment.save()

    _log_history(adjustment, 'APPLIED', 'APPROVED', 'APPLIED', user)
    InventoryNotificationService.notify_adjustment_event('applied', adjustment)

    return adjustment


@transaction.atomic
def cancel_adjustment(adjustment, user):
    """Cancel an adjustment (DRAFT or PENDING_APPROVAL only)."""
    if adjustment.status not in ['DRAFT', 'PENDING_APPROVAL']:
        raise ValueError(f"Cannot cancel adjustment in status '{adjustment.status}'")

    old_status = adjustment.status
    adjustment.status = 'CANCELLED'
    adjustment.updated_by = user
    adjustment.save()

    _log_history(adjustment, 'CANCELLED', old_status, 'CANCELLED', user)

    return adjustment
