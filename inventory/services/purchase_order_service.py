"""
Purchase Order Service — handles purchase order workflow, receipt, stock ledger integration,
history logging, and notifications.

Workflow:
    DRAFT → SENT → PARTIALLY_RECEIVED → RECEIVED → CLOSED
                                              → CANCELLED

Every purchase action:
1. Validates the state transition
2. Creates Stock Ledger entries (PURCHASE_IN on receipt)
3. Logs a history entry
4. Sends notifications to relevant parties

Never update stock quantities directly.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from inventory.models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory,
    PurchaseReceipt, PurchaseReceiptItem, InventoryItem,
)
from inventory.services.stock_engine import create_ledger_entry
from inventory.services.notification_service import InventoryNotificationService


def _log_history(purchase_order, action, from_status, to_status, user, remarks=''):
    """Create a history entry for a purchase order action."""
    PurchaseOrderHistory.objects.create(
        purchase_order=purchase_order,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def generate_order_number(tenant_id):
    """Generate a unique purchase order number: PO-YYYYMMDD-XXXX"""
    from django.db.models import Max
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"PO-{today}-"
    last = PurchaseOrder.objects.filter(
        tenant_id=tenant_id,
        order_number__startswith=prefix,
    ).aggregate(Max('order_number'))
    if last['order_number__max']:
        last_num = int(last['order_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


def generate_receipt_number(tenant_id):
    """Generate a unique receipt number: GRN-YYYYMMDD-XXXX"""
    from django.db.models import Max
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"GRN-{today}-"
    last = PurchaseReceipt.objects.filter(
        tenant_id=tenant_id,
        receipt_number__startswith=prefix,
    ).aggregate(Max('receipt_number'))
    if last['receipt_number__max']:
        last_num = int(last['receipt_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


@transaction.atomic
def create_purchase_order(tenant_id, data, created_by):
    """Create a new purchase order in DRAFT status."""
    items_data = data.pop('items', [])

    # Calculate total from items
    subtotal = Decimal('0')
    total_amount = Decimal('0')
    tax_amount = Decimal(str(data.get('tax_amount', 0)))
    discount_amount = Decimal(str(data.get('discount_amount', 0)))

    purchase_order = PurchaseOrder.objects.create(
        tenant_id=tenant_id,
        order_number=data.get('order_number') or generate_order_number(tenant_id),
        order_date=data.get('order_date', timezone.now().date()),
        expected_delivery_date=data.get('expected_delivery_date'),
        supplier_id=data.get('supplier'),
        location_id=data.get('location'),
        supplier_name=data.get('supplier_name', ''),
        supplier_reference=data.get('supplier_reference', ''),
        status='DRAFT',
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        subtotal=data.get('subtotal', total_amount),
        total_amount=total_amount,
        notes=data.get('notes', ''),
        terms=data.get('terms', ''),
        created_by=created_by,
        updated_by=created_by,
    )

    for item_data in items_data:
        quantity = Decimal(str(item_data['quantity']))
        unit_price = Decimal(str(item_data.get('unit_price', 0)))
        line_tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
        line_discount_rate = Decimal(str(item_data.get('discount_rate', 0)))
        line_subtotal = quantity * unit_price
        line_total = line_subtotal * (1 + line_tax_rate / 100) * (1 - line_discount_rate / 100)

        PurchaseOrderItem.objects.create(
            purchase_order=purchase_order,
            item_id=item_data['item_id'],
            ordered_quantity=quantity,
            unit_price=unit_price,
            tax_rate=line_tax_rate,
            discount_rate=line_discount_rate,
            line_total=line_total,
            remarks=item_data.get('remarks', ''),
        )
        subtotal += line_subtotal
        total_amount += line_total

    # Update totals
    purchase_order.subtotal = subtotal
    purchase_order.total_amount = total_amount
    purchase_order.save(update_fields=['subtotal', 'total_amount'])

    # Log creation
    _log_history(purchase_order, 'CREATED', '', 'DRAFT', created_by)

    # Notify
    InventoryNotificationService.notify_purchase_event('created', purchase_order)

    return purchase_order


@transaction.atomic
def update_purchase_order(purchase_order, data, user):
    """Update a DRAFT purchase order."""
    if purchase_order.status not in ('DRAFT',):
        raise ValueError(f"Cannot update a purchase order in status '{purchase_order.status}'")

    items_data = data.pop('items', [])

    # Update fields
    if 'order_date' in data:
        purchase_order.order_date = data['order_date']
    if 'expected_delivery_date' in data:
        purchase_order.expected_delivery_date = data.get('expected_delivery_date')
    if 'supplier' in data:
        purchase_order.supplier_id = data['supplier']
    if 'supplier_name' in data:
        purchase_order.supplier_name = data['supplier_name']
    if 'supplier_reference' in data:
        purchase_order.supplier_reference = data['supplier_reference']
    if 'location' in data:
        purchase_order.location_id = data['location']
    if 'notes' in data:
        purchase_order.notes = data['notes']
    if 'terms' in data:
        purchase_order.terms = data['terms']
    if 'tax_amount' in data:
        purchase_order.tax_amount = Decimal(str(data['tax_amount']))
    if 'discount_amount' in data:
        purchase_order.discount_amount = Decimal(str(data['discount_amount']))

    purchase_order.updated_by = user
    purchase_order.save()

    # Replace items
    if items_data:
        purchase_order.items.all().delete()
        subtotal = Decimal('0')
        total_amount = Decimal('0')
        for item_data in items_data:
            quantity = Decimal(str(item_data['quantity']))
            unit_price = Decimal(str(item_data.get('unit_price', 0)))
            line_tax_rate = Decimal(str(item_data.get('tax_rate', 0)))
            line_discount_rate = Decimal(str(item_data.get('discount_rate', 0)))
            line_subtotal = quantity * unit_price
            line_total = line_subtotal * (1 + line_tax_rate / 100) * (1 - line_discount_rate / 100)

            PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                item_id=item_data['item_id'],
                ordered_quantity=quantity,
                unit_price=unit_price,
                tax_rate=line_tax_rate,
                discount_rate=line_discount_rate,
                line_total=line_total,
                remarks=item_data.get('remarks', ''),
            )
            subtotal += line_subtotal
            total_amount += line_total

        purchase_order.subtotal = subtotal
        purchase_order.total_amount = total_amount
        purchase_order.save(update_fields=['subtotal', 'total_amount'])

    _log_history(purchase_order, 'UPDATED', 'DRAFT', 'DRAFT', user)
    return purchase_order


@transaction.atomic
def send_purchase_order(purchase_order, user):
    """Send a purchase order to the supplier (DRAFT → SENT)."""
    if purchase_order.status != 'DRAFT':
        raise ValueError(f"Cannot send a purchase order in status '{purchase_order.status}'")

    if not purchase_order.items.exists():
        raise ValueError("Cannot send a purchase order with no items.")

    old_status = purchase_order.status
    purchase_order.status = 'SENT'
    purchase_order.sent_at = timezone.now()
    purchase_order.updated_by = user
    purchase_order.save()

    _log_history(purchase_order, 'SENT', old_status, 'SENT', user)
    InventoryNotificationService.notify_purchase_event('sent', purchase_order)

    return purchase_order


@transaction.atomic
def receive_purchase_order_items(purchase_order, user, receipt_items):
    """
    Receive items against a purchase order.

    Creates PURCHASE_IN stock ledger entries for received quantities.
    Supports partial receiving.

    receipt_items: list of {
        item_id: UUID,
        ordered_item_id: UUID (PurchaseOrderItem id),
        received_quantity: Decimal,
        unit_price: Decimal (optional, uses PO price if not provided)
    }

    Creates PurchaseReceipt and PurchaseReceiptItem records.
    """
    if purchase_order.status not in ('SENT', 'PARTIALLY_RECEIVED'):
        raise ValueError(
            f"Cannot receive items for a purchase order in status '{purchase_order.status}'"
        )

    # Lock items being received
    po_items = purchase_order.items.select_related('item').all()
    item_ids = [i.item_id for i in po_items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=purchase_order.tenant_id
        ).select_for_update()
    )

    is_partial = False
    total_received_this_batch = Decimal('0')

    # Create receipt
    receipt = PurchaseReceipt.objects.create(
        tenant_id=purchase_order.tenant_id,
        receipt_number=generate_receipt_number(purchase_order.tenant_id),
        receipt_date=timezone.now().date(),
        purchase_order=purchase_order,
        location_id=purchase_order.location_id,
        notes='',
        created_by=user,
    )

    received_map = {str(r['ordered_item_id']): r for r in receipt_items}

    for po_item in purchase_order.items.all():
        po_item_id_str = str(po_item.id)
        if po_item_id_str in received_map:
            receipt_data = received_map[po_item_id_str]
            received_qty = Decimal(str(receipt_data.get('received_quantity', 0)))
            unit_price = Decimal(str(receipt_data.get('unit_price', po_item.unit_price)))
        else:
            continue  # Skip items not in this receipt

        if received_qty <= 0:
            raise ValueError(f"Received quantity must be greater than 0 for '{po_item.item.item_name}'.")

        # Prevent over-receiving
        new_total_received = po_item.received_quantity + received_qty
        if new_total_received > po_item.ordered_quantity:
            raise ValueError(
                f"Cannot receive {received_qty} for '{po_item.item.item_name}': "
                f"ordered {po_item.ordered_quantity}, already received {po_item.received_quantity}, "
                f"total would be {new_total_received}."
            )

        # Update PO item received quantity
        po_item.received_quantity = new_total_received
        po_item.save(update_fields=['received_quantity'])

        # Create receipt item
        PurchaseReceiptItem.objects.create(
            purchase_receipt=receipt,
            purchase_order_item=po_item,
            item=po_item.item,
            received_quantity=received_qty,
            unit_price=unit_price,
        )

        # Create stock ledger entry (PURCHASE_IN)
        create_ledger_entry(
            tenant_id=purchase_order.tenant_id,
            item_id=po_item.item_id,
            transaction_type='PURCHASE_IN',
            quantity=received_qty,  # Positive = stock increase
            location_id=purchase_order.location_id,
            unit_cost=unit_price,
            total_cost=unit_price * received_qty,
            reference_type='PURCHASE_ORDER',
            reference_id=str(purchase_order.order_number),
            description=f"Purchase Receipt {receipt.receipt_number} — {purchase_order.order_number}",
            created_by=user,
        )

        total_received_this_batch += received_qty * unit_price

        # Check if partial
        if new_total_received < po_item.ordered_quantity:
            is_partial = True

    # Update PO status
    old_status = purchase_order.status
    all_fully_received = all(
        item.received_quantity >= item.ordered_quantity
        for item in purchase_order.items.all()
    )

    if all_fully_received:
        purchase_order.status = 'RECEIVED'
    else:
        purchase_order.status = 'PARTIALLY_RECEIVED'

    purchase_order.updated_by = user
    purchase_order.save()

    # Previous status for accurate history logging
    from_status = 'SENT' if old_status == 'SENT' else 'PARTIALLY_RECEIVED'

    _log_history(
        purchase_order,
        'RECEIVED' if all_fully_received else 'PARTIALLY_RECEIVED',
        from_status,
        purchase_order.status,
        user,
        f"Receipt: {receipt.receipt_number}",
    )

    InventoryNotificationService.notify_purchase_event('received', purchase_order)

    return purchase_order, receipt


@transaction.atomic
def close_purchase_order(purchase_order, user):
    """Close a fully received purchase order."""
    if purchase_order.status != 'RECEIVED':
        raise ValueError(f"Cannot close a purchase order in status '{purchase_order.status}'")

    # Verify all items are fully received
    for item in purchase_order.items.all():
        if item.received_quantity < item.ordered_quantity:
            raise ValueError(
                f"Cannot close purchase order '{purchase_order.order_number}': "
                f"item '{item.item.item_code}' has outstanding quantity "
                f"({item.received_quantity} of {item.ordered_quantity} received)."
            )

    old_status = purchase_order.status
    purchase_order.status = 'CLOSED'
    purchase_order.closed_at = timezone.now()
    purchase_order.updated_by = user
    purchase_order.save()

    _log_history(purchase_order, 'CLOSED', old_status, 'CLOSED', user)
    InventoryNotificationService.notify_purchase_event('closed', purchase_order)

    return purchase_order


@transaction.atomic
def cancel_purchase_order(purchase_order, user):
    """Cancel a purchase order (DRAFT, SENT, or PARTIALLY_RECEIVED only)."""
    if purchase_order.status not in ('DRAFT', 'SENT', 'PARTIALLY_RECEIVED'):
        raise ValueError(f"Cannot cancel a purchase order in status '{purchase_order.status}'")

    old_status = purchase_order.status
    purchase_order.status = 'CANCELLED'
    purchase_order.updated_by = user
    purchase_order.save()

    _log_history(purchase_order, 'CANCELLED', old_status, 'CANCELLED', user)
    InventoryNotificationService.notify_purchase_event('cancelled', purchase_order)

    return purchase_order
