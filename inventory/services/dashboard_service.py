"""
Inventory Dashboard & Reports Service
========================================
Aggregates data from all inventory modules for real-time visibility.
Uses the Stock Ledger Engine as the single source of truth for stock quantities.
Does NOT duplicate business logic — delegates to existing services.
"""

from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum, Count, Q, F, Value, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth, TruncWeek, Coalesce
from django.utils import timezone

from inventory.models import (
    InventoryItem, ItemCategory, Brand,
    StockLedger, StockSummary,
    InventoryTransfer, InventoryAdjustment,
    InventoryReservation, InventoryReservationItem,
    InventoryStockCount,
    PurchaseOrder, PurchaseOrderItem,
    InventoryGoodsReceipt,
    InventorySupplierInvoice, InventorySupplierPayment,
    InventoryPurchaseReturn,
)
from inventory.services.stock_engine import (
    get_all_availability,
    get_low_stock_items as engine_low_stock,
    get_out_of_stock_items as engine_oos,
)


# ===========================================================================
# DASHBOARD CARDS
# ===========================================================================

def get_stock_summary_cards(tenant_id):
    """Summary cards for the dashboard header."""
    items = InventoryItem.objects.filter(tenant_id=tenant_id, status='ACTIVE')
    total_items = items.count()

    # Single combined query for all StockSummary aggregates
    summaries = StockSummary.objects.filter(tenant_id=tenant_id)
    agg = summaries.aggregate(
        total_physical=Sum('physical_quantity'),
        total_reserved=Sum('reserved_quantity'),
        total_in_transit=Sum('in_transit_quantity'),
        total_damaged=Sum('damaged_quantity'),
        total_stock_value=Sum(
            ExpressionWrapper(
                F('physical_quantity') * Coalesce('item__cost_price', Value(0)),
                output_field=DecimalField(),
            )
        ),
        total_available_value=Sum(
            ExpressionWrapper(
                (F('physical_quantity') - F('reserved_quantity')) * Coalesce('item__cost_price', Value(0)),
                output_field=DecimalField(),
            )
        ),
    )

    pending_transfers = InventoryTransfer.objects.filter(
        tenant_id=tenant_id, status__in=['PENDING', 'APPROVED']
    ).count()
    pending_pos = PurchaseOrder.objects.filter(
        tenant_id=tenant_id, status__in=['DRAFT', 'SENT', 'PARTIALLY_RECEIVED']
    ).count()
    pending_grns = InventoryGoodsReceipt.objects.filter(
        tenant_id=tenant_id, status__in=['DRAFT', 'PENDING_APPROVAL', 'APPROVED']
    ).count()
    pending_counts = InventoryStockCount.objects.filter(
        tenant_id=tenant_id, status__in=['DRAFT', 'ASSIGNED', 'IN_PROGRESS']
    ).count()
    pending_adjustments = InventoryAdjustment.objects.filter(
        tenant_id=tenant_id, status__in=['DRAFT', 'PENDING_APPROVAL', 'APPROVED']
    ).count()
    active_reservations = InventoryReservation.objects.filter(
        tenant_id=tenant_id, status='ACTIVE'
    ).count()

    return {
        'total_items': total_items,
        'total_stock_value': float(agg['total_stock_value'] or 0),
        'available_stock_value': float(agg['total_available_value'] or 0),
        'reserved_items': float(agg['total_reserved'] or 0),
        'in_transit_items': float(agg['total_in_transit'] or 0),
        'damaged_items': float(agg['total_damaged'] or 0),
        'active_reservations': active_reservations,
        'pending_transfers': pending_transfers,
        'pending_purchase_orders': pending_pos,
        'pending_grns': pending_grns,
        'pending_stock_counts': pending_counts,
        'pending_adjustments': pending_adjustments,
    }


# ===========================================================================
# DASHBOARD CHARTS
# ===========================================================================

