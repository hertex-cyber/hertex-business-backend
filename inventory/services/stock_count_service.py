"""
Stock Count Service — handles physical stock count (cycle count) workflow.

Workflow:
  DRAFT → ASSIGNED → IN_PROGRESS → SUBMITTED → APPROVED → COMPLETED
                                                         → CANCELLED

Key design decisions:
  - Auto-loads items from Stock Ledger based on location/category
  - Differences generate Adjustment records (reusing Section 7's adjustment_service)
  - Every status transition is logged in InventoryStockCountHistory
  - Completed counts are read-only
  - Integrates with Stock Ledger for expected quantities
  - Uses transaction.atomic for all state-changing operations
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from inventory.models import (
    InventoryStockCount, InventoryStockCountItem,
    InventoryStockCountHistory,
    StockCountReason, InventoryItem, StockLedger,
    InventoryAdjustmentReason,
)
from inventory.services.stock_engine import (
    get_physical_stock, get_reserved_stock,
)
from inventory.services.adjustment_service import (
    create_adjustment, submit_adjustment,
    approve_adjustment, apply_adjustment,
)
from inventory.services.notification_service import InventoryNotificationService


def _log_history(count, action, from_status, to_status, user, remarks=''):
    """Create a history entry for a stock count action."""
    InventoryStockCountHistory.objects.create(
        count=count,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def generate_count_number(tenant_id, count_date=None):
    """Generate a unique stock count number: CNT-YYYYMMDD-XXXX"""
    from django.db.models import Max
    count_date = count_date or timezone.now().date()
    if hasattr(count_date, 'strftime'):
        date_str = count_date.strftime('%Y%m%d')
    else:
        date_str = str(count_date).replace('-', '')
    prefix = f"CNT-{date_str}-"
    last = InventoryStockCount.objects.filter(
        tenant_id=tenant_id,
        count_number__startswith=prefix,
    ).aggregate(Max('count_number'))
    if last['count_number__max']:
        last_num = int(last['count_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


def _auto_load_items(count):
    """
    Auto-load inventory items based on count location (and optionally category).
    Uses the Stock Ledger to determine expected quantities.
    """
    tenant_id = count.tenant_id
    location_id = count.location_id

    # Build query for items at this location (has ledger entries)
    item_ids = StockLedger.objects.filter(
        tenant_id=tenant_id,
        location_id=location_id,
    ).values_list('item_id', flat=True).distinct()

    items_qs = InventoryItem.objects.filter(
        tenant_id=tenant_id,
        id__in=item_ids,
        status='ACTIVE',
    )

    if count.category_id:
        items_qs = items_qs.filter(category_id=count.category_id)

    created_count = 0
    for item in items_qs:
        # Skip if already loaded
        if InventoryStockCountItem.objects.filter(count=count, item=item).exists():
            continue

        expected = get_physical_stock(item.id, tenant_id, location_id)
        reserved = get_reserved_stock(item.id, tenant_id, location_id)

        InventoryStockCountItem.objects.create(
            count=count,
            item=item,
            expected_quantity=expected,
            reserved_quantity_at_count=reserved,
            unit=item.unit,
        )
        created_count += 1

    return created_count


# ===========================================================================
# MAIN WORKFLOW FUNCTIONS
# ===========================================================================

@transaction.atomic
def create_stock_count(tenant_id, data, created_by):
    """Create a new stock count in DRAFT status, auto-load items."""
    reason = StockCountReason.objects.for_tenant(tenant_id).filter(
        id=data.get('reason')
    ).first()
    if not reason:
        raise ValueError("Stock count reason not found.")

    count = InventoryStockCount.objects.create(
        tenant_id=tenant_id,
        count_number=generate_count_number(tenant_id, data.get('count_date')),
        count_date=data.get('count_date', timezone.now().date()),
        count_type=data.get('count_type', 'CYCLE'),
        location_id=data.get('location'),
        category_id=data.get('category'),
        reason=reason,
        status='DRAFT',
        remarks=data.get('remarks', ''),
        created_by=created_by,
        updated_by=created_by,
    )

    # Assign initial counters if provided
    counter_ids = data.get('assigned_counters', [])
    if counter_ids:
        User = created_by.__class__
        counters = User.objects.filter(id__in=counter_ids)
        count.assigned_counters.set(counters)

    # Auto-load items from ledger for this location
    _auto_load_items(count)

    # Log creation
    _log_history(count, 'CREATED', '', 'DRAFT', created_by)

    # Notify
    InventoryNotificationService.notify_stock_count_event('created', count)

    return count


@transaction.atomic
def update_stock_count(count, data, user):
    """
    Update a stock count in DRAFT or ASSIGNED status.
    Updates location, category, reason, count_date, count_type, and remarks.
    Reloads items if location or category changes.
    """
    if count.status not in ('DRAFT', 'ASSIGNED'):
        raise ValueError(
            f"Cannot update count in status '{count.get_status_display()}'."
        )

    location_changed = False
    category_changed = False

    if 'location' in data and data['location']:
        if str(data['location']) != str(count.location_id):
            count.location_id = data['location']
            location_changed = True

    if 'category' in data:
        new_cat = data.get('category')
        if str(new_cat or '') != str(count.category_id or ''):
            count.category_id = new_cat
            category_changed = True

    if 'reason' in data and data['reason']:
        reason = StockCountReason.objects.for_tenant(count.tenant_id).filter(
            id=data['reason']
        ).first()
        if not reason:
            raise ValueError("Stock count reason not found.")
        count.reason = reason

    if 'count_date' in data:
        count.count_date = data['count_date']

    if 'count_type' in data:
        count.count_type = data['count_type']

    if 'remarks' in data:
        count.remarks = data.get('remarks', '')

    count.updated_by = user
    count.save()

    # Reload items if location or category changed
    if location_changed or category_changed:
        count.items.all().delete()
        _auto_load_items(count)

    _log_history(count, 'UPDATED', count.status, count.status, user)

    return count


@transaction.atomic
def assign_counters(count, user, counter_ids):
    """Assign counters to a stock count (DRAFT only)."""
    if count.status not in ('DRAFT', 'ASSIGNED'):
        raise ValueError(
            f"Cannot assign counters to a count in status '{count.get_status_display()}'."
        )

    User = user.__class__
    counters = User.objects.filter(id__in=counter_ids)
    count.assigned_counters.set(counters)
    count.updated_by = user
    count.save()

    # Auto-transition to ASSIGNED
    old_status = count.status
    if old_status == 'DRAFT':
        count.status = 'ASSIGNED'
        count.save()

    _log_history(count, 'ASSIGNED', old_status, 'ASSIGNED', user)
    InventoryNotificationService.notify_stock_count_event('assigned', count)

    return count


@transaction.atomic
def start_counting(count, user):
    """Start the counting process — transition from ASSIGNED to IN_PROGRESS."""
    if count.status != 'ASSIGNED':
        raise ValueError(
            f"Cannot start counting. Expected status 'ASSIGNED', got '{count.get_status_display()}'."
        )

    # Only assigned counters can start
    if user.role not in ['Superadmin', 'Admin']:
        if not count.assigned_counters.filter(id=user.id).exists():
            raise ValueError("You are not assigned to this stock count.")

    count.status = 'IN_PROGRESS'
    count.updated_by = user
    count.save()

    _log_history(count, 'STARTED', 'ASSIGNED', 'IN_PROGRESS', user)
    InventoryNotificationService.notify_stock_count_event('started', count)

    return count


@transaction.atomic
def save_count_progress(count, user, items_data):
    """
    Save counting progress — record counted quantities for items.
    Can be called multiple times during IN_PROGRESS.
    """
    if count.status != 'IN_PROGRESS':
        raise ValueError(
            f"Cannot save progress. Expected status 'IN_PROGRESS', got '{count.get_status_display()}'."
        )

    # Only assigned counters can record counts
    if user.role not in ['Superadmin', 'Admin']:
        if not count.assigned_counters.filter(id=user.id).exists():
            raise ValueError("You are not assigned to this stock count.")

    now = timezone.now()
    updated_count = 0

    for item_data in items_data:
        item_id = item_data.get('item_id')
        counted_quantity = item_data.get('counted_quantity')

        try:
            count_item = InventoryStockCountItem.objects.get(
                count=count,
                item_id=item_id,
            )
        except InventoryStockCountItem.DoesNotExist:
            raise ValueError(f"Item {item_id} is not part of this stock count.")

        # Calculate difference
        difference = Decimal(str(counted_quantity)) - count_item.expected_quantity

        count_item.counted_quantity = counted_quantity
        count_item.difference_quantity = difference
        count_item.counted_by = user
        count_item.counted_at = now
        count_item.scanned_barcode = item_data.get('scanned_barcode', '')
        count_item.remarks = item_data.get('remarks', '')
        count_item.save()
        updated_count += 1

    # Log progress save
    _log_history(
        count, 'ITEM_COUNTED', 'IN_PROGRESS', 'IN_PROGRESS', user,
        f"Counted {updated_count} item(s)"
    )

    return count


@transaction.atomic
def submit_stock_count(count, user):
    """Submit stock count for approval."""
    if count.status != 'IN_PROGRESS':
        raise ValueError(
            f"Cannot submit. Expected status 'IN_PROGRESS', got '{count.get_status_display()}'."
        )

    # Validate all items are counted
    uncounted = count.items.filter(counted_quantity__isnull=True).count()
    if uncounted > 0:
        raise ValueError(
            f"Cannot submit — {uncounted} item(s) have not been counted yet."
        )

    count.status = 'SUBMITTED'
    count.updated_by = user
    count.save()

    _log_history(count, 'SUBMITTED', 'IN_PROGRESS', 'SUBMITTED', user)
    InventoryNotificationService.notify_stock_count_event('submitted', count)

    return count


@transaction.atomic
def approve_stock_count(count, user, notes=''):
    """Approve a submitted stock count. Transitions to APPROVED."""
    if count.status != 'SUBMITTED':
        raise ValueError(
            f"Cannot approve. Expected status 'SUBMITTED', got '{count.get_status_display()}'."
        )

    count.status = 'APPROVED'
    count.approved_by = user
    count.approved_at = timezone.now()
    count.approval_notes = notes
    count.updated_by = user
    count.save()

    _log_history(count, 'APPROVED', 'SUBMITTED', 'APPROVED', user, notes)
    InventoryNotificationService.notify_stock_count_event('approved', count)

    return count


@transaction.atomic
def complete_stock_count(count, user):
    """
    Complete an approved stock count.
    Generates Adjustment records from differences and transitions to COMPLETED.

    The adjustment is auto-created, submitted, approved, and applied
    so stock ledger gets updated automatically.
    """
    if count.status != 'APPROVED':
        raise ValueError(
            f"Cannot complete. Expected status 'APPROVED', got '{count.get_status_display()}'."
        )

    # Calculate differences and generate adjustments
    adjustment = _generate_adjustment_from_count(count, user)

    count.status = 'COMPLETED'
    count.completed_by = user
    count.completed_at = timezone.now()
    count.generated_adjustment = adjustment
    count.updated_by = user

    # Update difference summary
    count.total_items_counted = count.items.filter(
        counted_quantity__isnull=False
    ).count()
    count.total_items_with_difference = count.items.filter(
        difference_quantity__isnull=False
    ).exclude(difference_quantity=0).count()

    # Calculate total difference value
    total_diff_value = Decimal('0')
    for item in count.items.filter(difference_quantity__isnull=False).exclude(difference_quantity=0):
        cost_price = item.item.cost_price or Decimal('0')
        total_diff_value += abs(item.difference_quantity) * cost_price
    count.total_difference_value = total_diff_value

    count.save()

    _log_history(count, 'COMPLETED', 'APPROVED', 'COMPLETED', user,
                 f"Adjustment {adjustment.adjustment_number} generated")
    _log_history(count, 'ADJUSTMENT_GENERATED', 'COMPLETED', 'COMPLETED', user,
                 f"Auto-generated adjustment: {adjustment.adjustment_number}")

    InventoryNotificationService.notify_stock_count_event('completed', count)

    return count


@transaction.atomic
def _generate_adjustment_from_count(count, user):
    """
    Generate adjustment records from count differences.

    For items with differences:
      - Surplus (counted > expected): INCREASE adjustment.
      - Shortage (counted < expected): DECREASE adjustment.

    Pure-surplus → single INCREASE adjustment.
    Pure-shortage → single DECREASE adjustment.
    Mixed → two separate adjustments (one INCREASE, one DECREASE).

    Adjustment reason codes:
      - STOCK_COUNT_SURPLUS  (INCREASE)
      - STOCK_COUNT_SHORTAGE (DECREASE)
    """
    tenant_id = count.tenant_id
    location_id = count.location_id

    items_with_diff = count.items.exclude(difference_quantity=0).filter(
        counted_quantity__isnull=False
    )

    if not items_with_diff.exists():
        raise ValueError("No differences found — nothing to adjust.")

    surplus_items = items_with_diff.filter(difference_quantity__gt=0)
    shortage_items = items_with_diff.filter(difference_quantity__lt=0)

    # Mixed → delegate to the two-adjustments helper
    if surplus_items.exists() and shortage_items.exists():
        return _create_mixed_adjustments(
            count, user, tenant_id, location_id,
            surplus_items, shortage_items,
        )

    # Build a single adjustment
    if surplus_items.exists():
        reason_code = 'STOCK_COUNT_SURPLUS'
        reason_name = 'Stock Count Surplus'
        adj_type = 'INCREASE'
        items_qs = surplus_items
    else:
        reason_code = 'STOCK_COUNT_SHORTAGE'
        reason_name = 'Stock Count Shortage'
        adj_type = 'DECREASE'
        items_qs = shortage_items

    reason, _ = InventoryAdjustmentReason.objects.get_or_create(
        tenant_id=tenant_id,
        reason_code=reason_code,
        defaults={
            'reason_name': reason_name,
            'adjustment_type': adj_type,
            'description': f'Auto-generated from {reason_name.lower()} in stock count',
            'is_default': True,
            'status': 'ACTIVE',
        },
    )

    items_data = [
        {
            'item_id': item.item_id,
            'adjustment_quantity': abs(item.difference_quantity),
            'unit': item.unit_id,
            'remarks': f"Stock count {reason_code.lower()}: {count.count_number}",
        }
        for item in items_qs
    ]

    adjustment_data = {
        'adjustment_date': count.count_date,
        'location': location_id,
        'reason': reason.id,
        'remarks': f"Auto-generated from stock count {count.count_number}",
        'items': items_data,
    }

    adjustment = create_adjustment(tenant_id, adjustment_data, user)
    submit_adjustment(adjustment, user)
    approve_adjustment(adjustment, user,
                       notes=f"Auto-approved from stock count {count.count_number}")
    apply_adjustment(adjustment, user)

    return adjustment


def _create_mixed_adjustments(count, user, tenant_id, location_id,
                               surplus_items, shortage_items):
    """
    When a stock count has both surpluses and shortages,
    create two separate adjustments.
    """
    # Create INCREASE adjustment for surpluses
    surplus_reason, _ = InventoryAdjustmentReason.objects.get_or_create(
        tenant_id=tenant_id,
        reason_code='STOCK_COUNT_SURPLUS',
        defaults={
            'reason_name': 'Stock Count Surplus',
            'adjustment_type': 'INCREASE',
            'description': 'Auto-generated from stock count surplus differences',
            'is_default': True,
            'status': 'ACTIVE',
        }
    )

    surplus_data = {
        'adjustment_date': count.count_date,
        'location': location_id,
        'reason': surplus_reason.id,
        'remarks': f"Surplus from stock count {count.count_number}",
        'items': [
            {
                'item_id': item.item_id,
                'adjustment_quantity': abs(item.difference_quantity),
                'unit': item.unit_id,
                'remarks': f"Stock count surplus: {count.count_number}",
            }
            for item in surplus_items
        ],
    }

    surplus_adj = create_adjustment(tenant_id, surplus_data, user)
    submit_adjustment(surplus_adj, user)
    approve_adjustment(surplus_adj, user,
                       notes=f"Auto-approved from stock count {count.count_number}")
    apply_adjustment(surplus_adj, user)

    # Create DECREASE adjustment for shortages
    shortage_reason, _ = InventoryAdjustmentReason.objects.get_or_create(
        tenant_id=tenant_id,
        reason_code='STOCK_COUNT_SHORTAGE',
        defaults={
            'reason_name': 'Stock Count Shortage',
            'adjustment_type': 'DECREASE',
            'description': 'Auto-generated from stock count shortage differences',
            'is_default': True,
            'status': 'ACTIVE',
        }
    )

    shortage_data = {
        'adjustment_date': count.count_date,
        'location': location_id,
        'reason': shortage_reason.id,
        'remarks': f"Shortage from stock count {count.count_number}",
        'items': [
            {
                'item_id': item.item_id,
                'adjustment_quantity': abs(item.difference_quantity),
                'unit': item.unit_id,
                'remarks': f"Stock count shortage: {count.count_number}",
            }
            for item in shortage_items
        ],
    }

    shortage_adj = create_adjustment(tenant_id, shortage_data, user)
    submit_adjustment(shortage_adj, user)
    approve_adjustment(shortage_adj, user,
                       notes=f"Auto-approved from stock count {count.count_number}")
    apply_adjustment(shortage_adj, user)

    # Return the surplus adjustment as the primary reference
    return surplus_adj


@transaction.atomic
def cancel_stock_count(count, user):
    """Cancel a stock count (DRAFT, ASSIGNED, or IN_PROGRESS only)."""
    if count.status not in ('DRAFT', 'ASSIGNED', 'IN_PROGRESS'):
        raise ValueError(
            f"Cannot cancel count in status '{count.get_status_display()}'."
        )

    old_status = count.status
    count.status = 'CANCELLED'
    count.updated_by = user
    count.save()

    _log_history(count, 'CANCELLED', old_status, 'CANCELLED', user)
    InventoryNotificationService.notify_stock_count_event('cancelled', count)

    return count


# ===========================================================================
# DIFFERENCE SUMMARY
# ===========================================================================

def get_difference_summary(count):
    """Get a detailed difference summary for a stock count."""
    items = count.items.select_related('item').all()

    summary = []
    for item in items:
        diff = item.difference_quantity
        cost_price = item.item.cost_price or Decimal('0')
        diff_value = abs(diff) * cost_price

        if diff == 0 and item.counted_quantity is not None:
            status = 'MATCH'
        elif diff > 0:
            status = 'SURPLUS'
        elif diff < 0:
            status = 'SHORTAGE'
        else:
            status = 'UNCOUNTED'

        summary.append({
            'item_id': item.item_id,
            'item_code': item.item.item_code,
            'item_name': item.item.item_name,
            'expected_quantity': item.expected_quantity,
            'counted_quantity': item.counted_quantity,
            'difference_quantity': diff,
            'cost_price': cost_price,
            'difference_value': diff_value,
            'status': status,
        })

    totals = {
        'total_items': len(summary),
        'counted_items': sum(1 for s in summary if s['status'] != 'UNCOUNTED'),
        'matching_items': sum(1 for s in summary if s['status'] == 'MATCH'),
        'surplus_items': sum(1 for s in summary if s['status'] == 'SURPLUS'),
        'shortage_items': sum(1 for s in summary if s['status'] == 'SHORTAGE'),
        'uncounted_items': sum(1 for s in summary if s['status'] == 'UNCOUNTED'),
        'total_difference_value': sum(s['difference_value'] for s in summary),
    }

    return {'items': summary, 'totals': totals}


# ===========================================================================
# AUTO-LOAD ITEMS (re-import)
# ===========================================================================

def reload_items_from_ledger(count, user):
    """Reload items from the stock ledger, adding any new ones not yet in the count."""
    if count.status not in ('DRAFT', 'ASSIGNED'):
        raise ValueError(
            f"Cannot reload items for count in status '{count.get_status_display()}'."
        )

    added = _auto_load_items(count)
    count.updated_by = user
    count.save()

    return added
