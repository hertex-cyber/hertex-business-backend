"""
Transfer Service — handles stock transfer workflow, history logging, and notifications.

Every transfer action:
1. Validates the state transition
2. Creates Stock Ledger entries (dispatch/receive)
3. Logs a history entry
4. Sends notifications to relevant parties

Never update stock quantities directly.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from inventory.models import (
    InventoryTransfer, InventoryTransferItem,
    InventoryTransferHistory, InventoryItem, StockLedger,
)
from inventory.services.stock_engine import (
    get_available_stock,
    create_ledger_entry,
)
from inventory.services.notification_service import InventoryNotificationService


def _log_history(transfer, action, from_status, to_status, user, remarks=''):
    """Create a history entry for a transfer action."""
    InventoryTransferHistory.objects.create(
        transfer=transfer,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def generate_transfer_number(tenant_id):
    """Generate a unique transfer number: TRF-YYYYMMDD-XXXX"""
    from django.db.models import Max
    from django.utils import timezone as tz
    today = tz.now().strftime('%Y%m%d')
    prefix = f"TRF-{today}-"
    last = InventoryTransfer.objects.filter(
        tenant_id=tenant_id,
        transfer_number__startswith=prefix,
    ).aggregate(Max('transfer_number'))
    if last['transfer_number__max']:
        last_num = int(last['transfer_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


@transaction.atomic
def create_transfer(tenant_id, data, created_by):
    """Create a new transfer in DRAFT status."""
    items_data = data.pop('items', [])

    transfer = InventoryTransfer.objects.create(
        tenant_id=tenant_id,
        transfer_number=data.get('transfer_number') or generate_transfer_number(tenant_id),
        transfer_date=data.get('transfer_date', timezone.now().date()),
        source_location_id=data.get('source_location'),
        destination_location_id=data.get('destination_location'),
        transfer_type=data.get('transfer_type', 'STANDARD'),
        status='DRAFT',
        remarks=data.get('remarks', ''),
        created_by=created_by,
        updated_by=created_by,
    )

    for item_data in items_data:
        InventoryTransferItem.objects.create(
            transfer=transfer,
            item_id=item_data['item_id'],
            quantity=item_data['quantity'],
            remarks=item_data.get('remarks', ''),
        )

    # Log creation
    _log_history(transfer, 'CREATED', '', 'DRAFT', created_by)

    # Notify on creation
    InventoryNotificationService.notify_event('created', transfer)

    return transfer


@transaction.atomic
def submit_transfer(transfer, user):
    """Submit transfer for approval (or auto-approve if workflow disabled)."""
    if transfer.status != 'DRAFT':
        raise ValueError(f"Cannot submit transfer in status '{transfer.status}'")

    # Lock items and check stock availability
    items = transfer.items.select_related('item').all()
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=transfer.tenant_id
        ).select_for_update()
    )

    for item in items:
        available = get_available_stock(
            item.item_id, transfer.tenant_id, transfer.source_location_id
        )
        if available < item.quantity:
            raise ValueError(
                f"Insufficient stock for '{item.item.item_name}': "
                f"available {available}, requested {item.quantity}"
            )

    transfer.status = 'PENDING_APPROVAL'
    transfer.updated_by = user
    transfer.save()

    # Log submission
    _log_history(transfer, 'SUBMITTED', 'DRAFT', 'PENDING_APPROVAL', user)

    return transfer


@transaction.atomic
def approve_transfer(transfer, user, notes=''):
    """Approve a transfer."""
    if transfer.status != 'PENDING_APPROVAL':
        raise ValueError(f"Cannot approve transfer in status '{transfer.status}'")

    transfer.status = 'APPROVED'
    transfer.approved_by = user
    transfer.approved_at = timezone.now()
    transfer.approval_notes = notes
    transfer.updated_by = user
    transfer.save()

    # Log approval
    _log_history(transfer, 'APPROVED', 'PENDING_APPROVAL', 'APPROVED', user, notes)

    # Notify creator
    InventoryNotificationService.notify_event('approved', transfer)

    return transfer


@transaction.atomic
def reject_transfer(transfer, user, notes=''):
    """Reject a transfer."""
    if transfer.status != 'PENDING_APPROVAL':
        raise ValueError(f"Cannot reject transfer in status '{transfer.status}'")

    transfer.status = 'REJECTED'
    transfer.approved_by = user
    transfer.approved_at = timezone.now()
    transfer.approval_notes = notes
    transfer.updated_by = user
    transfer.save()

    # Log rejection
    _log_history(transfer, 'REJECTED', 'PENDING_APPROVAL', 'REJECTED', user, notes)

    # Notify creator
    InventoryNotificationService.notify_event('rejected', transfer)

    return transfer


@transaction.atomic
def dispatch_transfer(transfer, user):
    """
    Dispatch a transfer — moves stock OUT of source location.
    Creates TRANSFER_OUT ledger entries.
    """
    if transfer.status not in ['APPROVED', 'DRAFT']:
        raise ValueError(f"Cannot dispatch transfer in status '{transfer.status}'")

    # Lock items and check stock availability
    items = transfer.items.select_related('item', 'item__unit').all()
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=transfer.tenant_id
        ).select_for_update()
    )

    for item in items:
        available = get_available_stock(
            item.item_id, transfer.tenant_id, transfer.source_location_id
        )
        if available < item.quantity:
            raise ValueError(
                f"Insufficient stock for '{item.item.item_name}': "
                f"available {available}, requested {item.quantity}"
            )

    # Create TRANSFER_OUT ledger entries
    for item in items:
        create_ledger_entry(
            tenant_id=transfer.tenant_id,
            item_id=item.item_id,
            transaction_type='TRANSFER_OUT',
            quantity=-item.quantity,  # Negative = out
            location_id=transfer.source_location_id,
            reference_type='TRANSFER',
            reference_id=str(transfer.transfer_number),
            description=f"Transfer {transfer.transfer_number} → {transfer.destination_location.location_name}",
            created_by=user,
        )

    old_status = transfer.status
    transfer.status = 'IN_TRANSIT'
    transfer.dispatched_at = timezone.now()
    transfer.updated_by = user
    transfer.save()

    # Log dispatch
    _log_history(transfer, 'DISPATCHED', old_status, 'IN_TRANSIT', user)

    # Notify destination
    InventoryNotificationService.notify_event('dispatched', transfer)

    return transfer


@transaction.atomic
def receive_transfer(transfer, user, received_items=None):
    """
    Receive a transfer — moves stock INTO destination location.
    Creates TRANSFER_IN ledger entries.

    received_items: list of {item_id, received_quantity, damaged_quantity}
    If not provided, full quantity is received.
    """
    if transfer.status != 'IN_TRANSIT':
        raise ValueError(f"Cannot receive transfer in status '{transfer.status}'")

    # Lock destination items
    items = transfer.items.select_related('item', 'item__unit').all()
    item_ids = [i.item_id for i in items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=transfer.tenant_id
        ).select_for_update()
    )

    is_partial = False
    if received_items:
        received_map = {r['item_id']: r for r in received_items}
    else:
        received_map = {}

    for item in items:
        if item.item_id in received_map:
            received_qty = Decimal(str(received_map[item.item_id].get('received_quantity', item.quantity)))
            damaged_qty = Decimal(str(received_map[item.item_id].get('damaged_quantity', 0)))
        else:
            received_qty = item.quantity
            damaged_qty = Decimal('0')

        # Validate
        if received_qty + damaged_qty > item.quantity:
            raise ValueError(
                f"Received + damaged ({received_qty + damaged_qty}) exceeds "
                f"transferred quantity ({item.quantity}) for '{item.item.item_name}'"
            )

        # Update line item
        item.received_quantity = received_qty
        item.damaged_quantity = damaged_qty
        item.save()

        # Create TRANSFER_IN entry for received quantity
        if received_qty > 0:
            create_ledger_entry(
                tenant_id=transfer.tenant_id,
                item_id=item.item_id,
                transaction_type='TRANSFER_IN',
                quantity=received_qty,  # Positive = in
                location_id=transfer.destination_location_id,
                reference_type='TRANSFER',
                reference_id=str(transfer.transfer_number),
                description=f"Received from {transfer.source_location.location_name} via {transfer.transfer_number}",
                created_by=user,
            )

        # Create DAMAGE entry for damaged quantity
        if damaged_qty > 0:
            create_ledger_entry(
                tenant_id=transfer.tenant_id,
                item_id=item.item_id,
                transaction_type='DAMAGE',
                quantity=-damaged_qty,
                location_id=transfer.destination_location_id,
                reference_type='TRANSFER',
                reference_id=str(transfer.transfer_number),
                description=f"Damaged during transfer {transfer.transfer_number}",
                created_by=user,
            )

        # Check if partial
        if received_qty < item.quantity:
            is_partial = True

    transfer.status = 'PARTIALLY_RECEIVED' if is_partial else 'RECEIVED'
    transfer.received_at = timezone.now()
    transfer.received_by = user
    transfer.updated_by = user
    transfer.save()

    # If fully received, mark completed
    if not is_partial:
        transfer.status = 'COMPLETED'
        transfer.save()

    # Log receipt
    action = 'PARTIALLY_RECEIVED' if is_partial else 'COMPLETED'
    _log_history(transfer, action, 'IN_TRANSIT', transfer.status, user)

    # Notify creator
    InventoryNotificationService.notify_event('received', transfer)

    return transfer


@transaction.atomic
def cancel_transfer(transfer, user):
    """Cancel a transfer (only allowed in DRAFT or PENDING_APPROVAL)."""
    if transfer.status not in ['DRAFT', 'PENDING_APPROVAL']:
        raise ValueError(f"Cannot cancel transfer in status '{transfer.status}'")

    old_status = transfer.status
    transfer.status = 'CANCELLED'
    transfer.updated_by = user
    transfer.save()

    # Log cancellation
    _log_history(transfer, 'CANCELLED', old_status, 'CANCELLED', user)

    return transfer
