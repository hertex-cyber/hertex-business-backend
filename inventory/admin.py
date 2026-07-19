from django.contrib import admin
from inventory.models import (
    ItemCategory, Unit, UnitConversion, Brand, InventoryItem,
    CustomFieldDefinition, InventoryLocationType, InventoryLocation,
    StockLedger, StockSummary,
    InventoryTransfer, InventoryTransferItem, InventoryTransferAttachment,
    InventoryTransferHistory,
    InventoryAdjustmentReason, InventoryAdjustment,
    InventoryAdjustmentItem, InventoryAdjustmentAttachment,
    InventoryAdjustmentHistory,
    InventoryReservation, InventoryReservationItem,
    InventoryReservationHistory, InventoryReservationAttachment,
    InventoryReservationReason,
    StockCountReason,
    InventoryStockCount, InventoryStockCountItem,
    InventoryStockCountHistory, InventoryStockCountAttachment,
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory,
    PurchaseOrderAttachment, PurchaseReceipt, PurchaseReceiptItem,
    InventoryFeature, CompanyInventoryFeature,
)


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ['category_code', 'category_name', 'parent', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['category_code', 'category_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['unit_code', 'unit_name', 'symbol', 'status']
    list_filter = ['status']
    search_fields = ['unit_code', 'unit_name', 'symbol']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UnitConversion)
class UnitConversionAdmin(admin.ModelAdmin):
    list_display = ['from_unit', 'to_unit', 'conversion_factor']
    list_filter = ['from_unit', 'to_unit']
    search_fields = ['from_unit__unit_name', 'to_unit__unit_name']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['brand_code', 'brand_name', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['brand_code', 'brand_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = [
        'item_code', 'item_name', 'category', 'unit',
        'brand', 'status', 'created_at'
    ]
    list_filter = ['status', 'category', 'brand']
    search_fields = ['item_code', 'item_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['category', 'unit', 'brand']


@admin.register(CustomFieldDefinition)
class CustomFieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ['field_name', 'field_label', 'field_type', 'is_required', 'is_active', 'order']
    list_filter = ['field_type', 'is_required', 'is_active']
    search_fields = ['field_name', 'field_label']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InventoryLocationType)
class InventoryLocationTypeAdmin(admin.ModelAdmin):
    list_display = ['type_code', 'type_name', 'status']
    list_filter = ['status']
    search_fields = ['type_code', 'type_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InventoryLocation)
class InventoryLocationAdmin(admin.ModelAdmin):
    list_display = [
        'location_code', 'location_name', 'location_type',
        'parent_location', 'city', 'status', 'created_at'
    ]
    list_filter = ['status', 'location_type', 'country']
    search_fields = ['location_code', 'location_name', 'city', 'state']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['location_type', 'parent_location']


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = ['item', 'location', 'transaction_type', 'quantity', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['item__item_code', 'item__item_name', 'description']
    readonly_fields = ['created_at']
    list_select_related = ['item', 'location']


@admin.register(StockSummary)
class StockSummaryAdmin(admin.ModelAdmin):
    list_display = ['item', 'location', 'physical_quantity', 'reserved_quantity', 'available_quantity']
    list_filter = ['location']
    search_fields = ['item__item_code', 'item__item_name']
    list_select_related = ['item', 'location']


@admin.register(InventoryTransfer)
class InventoryTransferAdmin(admin.ModelAdmin):
    list_display = [
        'transfer_number', 'transfer_date', 'source_location',
        'destination_location', 'transfer_type', 'status', 'created_at'
    ]
    list_filter = ['status', 'transfer_type']
    search_fields = ['transfer_number', 'remarks']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['source_location', 'destination_location']


@admin.register(InventoryTransferItem)
class InventoryTransferItemAdmin(admin.ModelAdmin):
    list_display = ['transfer', 'item', 'quantity', 'received_quantity', 'damaged_quantity']
    list_filter = ['transfer']
    search_fields = ['item__item_code', 'item__item_name']
    list_select_related = ['transfer', 'item']


@admin.register(InventoryTransferAttachment)
class InventoryTransferAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'transfer', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['file_name']


@admin.register(InventoryTransferHistory)
class InventoryTransferHistoryAdmin(admin.ModelAdmin):
    list_display = ['transfer', 'action', 'from_status', 'to_status', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['transfer__transfer_number', 'remarks']
    readonly_fields = ['timestamp']
    list_select_related = ['transfer', 'performed_by']


# ============================================================================
# INVENTORY ADJUSTMENT ADMIN (Section 7)
# ============================================================================

@admin.register(InventoryAdjustmentReason)
class InventoryAdjustmentReasonAdmin(admin.ModelAdmin):
    list_display = ['reason_code', 'reason_name', 'adjustment_type', 'status', 'is_default']
    list_filter = ['adjustment_type', 'status', 'is_default']
    search_fields = ['reason_code', 'reason_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'adjustment_number', 'adjustment_date', 'location',
        'adjustment_type', 'reason', 'status', 'created_at'
    ]
    list_filter = ['status', 'adjustment_type']
    search_fields = ['adjustment_number', 'remarks']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['location', 'reason']


@admin.register(InventoryAdjustmentItem)
class InventoryAdjustmentItemAdmin(admin.ModelAdmin):
    list_display = ['adjustment', 'item', 'adjustment_quantity', 'available_quantity']
    list_filter = ['adjustment']
    search_fields = ['item__item_code', 'item__item_name']
    list_select_related = ['adjustment', 'item']


@admin.register(InventoryAdjustmentAttachment)
class InventoryAdjustmentAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'adjustment', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['file_name']


@admin.register(InventoryAdjustmentHistory)
class InventoryAdjustmentHistoryAdmin(admin.ModelAdmin):
    list_display = ['adjustment', 'action', 'from_status', 'to_status', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['adjustment__adjustment_number', 'remarks']
    readonly_fields = ['timestamp']
    list_select_related = ['adjustment', 'performed_by']


# ============================================================================
# RESERVATION ADMIN (Section 8)
# ============================================================================

@admin.register(InventoryReservationReason)
class InventoryReservationReasonAdmin(admin.ModelAdmin):
    list_display = ['reason_code', 'reason_name', 'status', 'is_default']
    list_filter = ['status', 'is_default']
    search_fields = ['reason_code', 'reason_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InventoryReservation)
class InventoryReservationAdmin(admin.ModelAdmin):
    list_display = [
        'reservation_number', 'reservation_date', 'expiry_date',
        'source_location', 'reservation_type', 'priority', 'status', 'created_at'
    ]
    list_filter = ['status', 'reservation_type', 'priority']
    search_fields = ['reservation_number', 'customer_name', 'reference_number', 'remarks']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['source_location']


@admin.register(InventoryReservationItem)
class InventoryReservationItemAdmin(admin.ModelAdmin):
    list_display = ['reservation', 'item', 'requested_quantity', 'reserved_quantity', 'fulfilled_quantity']
    list_filter = ['reservation']
    search_fields = ['item__item_code', 'item__item_name']
    list_select_related = ['reservation', 'item']


@admin.register(InventoryReservationAttachment)
class InventoryReservationAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'reservation', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['file_name']


@admin.register(InventoryReservationHistory)
class InventoryReservationHistoryAdmin(admin.ModelAdmin):
    list_display = ['reservation', 'action', 'from_status', 'to_status', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['reservation__reservation_number', 'remarks']
    readonly_fields = ['timestamp']
    list_select_related = ['reservation', 'performed_by']


# ============================================================================
# STOCK COUNT ADMIN (Section 9)
# ============================================================================

@admin.register(StockCountReason)
class StockCountReasonAdmin(admin.ModelAdmin):
    list_display = ['reason_code', 'reason_name', 'status', 'is_default']
    list_filter = ['status', 'is_default']
    search_fields = ['reason_code', 'reason_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InventoryStockCount)
class InventoryStockCountAdmin(admin.ModelAdmin):
    list_display = [
        'count_number', 'count_date', 'count_type', 'location',
        'reason', 'status', 'total_items_counted',
        'total_items_with_difference', 'created_at'
    ]
    list_filter = ['status', 'count_type']
    search_fields = ['count_number', 'remarks']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['location', 'reason']


@admin.register(InventoryStockCountItem)
class InventoryStockCountItemAdmin(admin.ModelAdmin):
    list_display = ['count', 'item', 'expected_quantity', 'counted_quantity', 'difference_quantity']
    list_filter = ['count']
    search_fields = ['item__item_code', 'item__item_name']
    list_select_related = ['count', 'item']


@admin.register(InventoryStockCountAttachment)
class InventoryStockCountAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'count', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['file_name']


@admin.register(InventoryStockCountHistory)
class InventoryStockCountHistoryAdmin(admin.ModelAdmin):
    list_display = ['count', 'action', 'from_status', 'to_status', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['count__count_number', 'remarks']
    readonly_fields = ['timestamp']
    list_select_related = ['count', 'performed_by']

# ============================================================================
# PURCHASE ORDER ADMIN (Section 10)
# ============================================================================

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'order_date', 'expected_delivery_date',
        'supplier', 'location', 'status', 'total_amount', 'created_at'
    ]
    list_filter = ['status']
    search_fields = ['order_number', 'supplier_name', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['supplier', 'location']


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ['purchase_order', 'item', 'ordered_quantity', 'received_quantity', 'unit_price', 'line_total']
    list_filter = ['purchase_order']
    search_fields = ['item__item_code', 'item__item_name']
    list_select_related = ['purchase_order', 'item']


@admin.register(PurchaseOrderAttachment)
class PurchaseOrderAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'purchase_order', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['file_name']


@admin.register(PurchaseOrderHistory)
class PurchaseOrderHistoryAdmin(admin.ModelAdmin):
    list_display = ['purchase_order', 'action', 'from_status', 'to_status', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['purchase_order__order_number', 'remarks']
    readonly_fields = ['timestamp']
    list_select_related = ['purchase_order', 'performed_by']


@admin.register(PurchaseReceipt)
class PurchaseReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'receipt_date', 'purchase_order', 'location', 'created_at']
    list_filter = ['receipt_date']
    search_fields = ['receipt_number', 'notes']
    readonly_fields = ['created_at']
    list_select_related = ['purchase_order', 'location']


@admin.register(PurchaseReceiptItem)
class PurchaseReceiptItemAdmin(admin.ModelAdmin):
    list_display = ['purchase_receipt', 'item', 'received_quantity', 'unit_price']
    list_filter = ['purchase_receipt']
    search_fields = ['item__item_code', 'item__item_name']
    list_select_related = ['purchase_receipt', 'item']


# ============================================================================
# INVENTORY FEATURE MANAGEMENT ADMIN (Section 23)
# ============================================================================

@admin.register(InventoryFeature)
class InventoryFeatureAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'display_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'description']
    ordering = ['display_order', 'code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CompanyInventoryFeature)
class CompanyInventoryFeatureAdmin(admin.ModelAdmin):
    list_display = ['company', 'inventory_feature', 'enabled']
    list_filter = ['enabled', 'company']
    search_fields = ['company__name', 'inventory_feature__code', 'inventory_feature__name']
    readonly_fields = ['created_at', 'updated_at']