def get_stock_movement_trend(tenant_id, days=30):
    """Stock movement trend (IN/OUT by transaction type) over recent days."""
    since = timezone.now() - timedelta(days=days)
    qs = StockLedger.objects.filter(
        tenant_id=tenant_id, created_at__gte=since
    ).exclude(
        transaction_type__in=['RESERVATION', 'RESERVATION_RELEASE']
    )
    data = qs.annotate(
        month=TruncMonth('created_at')
    ).values('month', 'transaction_type').annotate(
        total=Sum('quantity')
    ).order_by('month')
    return list(data)


def get_monthly_purchase_trend(tenant_id, months=12):
    """Monthly purchase order trend."""
    since = timezone.now() - timedelta(days=months * 30)
    qs = PurchaseOrder.objects.filter(
        tenant_id=tenant_id, created_at__gte=since
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id'),
        total=Sum('total_amount'),
    ).order_by('month')
    return list(qs)


def get_catergory_wise_inventory(tenant_id):
    """Inventory value broken down by category."""
    from django.db.models.functions import Coalesce
    data = StockSummary.objects.filter(
        tenant_id=tenant_id,
    ).values(
        cat_name=Coalesce('item__category__category_name', Value('Uncategorized')),
    ).annotate(
        value=Sum(
            ExpressionWrapper(
                F('physical_quantity') * Coalesce('item__cost_price', Value(0)),
                output_field=DecimalField(),
            )
        ),
    ).order_by('-value')
    return [{'category': d['cat_name'], 'value': float(d['value'])} for d in data if d['value'] > 0]


def get_warehouse_wise_inventory(tenant_id):
    """Inventory value broken down by warehouse/location."""
    data = StockSummary.objects.filter(
        tenant_id=tenant_id,
        location__isnull=False,
        location__status='ACTIVE',
    ).values(
        warehouse=F('location__location_name'),
    ).annotate(
        value=Sum(
            ExpressionWrapper(
                F('physical_quantity') * Coalesce('item__cost_price', Value(0)),
                output_field=DecimalField(),
            )
        ),
    ).order_by('-value')
    return [{'warehouse': d['warehouse'], 'value': float(d['value'])} for d in data if d['value'] > 0]


def get_inventory_aging_distribution(tenant_id):
    """Stock aging based on ledger entry age, using StockSummary for bulk quantities."""
    now = timezone.now()
    # Get items with physical stock from StockSummary
    stock_rows = StockSummary.objects.filter(
        tenant_id=tenant_id,
        physical_quantity__gt=0,
    ).select_related('item').values(
        'item_id', 'physical_quantity', 'item__cost_price',
    )
    item_ids = [r['item_id'] for r in stock_rows]

    if not item_ids:
        return [{'bucket': '0-30 days', 'value': 0},
                {'bucket': '31-60 days', 'value': 0},
                {'bucket': '61-90 days', 'value': 0},
                {'bucket': '90+ days', 'value': 0}]

    # Bulk-fetch latest ledger entry per item using a subquery
    from django.db.models import OuterRef, Subquery
    latest_per_item = StockLedger.objects.filter(
        tenant_id=tenant_id,
        item_id=OuterRef('pk'),
        transaction_type__in=[
            'OPENING', 'PURCHASE', 'PURCHASE_IN', 'GOODS_RECEIPT',
        ],
    ).order_by('-created_at').values('created_at')[:1]

    items_qs = InventoryItem.objects.filter(
        id__in=item_ids, tenant_id=tenant_id,
    ).annotate(
        latest_entry_date=Subquery(latest_per_item),
    ).values('id', 'latest_entry_date')

    entry_dates = {r['id']: r['latest_entry_date'] for r in items_qs}

    buckets = {'0-30 days': 0, '31-60 days': 0, '61-90 days': 0, '90+ days': 0}
    for row in stock_rows:
        phys = row['physical_quantity'] or 0
        if phys <= 0:
            continue
        entry_date = entry_dates.get(row['item_id'])
        if entry_date:
            age = (now - entry_date).days
            value = float(phys * (row['item__cost_price'] or 0))
            if age <= 30:
                buckets['0-30 days'] += value
            elif age <= 60:
                buckets['31-60 days'] += value
            elif age <= 90:
                buckets['61-90 days'] += value
            else:
                buckets['90+ days'] += value
    return [{'bucket': k, 'value': v} for k, v in buckets.items()]


