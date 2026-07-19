"""
Seed script: creates default InventoryFeature records.

Run with: python manage.py seed_inventory_features
"""

from django.core.management.base import BaseCommand
from inventory.models import InventoryFeature


DEFAULT_FEATURES = [
    {'code': 'dashboard', 'name': 'Dashboard', 'icon': 'LayoutDashboard', 'route': '/inventory/dashboard', 'display_order': 1},
    {'code': 'reports', 'name': 'Reports', 'icon': 'BarChart3', 'route': '/inventory/reports', 'display_order': 2},
    {'code': 'items', 'name': 'Items', 'icon': 'Box', 'route': '/inventory/items', 'display_order': 3},
    {'code': 'categories', 'name': 'Categories', 'icon': 'FolderTree', 'route': '/inventory/categories', 'display_order': 4},
    {'code': 'units', 'name': 'Units', 'icon': 'Ruler', 'route': '/inventory/units', 'display_order': 5},
    {'code': 'brands', 'name': 'Brands', 'icon': 'Building2', 'route': '/inventory/brands', 'display_order': 6},
    {'code': 'locations', 'name': 'Locations', 'icon': 'MapPin', 'route': '/inventory/locations', 'display_order': 7},
    {'code': 'location-types', 'name': 'Location Types', 'icon': 'Tags', 'route': '/inventory/location-types', 'display_order': 8},
    {'code': 'stock', 'name': 'Stock', 'icon': 'PackageSearch', 'route': '/inventory/stock', 'display_order': 9},
    {'code': 'transfers', 'name': 'Transfers', 'icon': 'ArrowLeftRight', 'route': '/inventory/transfers', 'display_order': 10},
    {'code': 'adjustments', 'name': 'Adjustments', 'icon': 'Scale', 'route': '/inventory/adjustments', 'display_order': 11},
    {'code': 'reservations', 'name': 'Reservations', 'icon': 'CalendarCheck', 'route': '/inventory/reservations', 'display_order': 12},
    {'code': 'purchase-orders', 'name': 'Purchase Orders', 'icon': 'ClipboardList', 'route': '/inventory/purchase-orders', 'display_order': 13},
    {'code': 'goods-receipts', 'name': 'Goods Receipts', 'icon': 'PackageCheck', 'route': '/inventory/goods-receipts', 'display_order': 14},
    {'code': 'supplier-invoices', 'name': 'Supplier Invoices', 'icon': 'Receipt', 'route': '/inventory/supplier-invoices', 'display_order': 15},
    {'code': 'purchase-returns', 'name': 'Purchase Returns', 'icon': 'Undo2', 'route': '/inventory/purchase-returns', 'display_order': 16},
    {'code': 'supplier-payments', 'name': 'Supplier Payments', 'icon': 'DollarSign', 'route': '/inventory/supplier-payments', 'display_order': 17},
    {'code': 'physical-stock-count', 'name': 'Physical Stock Count', 'icon': 'ClipboardCheck', 'route': '/inventory/stock-counts', 'display_order': 18},
    {'code': 'barcode-verification', 'name': 'Barcode Verification', 'icon': 'ScanLine', 'route': '/inventory/barcode-verification', 'display_order': 19},
    {'code': 'weight-check', 'name': 'Weight Check', 'icon': 'Weight', 'route': '/inventory/weight-check', 'display_order': 20},
    {'code': 'inventory-valuation', 'name': 'Inventory Valuation', 'icon': 'DollarSign', 'route': '/inventory/valuation', 'display_order': 21},
    {'code': 'low-stock', 'name': 'Low Stock', 'icon': 'AlertTriangle', 'route': '/inventory/reports?report=low-stock', 'display_order': 22},
    {'code': 'out-of-stock', 'name': 'Out of Stock', 'icon': 'AlertTriangle', 'route': '/inventory/reports?report=out-of-stock', 'display_order': 23},
    {'code': 'reorder', 'name': 'Reorder Report', 'icon': 'TrendingUp', 'route': '/inventory/reports?report=reorder', 'display_order': 24},
    {'code': 'fast-moving', 'name': 'Fast Moving', 'icon': 'TrendingUp', 'route': '/inventory/reports?report=fast-moving', 'display_order': 25},
    {'code': 'slow-moving', 'name': 'Slow Moving', 'icon': 'Clock', 'route': '/inventory/reports?report=slow-moving', 'display_order': 26},
    {'code': 'dead-stock', 'name': 'Dead Stock', 'icon': 'Clock', 'route': '/inventory/reports?report=dead-stock', 'display_order': 27},
    {'code': 'inventory-aging', 'name': 'Inventory Aging', 'icon': 'Clock', 'route': '/inventory/reports?report=inventory-aging', 'display_order': 28},
]

FEATURE_DESCRIPTIONS = {
    'dashboard': 'Inventory overview dashboard with key metrics and charts.',
    'reports': 'Generate and view inventory reports.',
    'items': 'Manage inventory item master data.',
    'categories': 'Organize items into hierarchical categories.',
    'units': 'Manage units of measurement.',
    'brands': 'Manage item brands and manufacturers.',
    'locations': 'Manage inventory storage locations.',
    'location-types': 'Configure location types (Warehouse, Store, etc.).',
    'stock': 'View real-time stock availability across locations.',
    'transfers': 'Transfer stock between locations.',
    'adjustments': 'Record stock adjustments (increases/decreases).',
    'reservations': 'Reserve stock for future orders.',
    'purchase-orders': 'Create and manage purchase orders.',
    'goods-receipts': 'Record goods received from suppliers.',
    'supplier-invoices': 'Manage supplier invoices and bills.',
    'purchase-returns': 'Process returns to suppliers.',
    'supplier-payments': 'Manage payments to suppliers.',
    'physical-stock-count': 'Conduct physical stock counts and cycle counts.',
    'barcode-verification': 'Verify items using barcode scanning.',
    'weight-check': 'Weight verification for received goods.',
    'inventory-valuation': 'View inventory valuation reports.',
    'low-stock': 'Items below minimum stock levels.',
    'out-of-stock': 'Items with zero available stock.',
    'reorder': 'Items needing reorder based on reorder levels.',
    'fast-moving': 'Items with high turnover rates.',
    'slow-moving': 'Items with low turnover rates.',
    'dead-stock': 'Items with no recent movement.',
    'inventory-aging': 'Inventory aging analysis.',
}


def seed_inventory_features():
    """Create all default inventory features if they don't exist."""
    created = 0
    updated = 0

    for feature_data in DEFAULT_FEATURES:
        code = feature_data['code']
        defaults = {
            'name': feature_data['name'],
            'description': FEATURE_DESCRIPTIONS.get(code, ''),
            'icon': feature_data['icon'],
            'route': feature_data['route'],
            'display_order': feature_data['display_order'],
        }

        obj, was_created = InventoryFeature.objects.update_or_create(
            code=code,
            defaults=defaults
        )

        if was_created:
            created += 1
        else:
            updated += 1

    print(f"✓ Features seeded: {created} created, {updated} updated")
    return created, updated
