"""
Goods Receipt Note (GRN) Service — handles GRN workflow, stock ledger integration,
history logging, notifications, and Purchase Order integration.

Workflow:
    DRAFT → PENDING_APPROVAL → APPROVED → RECEIVED → COMPLETED
                                                → CANCELLED

Business Rules:
1. Cannot receive more than ordered quantity on the PO.
2. Support multiple GRNs against one Purchase Order.
3. Automatically update PO received quantity.
4. Automatically complete PO when all quantities are received.
5. Create Stock Ledger entries (GOODS_RECEIPT).
6. Update Stock Summary via Stock Ledger Engine.
7. Record complete audit history.
8. Generate notifications.
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from inventory.models import (
    InventoryGoodsReceipt, InventoryGoodsReceiptItem,
    InventoryGoodsReceiptHistory, InventoryGoodsReceiptAttachment,
    InventoryItem, PurchaseOrder, PurchaseOrderItem,
)
from inventory.services.stock_engine import create_ledger_entry
from inventory.services.notification_service import InventoryNotificationService


def _log_history(grn, action, from_status, to_status, user, remarks=''):
    """Create a history entry for a GRN action."""
    InventoryGoodsReceiptHistory.objects.create(
        goods_receipt=grn,
        action=action,
        from_status=from_status,
        to_status=to_status,
        performed_by=user,
        remarks=remarks,
    )


def _update_po_received_quantity(purchase_order):
    """Recalculate PO item received quantities from all GRNs."""
    for po_item in PurchaseOrderItem.objects.filter(purchase_order=purchase_order):
        total_received = InventoryGoodsReceiptItem.objects.filter(
            purchase_order_item=po_item,
            goods_receipt__status__in=['RECEIVED', 'COMPLETED'],
            goods_receipt__purchase_order=purchase_order,
        ).aggregate(total=Sum('received_quantity'))['total'] or Decimal('0')

        po_item.received_quantity = total_received
        po_item.save(update_fields=['received_quantity'])

    # Update PO status based on receiving progress
    all_items = list(purchase_order.items.all())
    if not all_items:
        return

    all_fully_received = all(
        item.received_quantity >= item.ordered_quantity
        for item in all_items
    )
    any_received = any(item.received_quantity > 0 for item in all_items)

    if all_fully_received:
        if purchase_order.status != 'RECEIVED':
            purchase_order.status = 'RECEIVED'
            purchase_order.save(update_fields=['status'])
    elif any_received:
        if purchase_order.status not in ('RECEIVED', 'PARTIALLY_RECEIVED'):
            purchase_order.status = 'PARTIALLY_RECEIVED'
            purchase_order.save(update_fields=['status'])


def generate_grn_number(tenant_id):
    """Generate a unique GRN number: GRN-YYYYMMDD-XXXX"""
    from django.db.models import Max
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"GRN-{today}-"
    last = InventoryGoodsReceipt.objects.filter(
        tenant_id=tenant_id,
        grn_number__startswith=prefix,
    ).aggregate(Max('grn_number'))
    if last['grn_number__max']:
        last_num = int(last['grn_number__max'].split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f"{prefix}{new_num:04d}"


@transaction.atomic
def create_grn(tenant_id, data, created_by):
    """Create a new GRN in DRAFT status."""
    items_data = data.pop('items', [])

    purchase_order_id = data.get('purchase_order')
    purchase_order = PurchaseOrder.objects.get(id=purchase_order_id, tenant_id=tenant_id)

    supplier_id = data.get('supplier')
    supplier_name = ''
    if supplier_id:
        from contacts.models import Contact
        try:
            supplier = Contact.objects.get(id=supplier_id)
            supplier_name = supplier.name
        except Contact.DoesNotExist:
            pass
    elif purchase_order.supplier_id:
        supplier_id = str(purchase_order.supplier_id)
        supplier_name = purchase_order.supplier_name

    grn = InventoryGoodsReceipt.objects.create(
        tenant_id=tenant_id,
        grn_number=data.get('grn_number') or generate_grn_number(tenant_id),
        receipt_date=data.get('receipt_date', timezone.now().date()),
        purchase_order=purchase_order,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        location_id=data.get('location', purchase_order.location_id),
        status='DRAFT',
        remarks=data.get('remarks', ''),
        created_by=created_by,
        updated_by=created_by,
    )

    po_item_map = {}
    for po_item in purchase_order.items.all():
        po_item_map[str(po_item.id)] = po_item
        po_item_map[str(po_item.item_id)] = po_item

    for item_data in items_data:
        po_item_id = item_data.get('purchase_order_item')
        item_id = item_data.get('item_id')

        po_item = po_item_map.get(po_item_id) if po_item_id else po_item_map.get(item_id)

        received_qty = Decimal(str(item_data.get('received_quantity', 0)))
        accepted_qty = Decimal(str(item_data.get('accepted_quantity', 0)))
        rejected_qty = Decimal(str(item_data.get('rejected_quantity', 0)))
        damage_qty = Decimal(str(item_data.get('damage_quantity', 0)))

        if received_qty <= 0:
            raise ValueError("Received quantity must be greater than 0.")

        ordered_qty = po_item.ordered_quantity if po_item else received_qty
        unit_price = po_item.unit_price if po_item else Decimal(str(item_data.get('unit_price', 0)))

        InventoryGoodsReceiptItem.objects.create(
            goods_receipt=grn,
            item_id=item_data.get('item_id', po_item.item_id if po_item else item_data['item_id']),
            purchase_order_item=po_item,
            ordered_quantity=ordered_qty,
            received_quantity=received_qty,
            accepted_quantity=accepted_qty or received_qty,
            rejected_quantity=rejected_qty,
            damage_quantity=damage_qty,
            unit_price=unit_price,
            remarks=item_data.get('remarks', ''),
        )

    _log_history(grn, 'CREATED', '', 'DRAFT', created_by)
    InventoryNotificationService.notify_grn_event('created', grn)

    return grn


@transaction.atomic
def update_grn(grn, data, user):
    """Update a DRAFT GRN."""
    if grn.status != 'DRAFT':
        raise ValueError(f"Cannot update a GRN in status '{grn.status}'")

    items_data = data.pop('items', None)

    if 'receipt_date' in data:
        grn.receipt_date = data['receipt_date']
    if 'location' in data:
        grn.location_id = data['location']
    if 'remarks' in data:
        grn.remarks = data['remarks']

    grn.updated_by = user
    grn.save()

    if items_data is not None:
        grn.items.all().delete()
        purchase_order = grn.purchase_order
        po_item_map = {}
        for po_item in purchase_order.items.all():
            po_item_map[str(po_item.id)] = po_item
            po_item_map[str(po_item.item_id)] = po_item

        for item_data in items_data:
            po_item_id = item_data.get('purchase_order_item')
            item_id = item_data.get('item_id')
            po_item = po_item_map.get(po_item_id) if po_item_id else po_item_map.get(item_id)

            received_qty = Decimal(str(item_data.get('received_quantity', 0)))
            accepted_qty = Decimal(str(item_data.get('accepted_quantity', 0)))
            rejected_qty = Decimal(str(item_data.get('rejected_quantity', 0)))
            damage_qty = Decimal(str(item_data.get('damage_quantity', 0)))

            if received_qty <= 0:
                raise ValueError("Received quantity must be greater than 0.")

            ordered_qty = po_item.ordered_quantity if po_item else received_qty
            unit_price = po_item.unit_price if po_item else Decimal(str(item_data.get('unit_price', 0)))

            InventoryGoodsReceiptItem.objects.create(
                goods_receipt=grn,
                item_id=item_data.get('item_id', po_item.item_id if po_item else item_data['item_id']),
                purchase_order_item=po_item,
                ordered_quantity=ordered_qty,
                received_quantity=received_qty,
                accepted_quantity=accepted_qty or received_qty,
                rejected_quantity=rejected_qty,
                damage_quantity=damage_qty,
                unit_price=unit_price,
                remarks=item_data.get('remarks', ''),
            )

    _log_history(grn, 'UPDATED', 'DRAFT', 'DRAFT', user)
    return grn


@transaction.atomic
def submit_grn(grn, user):
    """Submit GRN for approval (DRAFT → PENDING_APPROVAL)."""
    if grn.status != 'DRAFT':
        raise ValueError(f"Cannot submit a GRN in status '{grn.status}'")

    if not grn.items.exists():
        raise ValueError("Cannot submit a GRN with no items.")

    old_status = grn.status
    grn.status = 'PENDING_APPROVAL'
    grn.updated_by = user
    grn.save()

    _log_history(grn, 'SUBMITTED', old_status, 'PENDING_APPROVAL', user)
    InventoryNotificationService.notify_grn_event('submitted', grn)

    return grn


@transaction.atomic
def approve_grn(grn, user, notes=''):
    """Approve a GRN (PENDING_APPROVAL → APPROVED)."""
    if grn.status != 'PENDING_APPROVAL':
        raise ValueError(f"Cannot approve a GRN in status '{grn.status}'")

    old_status = grn.status
    grn.status = 'APPROVED'
    grn.approved_by = user
    grn.approved_at = timezone.now()
    grn.approval_notes = notes
    grn.updated_by = user
    grn.save()

    _log_history(grn, 'APPROVED', old_status, 'APPROVED', user, notes)
    InventoryNotificationService.notify_grn_event('approved', grn)

    return grn


@transaction.atomic
def receive_grn(grn, user):
    """
    Receive goods against an approved GRN (APPROVED → RECEIVED).

    Creates GOODS_RECEIPT stock ledger entries for received quantities.
    Updates PO received quantities.
    """
    if grn.status != 'APPROVED':
        raise ValueError(f"Cannot receive a GRN in status '{grn.status}'")

    # Lock items being received
    grn_items = grn.items.select_related('purchase_order_item', 'item').all()
    item_ids = [i.item_id for i in grn_items]
    locked_items = list(
        InventoryItem.objects.filter(
            id__in=item_ids, tenant_id=grn.tenant_id
        ).select_for_update()
    )

    # Validate against PO ordered quantities
    for grn_item in grn_items:
        if grn_item.purchase_order_item:
            po_item = grn_item.purchase_order_item
            # Check total received across all GRNs for this PO item
            total_received = InventoryGoodsReceiptItem.objects.filter(
                purchase_order_item=po_item,
                goods_receipt__status__in=['RECEIVED', 'COMPLETED'],
            ).exclude(goods_receipt=grn).aggregate(
                total=Sum('received_quantity')
            )['total'] or Decimal('0')

            total_received += grn_item.received_quantity
            if total_received > po_item.ordered_quantity:
                raise ValueError(
                    f"Cannot receive {grn_item.received_quantity} for "
                    f"'{grn_item.item.item_name}': ordered {po_item.ordered_quantity}, "
                    f"total would be {total_received}."
                )

    old_status = grn.status
    grn.status = 'RECEIVED'
    grn.received_by = user
    grn.received_at = timezone.now()
    grn.updated_by = user
    grn.save()

    # Create stock ledger entries
    for grn_item in grn.items.select_related('item', 'purchase_order_item'):
        accepted_qty = grn_item.accepted_quantity or grn_item.received_quantity
        if accepted_qty > 0:
            create_ledger_entry(
                tenant_id=grn.tenant_id,
                item_id=grn_item.item_id,
                transaction_type='GOODS_RECEIPT',
                quantity=accepted_qty,
                location_id=grn.location_id,
                unit_cost=grn_item.unit_price,
                total_cost=grn_item.unit_price * accepted_qty,
                reference_type='GOODS_RECEIPT',
                reference_id=str(grn.grn_number),
                description=f"GRN {grn.grn_number} — {grn.purchase_order.order_number}",
                created_by=user,
            )

        # Handle rejected/damaged quantities — record as separate ledger entries
        rejected_qty = grn_item.rejected_quantity or Decimal('0')
        if rejected_qty > 0:
            create_ledger_entry(
                tenant_id=grn.tenant_id,
                item_id=grn_item.item_id,
                transaction_type='DAMAGE',
                quantity=-rejected_qty,
                location_id=grn.location_id,
                reference_type='GOODS_RECEIPT',
                reference_id=str(grn.grn_number),
                description=f"GRN {grn.grn_number} — Rejected: {grn_item.item.item_code}",
                created_by=user,
            )

        damage_qty = grn_item.damage_quantity or Decimal('0')
        if damage_qty > 0:
            create_ledger_entry(
                tenant_id=grn.tenant_id,
                item_id=grn_item.item_id,
                transaction_type='DAMAGE',
                quantity=-damage_qty,
                location_id=grn.location_id,
                reference_type='GOODS_RECEIPT',
                reference_id=str(grn.grn_number),
                description=f"GRN {grn.grn_number} — Damaged: {grn_item.item.item_code}",
                created_by=user,
            )

    # Update PO received quantities
    _update_po_received_quantity(grn.purchase_order)

    _log_history(grn, 'RECEIVED', old_status, 'RECEIVED', user)
    InventoryNotificationService.notify_grn_event('received', grn)

    return grn


@transaction.atomic
def complete_grn(grn, user):
    """Complete a GRN (RECEIVED → COMPLETED)."""
    if grn.status != 'RECEIVED':
        raise ValueError(f"Cannot complete a GRN in status '{grn.status}'")

    old_status = grn.status
    grn.status = 'COMPLETED'
    grn.completed_by = user
    grn.completed_at = timezone.now()
    grn.updated_by = user
    grn.save()

    _log_history(grn, 'COMPLETED', old_status, 'COMPLETED', user)
    InventoryNotificationService.notify_grn_event('completed', grn)

    return grn


@transaction.atomic
def cancel_grn(grn, user):
    """Cancel a GRN (DRAFT, PENDING_APPROVAL, or APPROVED only)."""
    if grn.status not in ('DRAFT', 'PENDING_APPROVAL', 'APPROVED'):
        raise ValueError(f"Cannot cancel a GRN in status '{grn.status}'")

    old_status = grn.status
    grn.status = 'CANCELLED'
    grn.updated_by = user
    grn.save()

    _log_history(grn, 'CANCELLED', old_status, 'CANCELLED', user)
    InventoryNotificationService.notify_grn_event('cancelled', grn)

    return grn


def get_history(grn):
    """Get the audit trail for a GRN."""
    return InventoryGoodsReceiptHistory.objects.filter(
        goods_receipt=grn
    ).select_related('performed_by').order_by('-timestamp')