# ===========================================================================
# RECENT ACTIVITY
# ===========================================================================

def get_recent_transactions(tenant_id, limit=10):
    """Recent stock ledger transactions."""
    return list(StockLedger.objects.filter(
        tenant_id=tenant_id
    ).select_related('item', 'location', 'created_by').order_by('-created_at')[:limit])


def get_recent_transfers(tenant_id, limit=5):
    """Recent transfers."""
    return list(InventoryTransfer.objects.filter(
        tenant_id=tenant_id
    ).select_related(
        'source_location', 'destination_location', 'created_by'
    ).order_by('-created_at')[:limit])


def get_recent_adjustments(tenant_id, limit=5):
    """Recent adjustments."""
    return list(InventoryAdjustment.objects.filter(
        tenant_id=tenant_id
    ).select_related('reason', 'location', 'created_by').order_by('-created_at')[:limit])


def get_recent_purchase_orders(tenant_id, limit=5):
    """Recent purchase orders."""
    return list(PurchaseOrder.objects.filter(
        tenant_id=tenant_id
    ).select_related('supplier', 'created_by').order_by('-created_at')[:limit])


def get_recent_goods_receipts(tenant_id, limit=5):
    """Recent GRNs."""
    return list(InventoryGoodsReceipt.objects.filter(
        tenant_id=tenant_id
    ).select_related('location', 'purchase_order', 'supplier', 'created_by'
    ).order_by('-created_at')[:limit])


def get_recent_purchase_returns(tenant_id, limit=5):
    """Recent purchase returns."""
    return list(InventoryPurchaseReturn.objects.filter(
        tenant_id=tenant_id
    ).select_related('supplier', 'created_by').order_by('-created_at')[:limit])


def get_recent_supplier_invoices(tenant_id, limit=5):
    """Recent supplier invoices."""
    return list(InventorySupplierInvoice.objects.filter(
        tenant_id=tenant_id
    ).select_related('supplier', 'created_by').order_by('-created_at')[:limit])


# ===========================================================================
# STOCK REPORTS
# ===========================================================================

def current_stock_report(tenant_id, filters=None):
    """Current stock position for all items."""
    return get_all_availability(tenant_id, filters)


def stock_ledger_report(tenant_id, filters=None):
    """Stock ledger entries with filters."""
    qs = StockLedger.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('item', 'item__unit', 'location', 'created_by')
    if filters:
        if filters.get('item_id'):
            qs = qs.filter(item_id=filters['item_id'])
        if filters.get('location_id'):
            qs = qs.filter(location_id=filters['location_id'])
        if filters.get('transaction_type'):
            qs = qs.filter(transaction_type=filters['transaction_type'])
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])
        if filters.get('search'):
            qs = qs.filter(
                Q(item__item_code__icontains=filters['search']) |
                Q(item__item_name__icontains=filters['search']) |
                Q(description__icontains=filters['search'])
            )
    return qs.order_by('-created_at')


def stock_movement_report(tenant_id, filters=None):
    """Stock movement grouped by item and transaction type."""
    qs = StockLedger.objects.filter(tenant_id=tenant_id)
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])
        if filters.get('item_id'):
            qs = qs.filter(item_id=filters['item_id'])
    return qs.values(
        'item_id', 'item__item_code', 'item__item_name',
        'transaction_type'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_cost=Sum('total_cost'),
        entry_count=Count('id'),
    ).order_by('item__item_code', 'transaction_type')


