"""
Reservation Service — handles stock reservation workflow, history logging, and notifications.

Every reservation action:
1. Validates the state transition
2. Creates Stock Ledger entries (RESERVATION / RESERVATION_RELEASE)
3. Logs a history entry
4. Sends notifications to relevant parties

Never update stock quantities directly.
Always use the Stock Ledger Engine.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from inventory.models import (
    InventoryReservation, InventoryReservationItem,
    InventoryReservationHistory, InventoryItem, StockLedger,
)
from inventory.services.stock_engine import (
    get_available_stock,
    create_ledger_entry,
)
from inventory.services.notification_service import InventoryNotificationService


def _log_history(reservation, action, from_status, to_status, user, remarks=''):
    """Create a history entry for a reservation action."""
    InventoryReservationHistory.objects.create(
        reservation=reservation,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def generate_reservation_number(tenant_id):
    """Generate a unique reservation number: RSV-YYYYMMDD-XXXX"""
    from django.db.models import Max
    from django.utils import timezone as tz
    today = tz.now().strftime('%Y%m%d')
    prefix = f"RSV-{today}-"
    last = InventoryReservation.objects.filter(
        tenant_id=tenant_id,
        reservation_number__startswith=prefix,
    ).aggregate(Max('reservation_number'))
    if last['reservation_number__max']:
        last_num = int(last['reservation_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


def _validate_available_stock(reservation, user):
    """Check that all items have sufficient available stock for reservation."""
    for item in reservation.items.all():
        available = get_available_stock(
            item.item_id, reservation.tenant_id, reservation.source_location_id
        )
        # requested_quantity is what we want to reserve
        to_reserve = item.requested_quantity - item.reserved_quantity
        if to_reserve > 0 and available < to_reserve:
            raise ValueError(
                f"Insufficient stock for '{item.item.item_name}': "
                f"available {available}, requested {to_reserve}"
            )


# ===========================================================================
# VALID STATUS TRANSITIONS
# ===========================================================================

VALID_TRANSITIONS = {
    'DRAFT': ['ACTIVE', 'CANCELLED'],
    'ACTIVE': ['PARTIALLY_FULFILLED', 'FULFILLED', 'CANCELLED', 'EXPIRED'],
    'PARTIALLY_FULFILLED': ['FULFILLED', 'CANCELLED'],
    'FULFILLED': [],
    'CANCELLED': [],
    'EXPIRED': [],
}


def _validate_transition(reservation, new_status):
    """Validate that the status transition is allowed."""
    allowed = VALID_TRANSITIONS.get(reservation.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{reservation.get_status_display()}' "
            f"to '{dict(InventoryReservation.RESERVATION_STATUSES).get(new_status, new_status)}'."
        )


# ===========================================================================
# SERVICE FUNCTIONS
# ===========================================================================

@transaction.atomic
def create_reservation(tenant_id, data, created_by):
    """Create a new reservation in DRAFT status."""
    items_data = data.pop('items', [])
    reason_id = data.pop('reason', None)

    # Validate no duplicate items
    item_ids = [i['item_id'] for i in items_data]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("Duplicate item rows are not allowed.")

    reservation = InventoryReservation.objects.create(
        tenant_id=tenant_id,
        reservation_number=generate_reservation_number(tenant_id),
        reservation_date=data.get('reservation_date', timezone.now().date()),
        expiry_date=data.get('expiry_date'),
        source_location_id=data.get('source_location'),
        reservation_type=data.get('reservation_type', 'OTHER'),
        priority=data.get('priority', 'MEDIUM'),
        customer_name=data.get('customer_name', ''),
        reference_number=data.get('reference_number', ''),
        reason_id=reason_id,
        remarks=data.get('remarks', ''),
        status='DRAFT',
        created_by=created_by,
        updated_by=created_by,
    )

    for item_data in items_data:
        InventoryReservationItem.objects.create(
            reservation=reservation,
            item_id=item_data['item_id'],
            requested_quantity=item_data['requested_quantity'],
            reserved_quantity=0,
            fulfilled_quantity=0,
            unit_id=item_data.get('unit_id'),
            remarks=item_data.get('remarks', ''),
        )

    _log_history(reservation, 'CREATED', '', 'DRAFT', created_by)
    InventoryNotificationService.notify_reservation_event('created', reservation)

    return reservation


@transaction.atomic
def update_reservation(reservation, data, user):
    """Update a DRAFT reservation."""
    if reservation.status != 'DRAFT':
        raise ValueError(f"Cannot update reservation in status '{reservation.status}'")

    # Update top-level fields
    if 'reservation_date' in data:
        reservation.reservation_date = data['reservation_date']
    if 'expiry_date' in data:
        reservation.expiry_date = data.get('expiry_date')
    if 'source_location' in data:
        reservation.source_location_id = data['source_location']
    if 'reservation_type' in data:
        reservation.reservation_type = data['reservation_type']
    if 'priority' in data:
        reservation.priority = data['priority']
    if 'customer_name' in data:
        reservation.customer_name = data.get('customer_name', '')
    if 'reference_number' in data:
        reservation.reference_number = data.get('reference_number', '')
    if 'reason' in data:
        reservation.reason_id = data.get('reason')
    if 'remarks' in data:
        reservation.remarks = data.get('remarks', '')

    # Update items
    items_data = data.get('items')
    if items_data is not None:
        # Validate no duplicate items
        item_ids = [i['item_id'] for i in items_data]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate item rows are not allowed.")
        # Remove existing items and recreate
        reservation.items.all().delete()
        for item_data in items_data:
            InventoryReservationItem.objects.create(
                reservation=reservation,
                item_id=item_data['item_id'],
                requested_quantity=item_data['requested_quantity'],
                reserved_quantity=0,
                fulfilled_quantity=0,
                unit_id=item_data.get('unit_id'),
                remarks=item_data.get('remarks', ''),
            )

    reservation.updated_by = user
    reservation.save()

    _log_history(reservation, 'UPDATED', 'DRAFT', 'DRAFT', user)
    return reservation


@transaction.atomic
def activate_reservation(reservation, user):
    """
    Activate a reservation — creates RESERVATION ledger entries.
    Increases Reserved Stock, decreases Available Stock.
    Physical Stock remains unchanged.
    """
    _validate_transition(reservation, 'ACTIVE')

    # Lock items and check stock availability
    items = list(reservation.items.select_related('item').all())
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=reservation.tenant_id
        ).select_for_update()
    )
    _validate_available_stock(reservation, user)

    old_status = reservation.status

    # Create RESERVATION ledger entries
    for item in items:
        to_reserve = item.requested_quantity - item.reserved_quantity
        if to_reserve > 0:
            create_ledger_entry(
                tenant_id=reservation.tenant_id,
                item_id=item.item_id,
                transaction_type='RESERVATION',
                quantity=to_reserve,  # Positive = reserved
                location_id=reservation.source_location_id,
                reference_type='RESERVATION',
                reference_id=str(reservation.reservation_number),
                description=f"Reservation {reservation.reservation_number}: {item.item.item_name}",
                created_by=user,
            )
            # Update item reserved quantity
            item.reserved_quantity += to_reserve
            item.save()

    reservation.status = 'ACTIVE'
    reservation.updated_by = user
    reservation.save()

    _log_history(reservation, 'ACTIVATED', old_status, 'ACTIVE', user)
    InventoryNotificationService.notify_reservation_event('activated', reservation)

    return reservation


@transaction.atomic
def fulfill_reservation(reservation, user, fulfillment_items=None):
    """
    Fulfill a reservation — releases reserved stock.
    Creates RESERVATION_RELEASE ledger entries.
    Physical stock movement must be handled via existing inventory transaction logic.

    fulfillment_items: list of {item_id, fulfilled_quantity}
    """
    if reservation.status not in ['ACTIVE', 'PARTIALLY_FULFILLED']:
        raise ValueError(f"Cannot fulfill reservation in status '{reservation.status}'")

    # Lock items
    items = list(reservation.items.select_related('item').all())
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=reservation.tenant_id
        ).select_for_update()
    )

    is_partial = False

    if fulfillment_items:
        fulfill_map = {str(f['item_id']): f for f in fulfillment_items}
    else:
        fulfill_map = {}

    for item in items:
        item_key = str(item.item_id)
        if item_key in fulfill_map:
            fulfill_qty = Decimal(str(fulfill_map[item_key].get('fulfilled_quantity', item.remaining_quantity)))
        else:
            fulfill_qty = item.remaining_quantity

        # Validate
        if fulfill_qty <= 0:
            continue

        if fulfill_qty > item.remaining_quantity:
            raise ValueError(
                f"Fulfilled quantity ({fulfill_qty}) exceeds remaining quantity "
                f"({item.remaining_quantity}) for '{item.item.item_name}'"
            )

        # Release reserved stock (negative reverses the RESERVATION entry)
        create_ledger_entry(
            tenant_id=reservation.tenant_id,
            item_id=item.item_id,
            transaction_type='RESERVATION_RELEASE',
            quantity=-fulfill_qty,  # Negative = release
            location_id=reservation.source_location_id,
            reference_type='RESERVATION',
            reference_id=str(reservation.reservation_number),
            description=f"Fulfilled {fulfill_qty} of {item.item.item_name} from reservation {reservation.reservation_number}",
            created_by=user,
        )

        # Update item
        item.fulfilled_quantity += fulfill_qty
        item.reserved_quantity -= fulfill_qty
        item.save()

        if item.remaining_quantity > 0:
            is_partial = True

    old_status = reservation.status
    new_status = 'PARTIALLY_FULFILLED' if is_partial else 'FULFILLED'
    reservation.status = new_status
    reservation.updated_by = user
    reservation.save()

    action = 'PARTIALLY_FULFILLED' if is_partial else 'FULFILLED'
    _log_history(reservation, action, old_status, new_status, user)
    InventoryNotificationService.notify_reservation_event('fulfilled', reservation)

    return reservation


@transaction.atomic
def cancel_reservation(reservation, user):
    """
    Cancel a reservation — releases reserved stock.
    Creates RESERVATION_RELEASE ledger entries for any reserved stock.
    """
    _validate_transition(reservation, 'CANCELLED')

    # Lock items
    items = list(reservation.items.select_related('item').all())
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=reservation.tenant_id
        ).select_for_update()
    )

    old_status = reservation.status

    # Release any reserved stock
    for item in items:
        if item.reserved_quantity > 0:
            create_ledger_entry(
                tenant_id=reservation.tenant_id,
                item_id=item.item_id,
                transaction_type='RESERVATION_RELEASE',
                quantity=-item.reserved_quantity,
                location_id=reservation.source_location_id,
                reference_type='RESERVATION',
                reference_id=str(reservation.reservation_number),
                description=f"Cancelled reservation {reservation.reservation_number}: {item.item.item_name}",
                created_by=user,
            )
            item.reserved_quantity = 0
            item.save()

    reservation.status = 'CANCELLED'
    reservation.updated_by = user
    reservation.save()

    _log_history(reservation, 'CANCELLED', old_status, 'CANCELLED', user)
    InventoryNotificationService.notify_reservation_event('cancelled', reservation)

    return reservation


@transaction.atomic
def expire_reservation(reservation, user=None):
    """
    Expire a reservation — releases reserved stock.
    Creates RESERVATION_RELEASE ledger entries.
    """
    _validate_transition(reservation, 'EXPIRED')

    # Lock items
    items = list(reservation.items.select_related('item').all())
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=reservation.tenant_id
        ).select_for_update()
    )

    old_status = reservation.status

    # Release any reserved stock
    for item in items:
        if item.reserved_quantity > 0:
            create_ledger_entry(
                tenant_id=reservation.tenant_id,
                item_id=item.item_id,
                transaction_type='RESERVATION_RELEASE',
                quantity=-item.reserved_quantity,
                location_id=reservation.source_location_id,
                reference_type='RESERVATION',
                reference_id=str(reservation.reservation_number),
                description=f"Expired reservation {reservation.reservation_number}: {item.item.item_name}",
                created_by=user,
            )
            item.reserved_quantity = 0
            item.save()

    reservation.status = 'EXPIRED'
    reservation.updated_by = user
    reservation.save()

    _log_history(reservation, 'EXPIRED', old_status, 'EXPIRED', user, 'Auto-expired')
    InventoryNotificationService.notify_reservation_event('expired', reservation)

    return reservation


def bulk_cancel_reservations(tenant_id, reservation_ids, user):
    """Cancel multiple reservations at once."""
    results = []
    reservations = InventoryReservation.objects.filter(
        tenant_id=tenant_id,
        id__in=reservation_ids,
    )
    for reservation in reservations:
        try:
            cancel_reservation(reservation, user)
            results.append({
                'id': str(reservation.id),
                'reservation_number': reservation.reservation_number,
                'status': 'CANCELLED',
                'success': True,
            })
        except ValueError as e:
            results.append({
                'id': str(reservation.id),
                'reservation_number': reservation.reservation_number,
                'status': reservation.status,
                'success': False,
                'error': str(e),
            })
    return results