def stock_summary_report(tenant_id, filters=None):
    """Stock summary with aggregated quantities."""
    qs = StockSummary.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('item', 'item__category', 'item__unit', 'location')
    if filters:
        if filters.get('location_id'):
            qs = qs.filter(location_id=filters['location_id'])
        if filters.get('category_id'):
            qs = qs.filter(item__category_id=filters['category_id'])
        if filters.get('brand_id'):
            qs = qs.filter(item__brand_id=filters['brand_id'])
        if filters.get('search'):
            qs = qs.filter(
                Q(item__item_code__icontains=filters['search']) |
                Q(item__item_name__icontains=filters['search'])
            )
    return qs.order_by('item__item_code')


def inventory_valuation_report(tenant_id, filters=None):
    """Inventory valuation."""
    from inventory.services.stock_engine import get_valuation
    return get_valuation(tenant_id, filters)


def reserved_stock_report(tenant_id, filters=None):
    """Items with active reservations."""
    qs = InventoryReservationItem.objects.filter(
        reservation__tenant_id=tenant_id,
        reservation__status='ACTIVE',
    )
    if filters:
        if filters.get('item_id'):
            qs = qs.filter(item_id=filters['item_id'])
        if filters.get('location_id'):
            qs = qs.filter(reservation__source_location_id=filters['location_id'])
    return qs.values(
        'item_id', 'item__item_code', 'item__item_name',
    ).annotate(
        reserved_qty=Sum('reserved_quantity'),
        reservation_count=Count('id', distinct=True),
    ).order_by('-reserved_qty')


def damaged_stock_report(tenant_id, filters=None):
    """Items marked as damaged/lost/expired."""
    qs = StockLedger.objects.filter(
        tenant_id=tenant_id,
        transaction_type__in=['DAMAGE', 'LOST', 'EXPIRED'],
    )
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])
        if filters.get('transaction_type'):
            qs = qs.filter(transaction_type=filters['transaction_type'])
    return qs.values(
        'item_id', 'item__item_code', 'item__item_name',
        'transaction_type', 'location__location_name',
    ).annotate(
        total_qty=Sum('quantity'),
        total_cost=Sum('total_cost'),
    ).order_by('-total_qty')


# ===========================================================================
# OPERATIONAL REPORTS
# ===========================================================================

def adjustment_report(tenant_id, filters=None):
    """Stock adjustment report."""
    qs = InventoryAdjustment.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('reason', 'location', 'created_by', 'approved_by')\
            .prefetch_related('items__item', 'items__unit')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('location_id'):
            qs = qs.filter(location_id=filters['location_id'])
        if filters.get('adjustment_type'):
            qs = qs.filter(adjustment_type=filters['adjustment_type'])
    return qs.order_by('-created_at')


def transfer_report(tenant_id, filters=None):
    """Stock transfer report."""
    qs = InventoryTransfer.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related(
        'source_location', 'destination_location',
        'created_by', 'approved_by', 'received_by',
    ).prefetch_related('items__item')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('transfer_type'):
            qs = qs.filter(transfer_type=filters['transfer_type'])
        if filters.get('location_id'):
            qs = qs.filter(
                Q(source_location_id=filters['location_id']) |
                Q(destination_location_id=filters['location_id'])
            )
    return qs.order_by('-created_at')


def reservation_report(tenant_id, filters=None):
    """Reservation report."""
    qs = InventoryReservation.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('source_location', 'reason', 'created_by')\
            .prefetch_related('items__item', 'items__unit')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('priority'):
            qs = qs.filter(priority=filters['priority'])
    return qs.order_by('-created_at')


def stock_count_report(tenant_id, filters=None):
    """Physical stock count report."""
    qs = InventoryStockCount.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('location', 'reason', 'created_by', 'approved_by')\
            .prefetch_related('items__item', 'items__unit', 'assigned_counters')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('location_id'):
            qs = qs.filter(location_id=filters['location_id'])
    return qs.order_by('-created_at')


# ===========================================================================
# PURCHASE REPORTS
# ===========================================================================

def purchase_order_report(tenant_id, filters=None):
    """Purchase order report."""
    qs = PurchaseOrder.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('supplier', 'created_by')\
            .prefetch_related('items__item')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(order_date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(order_date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('supplier_id'):
            qs = qs.filter(supplier_id=filters['supplier_id'])
        if filters.get('search'):
            qs = qs.filter(
                Q(order_number__icontains=filters['search']) |
                Q(supplier_name__icontains=filters['search'])
            )
    return qs.order_by('-created_at')


def pending_po_report(tenant_id):
    """Pending purchase orders report."""
    return list(PurchaseOrder.objects.filter(
        tenant_id=tenant_id,
        status__in=['DRAFT', 'SENT', 'PARTIALLY_RECEIVED'],
    ).select_related('supplier').order_by('-created_at'))


def goods_receipt_report(tenant_id, filters=None):
    """Goods receipt report."""
    qs = InventoryGoodsReceipt.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('location', 'purchase_order', 'supplier', 'created_by')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(receipt_date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(receipt_date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('location_id'):
            qs = qs.filter(location_id=filters['location_id'])
    return qs.order_by('-created_at')


def supplier_invoice_report(tenant_id, filters=None):
    """Supplier invoice report."""
    qs = InventorySupplierInvoice.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('supplier', 'purchase_order', 'created_by')\
            .prefetch_related('items__item', 'goods_receipts')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(invoice_date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(invoice_date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('supplier_id'):
            qs = qs.filter(supplier_id=filters['supplier_id'])
    return qs.order_by('-created_at')


def purchase_return_report(tenant_id, filters=None):
    """Purchase return report."""
    qs = InventoryPurchaseReturn.objects.filter(tenant_id=tenant_id)
    qs = qs.select_related('supplier', 'created_by')
    if filters:
        if filters.get('date_from'):
            qs = qs.filter(return_date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(return_date__lte=filters['date_to'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('supplier_id'):
            qs = qs.filter(supplier_id=filters['supplier_id'])
    return qs.order_by('-created_at')


# ===========================================================================
# ANALYTICS REPORTS
# ===========================================================================

def low_stock_report(tenant_id):
    """Low stock items."""
    return engine_low_stock(tenant_id)


def out_of_stock_report(tenant_id):
    """Out of stock items."""
    return engine_oos(tenant_id)


def reorder_report(tenant_id):
    """Items needing reorder (below reorder level) — uses StockSummary for bulk quantities."""
    items = InventoryItem.objects.filter(
        tenant_id=tenant_id, status='ACTIVE',
        reorder_level__isnull=False,
    ).select_related('category')
    item_ids = list(items.values_list('id', flat=True))
    if not item_ids:
        return []

    # Bulk-fetch available stock from StockSummary
    stock_rows = StockSummary.objects.filter(
        tenant_id=tenant_id, item_id__in=item_ids,
    ).values('item_id', 'physical_quantity', 'reserved_quantity')
    stock_map = {}
    for row in stock_rows:
        physical = row['physical_quantity'] or Decimal('0')
        reserved = row['reserved_quantity'] or Decimal('0')
        stock_map[row['item_id']] = physical - reserved

    results = []
    for item in items:
        avail = stock_map.get(item.id, Decimal('0'))
        if avail <= item.reorder_level:
            suggested = max((item.reorder_level or 0) - avail + 1, Decimal('0'))
            results.append({
                'item_id': item.id,
                'item_code': item.item_code,
                'item_name': item.item_name,
                'category_name': item.category.category_name if item.category else '',
                'current_stock': float(avail),
                'reorder_level': float(item.reorder_level),
                'min_stock_level': float(item.min_stock_level) if item.min_stock_level else 0,
                'max_stock_level': float(item.max_stock_level) if item.max_stock_level else 0,
                'suggested_order': float(suggested),
            })
    return sorted(results, key=lambda x: x['current_stock'])


def fast_moving_items(tenant_id, limit=20):
    """Items with the highest outbound movement."""
    qs = StockLedger.objects.filter(
        tenant_id=tenant_id,
        transaction_type__in=['SALE', 'TRANSFER_OUT', 'CONSUMPTION'],
    ).values('item_id', 'item__item_code', 'item__item_name', 'item__unit__unit_name')\
     .annotate(total=Sum('quantity')).order_by('total')[:limit]
    return list(qs)


def slow_moving_items(tenant_id, days=90, limit=20):
    """Items with no movement in the given period — uses StockSummary for physical stock."""
    since = timezone.now() - timedelta(days=days)
    items = InventoryItem.objects.filter(
        tenant_id=tenant_id, status='ACTIVE',
    ).only('id', 'item_code', 'item_name', 'category', 'cost_price')
    recent_item_ids = StockLedger.objects.filter(
        tenant_id=tenant_id,
        created_at__gte=since,
    ).exclude(
        transaction_type__in=['RESERVATION', 'RESERVATION_RELEASE'],
    ).values_list('item_id', flat=True).distinct()

    slow_items = items.exclude(id__in=recent_item_ids)[:limit]
    slow_item_ids = [i.id for i in slow_items]

    # Bulk-fetch physical stock from StockSummary
    stock_rows = StockSummary.objects.filter(
        tenant_id=tenant_id, item_id__in=slow_item_ids,
    ).values('item_id', 'physical_quantity')
    stock_map = {r['item_id']: r['physical_quantity'] or Decimal('0') for r in stock_rows}

    # Bulk-fetch categories
    cat_ids = list(set(
        i.category_id for i in slow_items if i.category_id
    ))
    cat_map = {}
    if cat_ids:
        for c in ItemCategory.objects.filter(id__in=cat_ids).values('id', 'category_name'):
            cat_map[c['id']] = c['category_name']

    results = []
    for item in slow_items:
        phys = stock_map.get(item.id, Decimal('0'))
        if phys > 0:
            results.append({
                'item_id': item.id,
                'item_code': item.item_code,
                'item_name': item.item_name,
                'category_name': cat_map.get(item.category_id, ''),
                'current_stock': float(phys),
                'value': float(phys * (item.cost_price or 0)),
                'days_without_movement': days,
            })
    return results


def dead_stock_report(tenant_id, days=180, limit=20):
    """Items with zero movement over a long period."""
    return slow_moving_items(tenant_id, days=days, limit=limit)


def inventory_aging_report(tenant_id):
    """Inventory aging analysis."""
    return get_inventory_aging_distribution(tenant_id)


def top_moving_items(tenant_id, limit=20):
    """Top items by movement quantity."""
    return fast_moving_items(tenant_id, limit)


def top_suppliers(tenant_id, limit=10):
    """Top suppliers by PO value."""
    qs = PurchaseOrder.objects.filter(
        tenant_id=tenant_id, status='CLOSED'
    ).values(
        'supplier_id', 'supplier_name',
    ).annotate(
        total_amount=Sum('total_amount'),
        order_count=Count('id'),
    ).order_by('-total_amount')[:limit]
    return list(qs)


def most_adjusted_items(tenant_id, limit=20):
    """Items with the most adjustments."""
    qs = StockLedger.objects.filter(
        tenant_id=tenant_id,
        transaction_type='ADJUSTMENT',
    ).values('item_id', 'item__item_code', 'item__item_name')\
     .annotate(total=Sum('quantity'), count=Count('id'))\
     .order_by('-count')[:limit]
    return list(qs)


def most_transferred_items(tenant_id, limit=20):
    """Items with the most transfers."""
    qs = StockLedger.objects.filter(
        tenant_id=tenant_id,
        transaction_type__in=['TRANSFER_OUT', 'TRANSFER_IN'],
    ).values('item_id', 'item__item_code', 'item__item_name')\
     .annotate(total=Sum('quantity'), count=Count('id'))\
     .order_by('-count')[:limit]
    return list(qs)
