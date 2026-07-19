from rest_framework import serializers
from inventory.models import (
    ItemCategory, Unit, UnitConversion, Brand, InventoryItem,
    CustomFieldDefinition, InventoryLocationType, InventoryLocation,
    StockLedger, StockSummary, InventoryTransfer, InventoryTransferItem,
    InventoryTransferAttachment, InventoryTransferHistory,
    InventoryAdjustment, InventoryAdjustmentItem,
    InventoryAdjustmentHistory, InventoryAdjustmentAttachment,
    InventoryAdjustmentReason,
    InventoryReservation, InventoryReservationItem,
    InventoryReservationHistory, InventoryReservationAttachment,
    InventoryReservationReason,
    StockCountReason, InventoryStockCount, InventoryStockCountItem,
    InventoryStockCountHistory, InventoryStockCountAttachment,
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderHistory,
    PurchaseOrderAttachment, PurchaseReceipt, PurchaseReceiptItem,
    InventoryGoodsReceipt, InventoryGoodsReceiptItem,
    InventoryGoodsReceiptHistory, InventoryGoodsReceiptAttachment,
    InventorySupplierInvoice, InventorySupplierInvoiceItem,
    InventorySupplierInvoiceHistory, InventorySupplierInvoiceAttachment,
    InventoryPurchaseReturn, InventoryPurchaseReturnItem,
    InventoryPurchaseReturnHistory, InventoryPurchaseReturnAttachment,
    InventorySupplierPayment, InventorySupplierPaymentAllocation,
    InventorySupplierPaymentHistory, InventorySupplierPaymentAttachment,
)


# ============================================================================
# CATEGORY SERIALIZERS
# ============================================================================

class CategoryTreeSerializer(serializers.ModelSerializer):
    """Nested serializer for tree view with item counts."""
    children = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.category_name', read_only=True, default='')

    class Meta:
        model = ItemCategory
        fields = [
            'id', 'category_code', 'category_name', 'parent', 'parent_name',
            'description', 'status', 'item_count', 'children',
            'created_at', 'updated_at',
        ]

    def get_children(self, obj):
        qs = obj.children.all()
        if 'status' in self.context.get('filters', {}):
            qs = qs.filter(status=self.context['filters']['status'])
        return CategoryTreeSerializer(qs, many=True, context=self.context).data

    def get_item_count(self, obj):
        return obj.items.count()


class ItemCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.category_name', read_only=True, default='')

    class Meta:
        model = ItemCategory
        fields = [
            'id', 'category_code', 'category_name', 'parent', 'parent_name',
            'description', 'status', 'item_count', 'children',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_children(self, obj):
        return ItemCategorySerializer(obj.children.all(), many=True).data

    def get_item_count(self, obj):
        return obj.items.count()

    def validate(self, data):
        tenant_id = self.context['request'].user.organization_id
        category_code = data.get('category_code')
        instance = self.instance

        if category_code:
            qs = ItemCategory.objects.filter(
                tenant_id=tenant_id,
                category_code=category_code
            )
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'category_code': f"Category code '{category_code}' already exists."
                })
        return data


class ItemCategoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdown/reference data."""
    parent_name = serializers.CharField(source='parent.category_name', read_only=True, default='')

    class Meta:
        model = ItemCategory
        fields = ['id', 'category_code', 'category_name', 'parent_name', 'status']


# ============================================================================
# UNIT SERIALIZERS
# ============================================================================

class UnitConversionSerializer(serializers.ModelSerializer):
    from_unit_name = serializers.CharField(source='from_unit.unit_name', read_only=True)
    to_unit_name = serializers.CharField(source='to_unit.unit_name', read_only=True)

    class Meta:
        model = UnitConversion
        fields = [
            'id', 'from_unit', 'from_unit_name', 'to_unit', 'to_unit_name',
            'conversion_factor', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        tenant_id = self.context['request'].user.organization_id
        from_unit = data.get('from_unit')
        to_unit = data.get('to_unit')

        if from_unit and to_unit and from_unit == to_unit:
            raise serializers.ValidationError(
                "Cannot create a conversion between the same unit."
            )

        if from_unit and to_unit:
            qs = UnitConversion.objects.filter(
                tenant_id=tenant_id,
                from_unit=from_unit,
                to_unit=to_unit,
            )
            instance = self.instance
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError(
                    "This conversion already exists."
                )

        if 'conversion_factor' in data and data.get('conversion_factor', 0) <= 0:
            raise serializers.ValidationError({
                'conversion_factor': 'Conversion factor must be greater than 0.'
            })

        return data


class UnitSerializer(serializers.ModelSerializer):
    conversions = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            'id', 'unit_code', 'unit_name', 'symbol', 'description',
            'status', 'conversions', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_conversions(self, obj):
        conversions_from = UnitConversion.objects.filter(from_unit=obj)
        conversions_to = UnitConversion.objects.filter(to_unit=obj)
        qs = list(conversions_from) + list(conversions_to)
        return UnitConversionSerializer(qs, many=True).data

    def validate(self, data):
        tenant_id = self.context['request'].user.organization_id
        unit_code = data.get('unit_code')
        instance = self.instance

        if unit_code:
            qs = Unit.objects.filter(
                tenant_id=tenant_id,
                unit_code=unit_code
            )
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'unit_code': f"Unit code '{unit_code}' already exists."
                })
        return data


class UnitListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdown/reference data."""
    class Meta:
        model = Unit
        fields = ['id', 'unit_code', 'unit_name', 'symbol', 'status']


# ============================================================================
# BRAND SERIALIZERS
# ============================================================================

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = [
            'id', 'brand_code', 'brand_name', 'description',
            'logo_url', 'website', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        tenant_id = self.context['request'].user.organization_id
        brand_code = data.get('brand_code')
        instance = self.instance

        if brand_code:
            qs = Brand.objects.filter(
                tenant_id=tenant_id,
                brand_code=brand_code
            )
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'brand_code': f"Brand code '{brand_code}' already exists."
                })
        return data


class BrandListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdown/reference data."""
    class Meta:
        model = Brand
        fields = ['id', 'brand_code', 'brand_name', 'status']


# ============================================================================
# INVENTORY ITEM SERIALIZERS
# ============================================================================

class InventoryItemListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True, default='')
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True, default='')
    brand_name = serializers.CharField(source='brand.brand_name', read_only=True, default='')

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'item_code', 'item_name', 'category', 'category_name',
            'sub_category', 'unit', 'unit_name', 'brand', 'brand_name',
            'description', 'image_url', 'status', 'tags',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True, default='')
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True, default='')
    brand_name = serializers.CharField(source='brand.brand_name', read_only=True, default='')

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'item_code', 'item_name', 'category', 'category_name',
            'sub_category', 'unit', 'unit_name', 'brand', 'brand_name',
            'description', 'image_url', 'status', 'custom_fields', 'tags',
            'imported_from', 'cloned_from',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'cloned_from']

    def validate(self, data):
        """Ensure item_code is unique per tenant."""
        tenant_id = self.context['request'].user.organization_id
        item_code = data.get('item_code')
        instance = self.instance

        if item_code:
            qs = InventoryItem.objects.filter(
                tenant_id=tenant_id,
                item_code=item_code
            )
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'item_code': f"Item code '{item_code}' already exists."
                })

        return data


class CustomFieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomFieldDefinition
        fields = [
            'id', 'field_name', 'field_label', 'field_type',
            'options', 'is_required', 'order', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# STOCK SERIALIZERS
# ============================================================================

class StockLedgerSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    location_name = serializers.CharField(
        source='location.location_name', read_only=True, default=''
    )

    class Meta:
        model = StockLedger
        fields = [
            'id', 'item', 'item_code', 'item_name',
            'location', 'location_name',
            'transaction_type', 'quantity',
            'unit_cost', 'total_cost',
            'reference_type', 'reference_id',
            'description', 'created_by', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CreateLedgerEntrySerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    location_id = serializers.UUIDField(required=False, allow_null=True)
    transaction_type = serializers.ChoiceField(choices=StockLedger.TRANSACTION_TYPES)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=4)
    unit_cost = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, allow_null=True
    )
    reference_type = serializers.CharField(required=False, allow_blank=True)
    reference_id = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class StockAvailabilitySerializer(serializers.Serializer):
    """Read-only serializer for stock availability data."""
    item_id = serializers.UUIDField()
    item_code = serializers.CharField()
    item_name = serializers.CharField()
    category_name = serializers.CharField(default='')
    brand_name = serializers.CharField(default='')
    unit_name = serializers.CharField(default='')
    physical = serializers.DecimalField(max_digits=20, decimal_places=4)
    reserved = serializers.DecimalField(max_digits=20, decimal_places=4)
    available = serializers.DecimalField(max_digits=20, decimal_places=4)
    in_transit = serializers.DecimalField(max_digits=20, decimal_places=4)
    damaged = serializers.DecimalField(max_digits=20, decimal_places=4)
    cost_price = serializers.DecimalField(
        max_digits=20, decimal_places=4, allow_null=True
    )
    selling_price = serializers.DecimalField(
        max_digits=20, decimal_places=4, allow_null=True
    )
    cost_value = serializers.DecimalField(max_digits=20, decimal_places=4)
    selling_value = serializers.DecimalField(max_digits=20, decimal_places=4)
    min_stock_level = serializers.DecimalField(
        max_digits=20, decimal_places=4, allow_null=True
    )
    reorder_level = serializers.DecimalField(
        max_digits=20, decimal_places=4, allow_null=True
    )
    max_stock_level = serializers.DecimalField(
        max_digits=20, decimal_places=4, allow_null=True
    )


class LowStockSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    item_code = serializers.CharField()
    item_name = serializers.CharField()
    current_stock = serializers.DecimalField(max_digits=20, decimal_places=4)
    min_stock_level = serializers.DecimalField(max_digits=20, decimal_places=4)
    reorder_level = serializers.DecimalField(
        max_digits=20, decimal_places=4, allow_null=True
    )
    suggested_purchase = serializers.DecimalField(max_digits=20, decimal_places=4)


class InventoryValuationSerializer(serializers.Serializer):
    items = serializers.ListField()
    summary = serializers.DictField()


# ============================================================================
# TRANSFER SERIALIZERS
# ============================================================================

class TransferItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)

    class Meta:
        model = InventoryTransferItem
        fields = [
            'id', 'item', 'item_code', 'item_name',
            'quantity', 'received_quantity', 'damaged_quantity', 'remarks',
        ]
        read_only_fields = ['id']


class TransferAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryTransferAttachment
        fields = ['id', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class TransferListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    source_name = serializers.CharField(
        source='source_location.location_name', read_only=True
    )
    destination_name = serializers.CharField(
        source='destination_location.location_name', read_only=True
    )
    item_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryTransfer
        fields = [
            'id', 'transfer_number', 'transfer_date',
            'source_location', 'source_name',
            'destination_location', 'destination_name',
            'transfer_type', 'status',
            'item_count', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class TransferDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested items."""
    items = TransferItemSerializer(many=True, read_only=True)
    attachments = TransferAttachmentSerializer(many=True, read_only=True)
    source_name = serializers.CharField(
        source='source_location.location_name', read_only=True
    )
    destination_name = serializers.CharField(
        source='destination_location.location_name', read_only=True
    )
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryTransfer
        fields = [
            'id', 'tenant_id', 'transfer_number', 'transfer_date',
            'source_location', 'source_name',
            'destination_location', 'destination_name',
            'transfer_type', 'status',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_notes',
            'dispatched_at', 'received_at', 'received_by', 'received_by_name',
            'remarks',
            'items', 'attachments',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'transfer_number', 'status',
            'approved_at', 'dispatched_at', 'received_at',
            'created_at', 'updated_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return ''

    def get_received_by_name(self, obj):
        if obj.received_by:
            return obj.received_by.get_full_name() or obj.received_by.email
        return ''


class CreateTransferSerializer(serializers.Serializer):
    """Serializer for creating a transfer."""
    transfer_date = serializers.DateField(required=False)
    source_location = serializers.UUIDField()
    destination_location = serializers.UUIDField()
    transfer_type = serializers.ChoiceField(
        choices=InventoryTransfer.TRANSFER_TYPES, default='STANDARD'
    )
    remarks = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(min_length=1)

    def validate_items(self, items):
        for item in items:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have 'item_id'.")
            if 'quantity' not in item:
                raise serializers.ValidationError("Each item must have 'quantity'.")
            if float(item['quantity']) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return items

    def validate(self, data):
        if data['source_location'] == data['destination_location']:
            raise serializers.ValidationError(
                "Source and destination must be different."
            )
        return data


class TransferHistorySerializer(serializers.ModelSerializer):
    """Serializer for transfer history/audit trail."""
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryTransferHistory
        fields = [
            'id', 'transfer', 'action',
            'from_status', 'to_status',
            'performed_by', 'performed_by_name',
            'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class ReceiveTransferSerializer(serializers.Serializer):
    """Serializer for receiving a transfer with optional partial receipt."""
    items = serializers.ListField(required=False)

    def validate_items(self, items):
        if not items:
            return items
        for item in items:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have 'item_id'.")
            received = item.get('received_quantity', 0)
            damaged = item.get('damaged_quantity', 0)
            if float(received) < 0 or float(damaged) < 0:
                raise serializers.ValidationError("Quantities cannot be negative.")
        return items


# ============================================================================
# ADJUSTMENT SERIALIZERS (Section 7)
# ============================================================================

class AdjustmentReasonSerializer(serializers.ModelSerializer):
    """Serializer for adjustment reasons."""
    class Meta:
        model = InventoryAdjustmentReason
        fields = [
            'id', 'reason_code', 'reason_name', 'adjustment_type',
            'description', 'status', 'is_default',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AdjustmentReasonListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdown."""
    class Meta:
        model = InventoryAdjustmentReason
        fields = ['id', 'reason_code', 'reason_name', 'adjustment_type', 'status']


class AdjustmentItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True, default='')

    class Meta:
        model = InventoryAdjustmentItem
        fields = [
            'id', 'item', 'item_code', 'item_name',
            'available_quantity', 'adjustment_quantity',
            'unit', 'unit_name', 'remarks',
        ]
        read_only_fields = ['id', 'available_quantity']


class AdjustmentAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryAdjustmentAttachment
        fields = ['id', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class AdjustmentHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAdjustmentHistory
        fields = [
            'id', 'adjustment', 'action',
            'from_status', 'to_status',
            'performed_by', 'performed_by_name',
            'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class AdjustmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    location_name = serializers.CharField(
        source='location.location_name', read_only=True
    )
    reason_name = serializers.CharField(
        source='reason.reason_name', read_only=True
    )
    item_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAdjustment
        fields = [
            'id', 'adjustment_number', 'adjustment_date',
            'location', 'location_name',
            'adjustment_type', 'reason', 'reason_name',
            'status', 'item_count', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class AdjustmentDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested items."""
    items = AdjustmentItemSerializer(many=True, read_only=True)
    attachments = AdjustmentAttachmentSerializer(many=True, read_only=True)
    location_name = serializers.CharField(
        source='location.location_name', read_only=True
    )
    reason_name = serializers.CharField(
        source='reason.reason_name', read_only=True
    )
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    applied_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAdjustment
        fields = [
            'id', 'tenant_id', 'adjustment_number', 'adjustment_date',
            'location', 'location_name',
            'adjustment_type', 'reason', 'reason_name',
            'status',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_notes',
            'applied_by', 'applied_by_name', 'applied_at',
            'remarks',
            'items', 'attachments',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'adjustment_number', 'status',
            'approved_at', 'applied_at',
            'created_at', 'updated_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return ''

    def get_applied_by_name(self, obj):
        if obj.applied_by:
            return obj.applied_by.get_full_name() or obj.applied_by.email
        return ''


class CreateAdjustmentSerializer(serializers.Serializer):
    """Serializer for creating an adjustment."""
    adjustment_date = serializers.DateField(required=False)
    location = serializers.UUIDField()
    reason = serializers.UUIDField()
    remarks = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(min_length=1)

    def validate_items(self, items):
        for item in items:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have 'item_id'.")
            if 'adjustment_quantity' not in item:
                raise serializers.ValidationError("Each item must have 'adjustment_quantity'.")
            qty = float(item['adjustment_quantity'])
            if qty <= 0:
                raise serializers.ValidationError("Adjustment quantity must be greater than 0.")
        return items

    def validate_reason(self, reason_id):
        from inventory.models import InventoryAdjustmentReason
        try:
            reason = InventoryAdjustmentReason.objects.get(id=reason_id)
        except InventoryAdjustmentReason.DoesNotExist:
            raise serializers.ValidationError("Adjustment reason not found.")
        if reason.status != 'ACTIVE':
            raise serializers.ValidationError("Adjustment reason is not active.")
        return reason_id

    def validate_location(self, location_id):
        from inventory.models import InventoryLocation
        try:
            loc = InventoryLocation.objects.get(id=location_id)
        except InventoryLocation.DoesNotExist:
            raise serializers.ValidationError("Location not found.")
        if loc.status != 'ACTIVE':
            raise serializers.ValidationError("Location is not active.")
        return location_id


# ============================================================================
# RESERVATION SERIALIZERS (Section 8)
# ============================================================================

class ReservationReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryReservationReason
        fields = [
            'id', 'reason_code', 'reason_name', 'description',
            'status', 'is_default', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReservationReasonListSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryReservationReason
        fields = ['id', 'reason_code', 'reason_name', 'status']


class ReservationItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True, default='')

    class Meta:
        model = InventoryReservationItem
        fields = [
            'id', 'item', 'item_code', 'item_name',
            'requested_quantity', 'reserved_quantity', 'fulfilled_quantity',
            'remaining_quantity', 'unit', 'unit_name', 'remarks',
        ]
        read_only_fields = ['id', 'reserved_quantity', 'fulfilled_quantity', 'remaining_quantity']


class ReservationAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryReservationAttachment
        fields = ['id', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class ReservationHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryReservationHistory
        fields = [
            'id', 'reservation', 'action',
            'from_status', 'to_status',
            'performed_by', 'performed_by_name',
            'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class ReservationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    source_name = serializers.CharField(
        source='source_location.location_name', read_only=True
    )
    reason_name = serializers.CharField(
        source='reason.reason_name', read_only=True, default=''
    )
    item_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryReservation
        fields = [
            'id', 'reservation_number', 'reservation_date', 'expiry_date',
            'source_location', 'source_name',
            'reservation_type', 'status', 'priority',
            'customer_name', 'reference_number',
            'reason', 'reason_name',
            'item_count', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class ReservationDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested items."""
    items = ReservationItemSerializer(many=True, read_only=True)
    attachments = ReservationAttachmentSerializer(many=True, read_only=True)
    source_name = serializers.CharField(
        source='source_location.location_name', read_only=True
    )
    reason_name = serializers.CharField(
        source='reason.reason_name', read_only=True, default=''
    )
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryReservation
        fields = [
            'id', 'tenant_id', 'reservation_number', 'reservation_date', 'expiry_date',
            'source_location', 'source_name',
            'reservation_type', 'status', 'priority',
            'customer_name', 'reference_number',
            'reason', 'reason_name',
            'remarks',
            'items', 'attachments',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'reservation_number', 'status',
            'created_at', 'updated_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class CreateReservationSerializer(serializers.Serializer):
    """Serializer for creating a reservation."""
    reservation_date = serializers.DateField(required=False)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    source_location = serializers.UUIDField()
    reservation_type = serializers.ChoiceField(
        choices=InventoryReservation.RESERVATION_TYPES, default='OTHER'
    )
    priority = serializers.ChoiceField(
        choices=InventoryReservation.PRIORITY_CHOICES, default='MEDIUM'
    )
    customer_name = serializers.CharField(required=False, allow_blank=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.UUIDField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(min_length=1)

    def validate_items(self, items):
        for item in items:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have 'item_id'.")
            if 'requested_quantity' not in item:
                raise serializers.ValidationError("Each item must have 'requested_quantity'.")
            if float(item['requested_quantity']) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return items

    def validate_source_location(self, location_id):
        try:
            loc = InventoryLocation.objects.get(id=location_id)
        except InventoryLocation.DoesNotExist:
            raise serializers.ValidationError("Source location not found.")
        if loc.status != 'ACTIVE':
            raise serializers.ValidationError("Source location is not active.")
        return location_id


class FulfillReservationSerializer(serializers.Serializer):
    """Serializer for fulfilling a reservation."""
    items = serializers.ListField(required=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("At least one item is required.")
        for item in items:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have 'item_id'.")
            fulfilled = float(item.get('fulfilled_quantity', 0))
            if fulfilled <= 0:
                raise serializers.ValidationError("Fulfilled quantity must be greater than 0.")
        return items


# ============================================================================
# STOCK COUNT SERIALIZERS (Section 9)
# ============================================================================

class StockCountReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockCountReason
        fields = [
            'id', 'reason_code', 'reason_name', 'description',
            'status', 'is_default', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StockCountReasonListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdown."""
    class Meta:
        model = StockCountReason
        fields = ['id', 'reason_code', 'reason_name', 'status']


class StockCountItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True, default='')
    counted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryStockCountItem
        fields = [
            'id', 'item', 'item_code', 'item_name',
            'expected_quantity', 'reserved_quantity_at_count',
            'counted_quantity', 'counted_by', 'counted_by_name', 'counted_at',
            'scanned_barcode', 'difference_quantity',
            'unit', 'unit_name', 'remarks',
        ]
        read_only_fields = ['id', 'difference_quantity', 'counted_at']

    def get_counted_by_name(self, obj):
        if obj.counted_by:
            return obj.counted_by.get_full_name() or obj.counted_by.email
        return ''


class StockCountAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryStockCountAttachment
        fields = ['id', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class StockCountHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryStockCountHistory
        fields = [
            'id', 'count', 'action',
            'from_status', 'to_status',
            'performed_by', 'performed_by_name',
            'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class StockCountListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    location_name = serializers.CharField(
        source='location.location_name', read_only=True
    )
    reason_name = serializers.CharField(
        source='reason.reason_name', read_only=True
    )
    item_count = serializers.SerializerMethodField()
    counters_list = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryStockCount
        fields = [
            'id', 'count_number', 'count_date', 'count_type',
            'location', 'location_name',
            'reason', 'reason_name',
            'status',
            'item_count',
            'total_items_counted',
            'total_items_with_difference',
            'counters_list',
            'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_counters_list(self, obj):
        return [
            {
                'id': str(u.id),
                'name': u.get_full_name() or u.email
            }
            for u in obj.assigned_counters.all()
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class StockCountDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested items, attachments, and counters."""
    items = StockCountItemSerializer(many=True, read_only=True)
    attachments = StockCountAttachmentSerializer(many=True, read_only=True)
    location_name = serializers.CharField(
        source='location.location_name', read_only=True
    )
    category_name = serializers.CharField(
        source='category.category_name', read_only=True, default=''
    )
    reason_name = serializers.CharField(
        source='reason.reason_name', read_only=True
    )
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    completed_by_name = serializers.SerializerMethodField()
    assigned_counters_detail = serializers.SerializerMethodField()
    generated_adjustment_number = serializers.SerializerMethodField()

    class Meta:
        model = InventoryStockCount
        fields = [
            'id', 'tenant_id', 'count_number', 'count_date', 'count_type',
            'location', 'location_name',
            'category', 'category_name',
            'reason', 'reason_name',
            'status',
            'assigned_counters', 'assigned_counters_detail',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_notes',
            'completed_by', 'completed_by_name', 'completed_at',
            'total_items_counted', 'total_items_with_difference',
            'total_difference_value',
            'generated_adjustment', 'generated_adjustment_number',
            'remarks',
            'items', 'attachments',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'count_number', 'status',
            'total_items_counted', 'total_items_with_difference',
            'total_difference_value', 'generated_adjustment',
            'approved_at', 'completed_at',
            'created_at', 'updated_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return ''

    def get_completed_by_name(self, obj):
        if obj.completed_by:
            return obj.completed_by.get_full_name() or obj.completed_by.email
        return ''

    def get_assigned_counters_detail(self, obj):
        return [
            {
                'id': str(u.id),
                'name': u.get_full_name() or u.email,
                'email': u.email,
            }
            for u in obj.assigned_counters.all()
        ]

    def get_generated_adjustment_number(self, obj):
        if obj.generated_adjustment:
            return obj.generated_adjustment.adjustment_number
        return None


class CreateStockCountSerializer(serializers.Serializer):
    """Serializer for creating a stock count."""
    count_date = serializers.DateField(required=False)
    count_type = serializers.ChoiceField(
        choices=InventoryStockCount.COUNT_TYPES, default='CYCLE'
    )
    location = serializers.UUIDField()
    category = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.UUIDField()
    assigned_counters = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate_reason(self, reason_id):
        try:
            reason = StockCountReason.objects.get(id=reason_id)
        except StockCountReason.DoesNotExist:
            raise serializers.ValidationError("Stock count reason not found.")
        if reason.status != 'ACTIVE':
            raise serializers.ValidationError("Stock count reason is not active.")
        return reason_id

    def validate_location(self, location_id):
        try:
            loc = InventoryLocation.objects.get(id=location_id)
        except InventoryLocation.DoesNotExist:
            raise serializers.ValidationError("Location not found.")
        if loc.status != 'ACTIVE':
            raise serializers.ValidationError("Location is not active.")
        return location_id


class UpdateStockCountSerializer(serializers.Serializer):
    """Serializer for updating a stock count (DRAFT/ASSIGNED only)."""
    count_date = serializers.DateField(required=False)
    count_type = serializers.ChoiceField(
        choices=InventoryStockCount.COUNT_TYPES, required=False
    )
    location = serializers.UUIDField(required=False)
    category = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.UUIDField(required=False)
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate_reason(self, reason_id):
        try:
            reason = StockCountReason.objects.get(id=reason_id)
        except StockCountReason.DoesNotExist:
            raise serializers.ValidationError("Stock count reason not found.")
        if reason.status != 'ACTIVE':
            raise serializers.ValidationError("Stock count reason is not active.")
        return reason_id

    def validate_location(self, location_id):
        try:
            loc = InventoryLocation.objects.get(id=location_id)
        except InventoryLocation.DoesNotExist:
            raise serializers.ValidationError("Location not found.")
        if loc.status != 'ACTIVE':
            raise serializers.ValidationError("Location is not active.")
        return location_id


class CountItemSerializer(serializers.Serializer):
    """Serializer for counting a single item during stock count."""
    item_id = serializers.UUIDField()
    counted_quantity = serializers.DecimalField(
        max_digits=20, decimal_places=4,
        required=True
    )
    scanned_barcode = serializers.CharField(
        required=False, allow_blank=True, default=''
    )
    remarks = serializers.CharField(
        required=False, allow_blank=True, default=''
    )


class SaveCountProgressSerializer(serializers.Serializer):
    """Serializer for saving stock count progress."""
    items = serializers.ListField(
        child=CountItemSerializer(),
        required=True,
    )


class AssignCountersSerializer(serializers.Serializer):
    """Serializer for assigning counters to a stock count."""
    assigned_counters = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1,
    )


class StockCountDifferenceSerializer(serializers.Serializer):
    """Read-only serializer for difference summary."""
    item_id = serializers.UUIDField()
    item_code = serializers.CharField()
    item_name = serializers.CharField()
    expected_quantity = serializers.DecimalField(max_digits=20, decimal_places=4)
    counted_quantity = serializers.DecimalField(max_digits=20, decimal_places=4, allow_null=True)
    difference_quantity = serializers.DecimalField(max_digits=20, decimal_places=4)
    cost_price = serializers.DecimalField(max_digits=20, decimal_places=4, allow_null=True)
    difference_value = serializers.DecimalField(max_digits=20, decimal_places=4)
    status = serializers.CharField()  # 'MATCH', 'SURPLUS', 'SHORTAGE', 'UNCOUNTED'


# ============================================================================
# BULK IMPORT SERIALIZER
# ============================================================================

class BulkImportSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate_items(self, items):
        errors = []
        validated = []

        for idx, item in enumerate(items):
            item_errors = {}

            item_code = item.get('item_code', '').strip()
            item_name = item.get('item_name', '').strip()

            if not item_code:
                item_errors['item_code'] = 'Item code is required.'
            if not item_name:
                item_errors['item_name'] = 'Item name is required.'

            if item_errors:
                errors.append({'index': idx, 'errors': item_errors})
            else:
                validated.append(item)

        if errors:
            raise serializers.ValidationError({
                'validation_errors': errors,
                'valid_count': len(validated),
                'error_count': len(errors),
            })

        return validated


# ============================================================================
# LOCATION TYPE SERIALIZERS
# ============================================================================

class LocationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLocationType
        fields = [
            'id', 'type_code', 'type_name', 'description', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        tenant_id = self.context['request'].user.organization_id
        type_code = data.get('type_code')
        instance = self.instance

        if type_code:
            qs = InventoryLocationType.objects.filter(
                tenant_id=tenant_id,
                type_code=type_code
            )
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'type_code': f"Type code '{type_code}' already exists."
                })
        return data


class LocationTypeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdown/reference data."""
    class Meta:
        model = InventoryLocationType
        fields = ['id', 'type_code', 'type_name', 'status']


# ============================================================================
# LOCATION SERIALIZERS
# ============================================================================

class LocationTreeSerializer(serializers.ModelSerializer):
    """Nested serializer for tree view."""
    children = serializers.SerializerMethodField()
    location_type_name = serializers.CharField(
        source='location_type.type_name', read_only=True, default=''
    )
    parent_name = serializers.CharField(
        source='parent_location.location_name', read_only=True, default=''
    )
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryLocation
        fields = [
            'id', 'location_code', 'location_name', 'location_type',
            'location_type_name', 'parent_location', 'parent_name',
            'city', 'state', 'country', 'status',
            'manager', 'manager_name',
            'children', 'created_at', 'updated_at',
        ]

    def get_children(self, obj):
        qs = obj.child_locations.all()
        filters = self.context.get('filters', {})
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        return LocationTreeSerializer(qs, many=True, context=self.context).data

    def get_manager_name(self, obj):
        if obj.manager:
            return obj.manager.get_full_name() or obj.manager.email
        return ''


class LocationSerializer(serializers.ModelSerializer):
    location_type_name = serializers.CharField(
        source='location_type.type_name', read_only=True, default=''
    )
    parent_name = serializers.CharField(
        source='parent_location.location_name', read_only=True, default=''
    )
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryLocation
        fields = [
            'id', 'location_code', 'location_name',
            'location_type', 'location_type_name',
            'parent_location', 'parent_name',
            'address', 'city', 'state', 'country', 'postal_code',
            'phone', 'email', 'contact_person', 'mobile',
            'manager', 'manager_name',
            'status',
            'max_capacity', 'capacity_unit',
            'allow_reservations', 'allow_transfers',
            'allow_sales', 'allow_purchases', 'allow_audits',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_manager_name(self, obj):
        if obj.manager:
            return obj.manager.get_full_name() or obj.manager.email
        return ''

    def validate(self, data):
        tenant_id = self.context['request'].user.organization_id
        location_code = data.get('location_code')
        instance = self.instance

        if location_code:
            qs = InventoryLocation.objects.filter(
                tenant_id=tenant_id,
                location_code=location_code
            )
            if instance:
                qs = qs.exclude(id=instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'location_code': f"Location code '{location_code}' already exists."
                })
        return data


class LocationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list/dropdown."""
    location_type_name = serializers.CharField(
        source='location_type.type_name', read_only=True, default=''
    )
    parent_name = serializers.CharField(
        source='parent_location.location_name', read_only=True, default=''
    )

    class Meta:
        model = InventoryLocation
        fields = [
            'id', 'location_code', 'location_name',
            'location_type', 'location_type_name',
            'parent_location', 'parent_name',
            'city', 'state', 'country', 'status',
        ]



# ============================================================================
# PURCHASE ORDER SERIALIZERS (Section 10)
# ============================================================================

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    """Serializer for purchase order line items."""
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    unit_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'item', 'item_code', 'item_name', 'unit_name',
            'ordered_quantity', 'received_quantity', 'outstanding_quantity',
            'unit_price', 'tax_rate', 'discount_rate', 'line_total', 'remarks',
        ]
        read_only_fields = ['id', 'received_quantity', 'outstanding_quantity', 'line_total']

    def get_unit_name(self, obj):
        if obj.item and obj.item.unit:
            return obj.item.unit.unit_name
        return ''


class PurchaseOrderAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderAttachment
        fields = ['id', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class PurchaseOrderHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrderHistory
        fields = [
            'id', 'purchase_order', 'action',
            'from_status', 'to_status',
            'performed_by', 'performed_by_name',
            'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class PurchaseReceiptItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)

    class Meta:
        model = PurchaseReceiptItem
        fields = [
            'id', 'item', 'item_code', 'item_name',
            'received_quantity', 'unit_price',
        ]
        read_only_fields = ['id']


class PurchaseReceiptListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for receipt list views."""
    created_by_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseReceipt
        fields = [
            'id', 'receipt_number', 'receipt_date',
            'purchase_order', 'location', 'notes',
            'item_count', 'created_by_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class PurchaseReceiptDetailSerializer(serializers.ModelSerializer):
    """Full receipt serializer with items."""
    items = PurchaseReceiptItemSerializer(many=True, read_only=True)
    order_number = serializers.CharField(
        source='purchase_order.order_number', read_only=True
    )
    location_name = serializers.CharField(
        source='location.location_name', read_only=True, default=''
    )
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseReceipt
        fields = [
            'id', 'tenant_id', 'receipt_number', 'receipt_date',
            'purchase_order', 'order_number',
            'location', 'location_name',
            'notes', 'items',
            'created_by', 'created_by_name',
            'created_at',
        ]
        read_only_fields = ['id', 'tenant_id', 'created_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    supplier_name_display = serializers.SerializerMethodField()
    location_name = serializers.CharField(
        source='location.location_name', read_only=True, default=''
    )
    item_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_number', 'order_date', 'expected_delivery_date',
            'supplier', 'supplier_name', 'supplier_name_display',
            'supplier_reference',
            'location', 'location_name',
            'status',
            'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
            'item_count', 'created_by_name',
            'sent_at', 'closed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_supplier_name_display(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name or ''


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested items, attachments, receipts, and history."""
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    attachments = PurchaseOrderAttachmentSerializer(many=True, read_only=True)
    supplier_name_display = serializers.SerializerMethodField()
    location_name = serializers.CharField(
        source='location.location_name', read_only=True, default=''
    )
    created_by_name = serializers.SerializerMethodField()
    receipt_count = serializers.SerializerMethodField()
    total_received_value = serializers.SerializerMethodField()
    receipt_numbers = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'tenant_id', 'order_number', 'order_date', 'expected_delivery_date',
            'supplier', 'supplier_name', 'supplier_name_display',
            'supplier_reference',
            'location', 'location_name',
            'status',
            'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
            'notes', 'terms',
            'items', 'attachments',
            'receipt_count', 'total_received_value', 'receipt_numbers',
            'sent_at', 'closed_at',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'order_number', 'status',
            'subtotal', 'total_amount',
            'sent_at', 'closed_at',
            'created_at', 'updated_at',
        ]

    def get_supplier_name_display(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return obj.supplier_name or ''

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_receipt_count(self, obj):
        return obj.receipts.count()

    def get_total_received_value(self, obj):
        total = sum(
            item.received_quantity * item.unit_price
            for item in obj.items.all()
        )
        return total

    def get_receipt_numbers(self, obj):
        return [
            {
                'id': str(r.id),
                'receipt_number': r.receipt_number,
                'receipt_date': r.receipt_date,
            }
            for r in obj.receipts.all()
        ]


class CreatePurchaseOrderSerializer(serializers.Serializer):
    """Serializer for creating a purchase order."""
    order_date = serializers.DateField(required=False)
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True)
    supplier_reference = serializers.CharField(required=False, allow_blank=True)
    location = serializers.UUIDField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, default=0
    )
    discount_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, default=0
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    terms = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(min_length=1)

    def validate_items(self, items):
        for item in items:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have 'item_id'.")
            if 'quantity' not in item:
                raise serializers.ValidationError("Each item must have 'quantity'.")
            if float(item['quantity']) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return items

    def validate_supplier(self, supplier_id):
        if not supplier_id:
            return supplier_id
        from contacts.models import Contact
        try:
            Contact.objects.get(id=supplier_id)
        except Contact.DoesNotExist:
            raise serializers.ValidationError("Supplier not found.")
        return supplier_id

    def validate_location(self, location_id):
        if not location_id:
            return location_id
        from inventory.models import InventoryLocation
        try:
            loc = InventoryLocation.objects.get(id=location_id)
        except InventoryLocation.DoesNotExist:
            raise serializers.ValidationError("Location not found.")
        if loc.status != 'ACTIVE':
            raise serializers.ValidationError("Location is not active.")
        return location_id


class UpdatePurchaseOrderSerializer(serializers.Serializer):
    """Serializer for updating a DRAFT purchase order."""
    order_date = serializers.DateField(required=False)
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True)
    supplier_reference = serializers.CharField(required=False, allow_blank=True)
    location = serializers.UUIDField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False
    )
    discount_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    terms = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(required=False)

    def validate_items(self, items):
        if not items:
            return items
        for item in items:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have 'item_id'.")
            if 'quantity' not in item:
                raise serializers.ValidationError("Each item must have 'quantity'.")
            if float(item['quantity']) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return items


class ReceivePurchaseSerializer(serializers.Serializer):
    """Serializer for receiving items against a purchase order."""
    items = serializers.ListField(min_length=1)

    def validate_items(self, items):
        for item in items:
            if 'ordered_item_id' not in item:
                raise serializers.ValidationError("Each item must have 'ordered_item_id'.")
            if 'received_quantity' not in item:
                raise serializers.ValidationError("Each item must have 'received_quantity'.")
            received = float(item['received_quantity'])
            if received <= 0:
                raise serializers.ValidationError("Received quantity must be greater than 0.")
        return items


# ============================================================================
# GOODS RECEIPT NOTE SERIALIZERS (Section 11)
# ============================================================================

class GRNItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    unit_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryGoodsReceiptItem
        fields = [
            'id', 'item', 'item_code', 'item_name', 'unit_name',
            'purchase_order_item',
            'ordered_quantity', 'received_quantity',
            'accepted_quantity', 'rejected_quantity', 'damage_quantity',
            'unit_price', 'remarks',
        ]
        read_only_fields = ['id']

    def get_unit_name(self, obj):
        if obj.item and obj.item.unit:
            return obj.item.unit.unit_name
        return ''


class GRNAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryGoodsReceiptAttachment
        fields = ['id', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class GRNHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryGoodsReceiptHistory
        fields = [
            'id', 'goods_receipt', 'action',
            'from_status', 'to_status',
            'performed_by', 'performed_by_name',
            'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class GRNListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    purchase_order_number = serializers.CharField(
        source='purchase_order.order_number', read_only=True
    )
    location_name = serializers.CharField(
        source='location.location_name', read_only=True, default=''
    )
    item_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    supplier_display = serializers.SerializerMethodField()

    class Meta:
        model = InventoryGoodsReceipt
        fields = [
            'id', 'grn_number', 'receipt_date',
            'purchase_order', 'purchase_order_number',
            'supplier', 'supplier_name', 'supplier_display',
            'location', 'location_name',
            'status', 'remarks',
            'item_count', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_supplier_display(self, obj):
        if obj.supplier:
            return getattr(obj.supplier, 'name', '')
        return obj.supplier_name or ''


class GRNDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested items, attachments, and history."""
    items = GRNItemSerializer(many=True, read_only=True)
    attachments = GRNAttachmentSerializer(many=True, read_only=True)
    purchase_order_number = serializers.CharField(
        source='purchase_order.order_number', read_only=True
    )
    location_name = serializers.CharField(
        source='location.location_name', read_only=True, default=''
    )
    supplier_display = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    received_by_name = serializers.SerializerMethodField()
    completed_by_name = serializers.SerializerMethodField()
    total_received_quantity = serializers.SerializerMethodField()
    total_accepted_quantity = serializers.SerializerMethodField()
    total_rejected_quantity = serializers.SerializerMethodField()
    total_damage_quantity = serializers.SerializerMethodField()

    class Meta:
        model = InventoryGoodsReceipt
        fields = [
            'id', 'tenant_id', 'grn_number', 'receipt_date',
            'purchase_order', 'purchase_order_number',
            'supplier', 'supplier_name', 'supplier_display',
            'location', 'location_name',
            'status', 'remarks',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_notes',
            'received_by', 'received_by_name', 'received_at',
            'completed_by', 'completed_by_name', 'completed_at',
            'total_received_quantity', 'total_accepted_quantity',
            'total_rejected_quantity', 'total_damage_quantity',
            'items', 'attachments',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'grn_number', 'status',
            'approved_at', 'received_at', 'completed_at',
            'created_at', 'updated_at',
        ]

    def get_supplier_display(self, obj):
        if obj.supplier:
            return getattr(obj.supplier, 'name', '')
        return obj.supplier_name or ''

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return ''

    def get_received_by_name(self, obj):
        if obj.received_by:
            return obj.received_by.get_full_name() or obj.received_by.email
        return ''

    def get_completed_by_name(self, obj):
        if obj.completed_by:
            return obj.completed_by.get_full_name() or obj.completed_by.email
        return ''

    def get_total_received_quantity(self, obj):
        from django.db.models import Sum
        result = obj.items.aggregate(total=Sum('received_quantity'))
        return result['total'] or 0

    def get_total_accepted_quantity(self, obj):
        from django.db.models import Sum
        result = obj.items.aggregate(total=Sum('accepted_quantity'))
        return result['total'] or 0

    def get_total_rejected_quantity(self, obj):
        from django.db.models import Sum
        result = obj.items.aggregate(total=Sum('rejected_quantity'))
        return result['total'] or 0

    def get_total_damage_quantity(self, obj):
        from django.db.models import Sum
        result = obj.items.aggregate(total=Sum('damage_quantity'))
        return result['total'] or 0


class CreateGRNSerializer(serializers.Serializer):
    """Serializer for creating a GRN."""
    grn_number = serializers.CharField(required=False, allow_blank=True)
    receipt_date = serializers.DateField(required=False)
    purchase_order = serializers.UUIDField()
    supplier = serializers.UUIDField(required=False, allow_null=True)
    location = serializers.UUIDField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(min_length=1)

    def validate_items(self, items):
        for item in items:
            if 'item_id' not in item and 'purchase_order_item' not in item:
                raise serializers.ValidationError(
                    "Each item must have 'item_id' or 'purchase_order_item'."
                )
            if 'received_quantity' not in item:
                raise serializers.ValidationError("Each item must have 'received_quantity'.")
            if float(item['received_quantity']) <= 0:
                raise serializers.ValidationError("Received quantity must be greater than 0.")
        return items

    def validate_purchase_order(self, po_id):
        from inventory.models import PurchaseOrder
        try:
            po = PurchaseOrder.objects.get(id=po_id)
        except PurchaseOrder.DoesNotExist:
            raise serializers.ValidationError("Purchase order not found.")
        if po.status not in ('SENT', 'PARTIALLY_RECEIVED'):
            raise serializers.ValidationError(
                f"Cannot create GRN for PO in status '{po.get_status_display()}'."
            )
        return po_id

    def validate_location(self, location_id):
        if not location_id:
            return location_id
        from inventory.models import InventoryLocation
        try:
            loc = InventoryLocation.objects.get(id=location_id)
        except InventoryLocation.DoesNotExist:
            raise serializers.ValidationError("Location not found.")
        if loc.status != 'ACTIVE':
            raise serializers.ValidationError("Location is not active.")
        return location_id


class UpdateGRNSerializer(serializers.Serializer):
    """Serializer for updating a DRAFT GRN."""
    receipt_date = serializers.DateField(required=False)
    location = serializers.UUIDField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(required=False)

    def validate_items(self, items):
        if not items:
            return items
        for item in items:
            if 'item_id' not in item and 'purchase_order_item' not in item:
                raise serializers.ValidationError(
                    "Each item must have 'item_id' or 'purchase_order_item'."
                )
            if 'received_quantity' not in item:
                raise serializers.ValidationError("Each item must have 'received_quantity'.")
            if float(item['received_quantity']) <= 0:
                raise serializers.ValidationError("Received quantity must be greater than 0.")
        return items


# ============================================================================
# SUPPLIER INVOICE SERIALIZERS (Section 12)
# ============================================================================

class SupplierInvoiceItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True, default='')
    item_name = serializers.CharField(source='item.item_name', read_only=True, default='')
    unit_name = serializers.SerializerMethodField()
    grn_number = serializers.SerializerMethodField()

    class Meta:
        model = InventorySupplierInvoiceItem
        fields = [
            'id', 'item', 'item_code', 'item_name', 'unit_name',
            'item_description',
            'goods_receipt_item', 'grn_number',
            'quantity', 'unit_price',
            'tax_rate', 'discount_rate', 'line_total',
            'remarks',
        ]
        read_only_fields = ['id', 'line_total']

    def get_unit_name(self, obj):
        if obj.item and obj.item.unit:
            return obj.item.unit.unit_name
        return ''

    def get_grn_number(self, obj):
        if obj.goods_receipt_item and obj.goods_receipt_item.goods_receipt:
            return obj.goods_receipt_item.goods_receipt.grn_number
        return ''


class SupplierInvoiceAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventorySupplierInvoiceAttachment
        fields = ['id', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class SupplierInvoiceHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventorySupplierInvoiceHistory
        fields = [
            'id', 'invoice', 'action',
            'from_status', 'to_status',
            'performed_by', 'performed_by_name',
            'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class SupplierInvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    supplier_display = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    po_number = serializers.SerializerMethodField()

    class Meta:
        model = InventorySupplierInvoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'due_date',
            'supplier', 'supplier_name', 'supplier_display',
            'supplier_invoice_number',
            'purchase_order', 'po_number',
            'status', 'payment_status',
            'subtotal', 'discount_amount', 'tax_amount',
            'shipping_charges', 'other_charges',
            'grand_total', 'outstanding_amount',
            'currency',
            'item_count', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_supplier_display(self, obj):
        if obj.supplier:
            return getattr(obj.supplier, 'name', '')
        return obj.supplier_name or ''

    def get_po_number(self, obj):
        if obj.purchase_order:
            return obj.purchase_order.order_number
        return ''


class SupplierInvoiceDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested items, attachments, and history."""
    items = SupplierInvoiceItemSerializer(many=True, read_only=True)
    attachments = SupplierInvoiceAttachmentSerializer(many=True, read_only=True)
    supplier_display = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    posted_by_name = serializers.SerializerMethodField()
    po_number = serializers.SerializerMethodField()
    grn_details = serializers.SerializerMethodField()
    total_payments = serializers.SerializerMethodField()

    class Meta:
        model = InventorySupplierInvoice
        fields = [
            'id', 'tenant_id', 'invoice_number', 'invoice_date', 'due_date',
            'supplier', 'supplier_name', 'supplier_display',
            'supplier_invoice_number',
            'currency', 'exchange_rate',
            'purchase_order', 'po_number',
            'goods_receipts',
            'status', 'payment_status',
            'subtotal', 'discount_amount', 'tax_amount',
            'shipping_charges', 'other_charges',
            'grand_total', 'outstanding_amount',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_notes',
            'posted_by', 'posted_by_name', 'posted_at',
            'remarks', 'terms',
            'items', 'attachments',
            'grn_details', 'total_payments',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'invoice_number', 'status', 'payment_status',
            'subtotal', 'grand_total', 'outstanding_amount',
            'approved_at', 'posted_at',
            'created_at', 'updated_at',
        ]

    def get_supplier_display(self, obj):
        if obj.supplier:
            return getattr(obj.supplier, 'name', '')
        return obj.supplier_name or ''

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return ''

    def get_posted_by_name(self, obj):
        if obj.posted_by:
            return obj.posted_by.get_full_name() or obj.posted_by.email
        return ''

    def get_po_number(self, obj):
        if obj.purchase_order:
            return obj.purchase_order.order_number
        return ''

    def get_grn_details(self, obj):
        grns = obj.goods_receipts.all()
        return [
            {
                'id': str(g.id),
                'grn_number': g.grn_number,
                'receipt_date': str(g.receipt_date),
            }
            for g in grns
        ]

    def get_total_payments(self, obj):
        from payments.models import Payment
        result = Payment.objects.filter(
            invoice=obj.invoice_number
        ).aggregate(total=Sum('amount'))
        return float(result['total'] or 0)


class CreateSupplierInvoiceSerializer(serializers.Serializer):
    """Serializer for creating a Supplier Invoice."""
    invoice_number = serializers.CharField(required=False, allow_blank=True)
    invoice_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_invoice_number = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(required=False, default='INR')
    exchange_rate = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, default=1.0
    )
    purchase_order = serializers.UUIDField(required=False, allow_null=True)
    goods_receipts = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    discount_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, default=0
    )
    tax_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, default=0
    )
    shipping_charges = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, default=0
    )
    other_charges = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, default=0
    )
    remarks = serializers.CharField(required=False, allow_blank=True)
    terms = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(min_length=1)

    def validate_items(self, items):
        for item in items:
            if 'item_id' not in item and 'item_description' not in item:
                raise serializers.ValidationError(
                    "Each item must have 'item_id' or 'item_description'."
                )
            if 'quantity' not in item:
                raise serializers.ValidationError("Each item must have 'quantity'.")
            if float(item['quantity']) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return items

    def validate_supplier(self, supplier_id):
        if not supplier_id:
            return supplier_id
        from contacts.models import Contact
        try:
            Contact.objects.get(id=supplier_id)
        except Contact.DoesNotExist:
            raise serializers.ValidationError("Supplier not found.")
        return supplier_id

    def validate_purchase_order(self, po_id):
        if not po_id:
            return po_id
        try:
            PurchaseOrder.objects.get(id=po_id)
        except PurchaseOrder.DoesNotExist:
            raise serializers.ValidationError("Purchase order not found.")
        return po_id


class UpdateSupplierInvoiceSerializer(serializers.Serializer):
    """Serializer for updating a DRAFT Supplier Invoice."""
    invoice_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_invoice_number = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(required=False)
    exchange_rate = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False
    )
    purchase_order = serializers.UUIDField(required=False, allow_null=True)
    goods_receipts = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    discount_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False
    )
    tax_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False
    )
    shipping_charges = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False
    )
    other_charges = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False
    )
    remarks = serializers.CharField(required=False, allow_blank=True)
    terms = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(required=False)

    def validate_items(self, items):
        if not items:
            return items
        for item in items:
            if 'item_id' not in item and 'item_description' not in item:
                raise serializers.ValidationError(
                    "Each item must have 'item_id' or 'item_description'."
                )
            if 'quantity' not in item:
                raise serializers.ValidationError("Each item must have 'quantity'.")
            if float(item['quantity']) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return items


class RecordPaymentSerializer(serializers.Serializer):
    """Serializer for recording a payment against an invoice."""
    amount = serializers.DecimalField(max_digits=20, decimal_places=4)
    payment_method = serializers.ChoiceField(
        choices=[
            ('UPI', 'UPI'),
            ('Bank Transfer', 'Bank Transfer'),
            ('Cash', 'Cash'),
            ('Card', 'Card'),
            ('Net Banking', 'Net Banking'),
            ('Cheque', 'Cheque'),
            ('Other', 'Other'),
        ],
        default='Bank Transfer',
    )
    payment_date = serializers.DateField(required=False, allow_null=True)
    reference = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate_amount(self, amount):
        if float(amount) <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return amount


# ============================================================================
# PURCHASE RETURN SERIALIZERS (Section 13)
# ============================================================================

class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)

    class Meta:
        model = InventoryPurchaseReturnItem
        fields = [
            'id', 'purchase_return', 'item', 'item_code', 'item_name',
            'goods_receipt_item',
            'received_quantity', 'return_quantity', 'damaged_quantity',
            'unit_cost', 'tax_rate', 'total_amount',
            'remarks',
        ]


class PurchaseReturnAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryPurchaseReturnAttachment
        fields = ['id', 'purchase_return', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class PurchaseReturnHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryPurchaseReturnHistory
        fields = [
            'id', 'purchase_return', 'action', 'from_status', 'to_status',
            'performed_by', 'performed_by_name', 'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class PurchaseReturnListSerializer(serializers.ModelSerializer):
    supplier_display = serializers.SerializerMethodField()

    class Meta:
        model = InventoryPurchaseReturn
        fields = [
            'id', 'return_number', 'return_date',
            'supplier', 'supplier_name', 'supplier_display',
            'return_reason', 'status',
            'subtotal', 'tax_amount', 'total_amount',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_supplier_display(self, obj):
        if obj.supplier_name:
            return obj.supplier_name
        if obj.supplier:
            return getattr(obj.supplier, 'name', str(obj.supplier))
        return ''


class PurchaseReturnDetailSerializer(serializers.ModelSerializer):
    items = PurchaseReturnItemSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()
    attachments = PurchaseReturnAttachmentSerializer(many=True, read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    processed_by_name = serializers.SerializerMethodField()
    completed_by_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    purchase_order_number = serializers.SerializerMethodField()
    goods_receipt_number = serializers.SerializerMethodField()
    supplier_invoice_number = serializers.SerializerMethodField()

    class Meta:
        model = InventoryPurchaseReturn
        fields = [
            'id', 'tenant_id', 'return_number', 'return_date',
            'supplier', 'supplier_name',
            'purchase_order', 'purchase_order_number',
            'goods_receipt', 'goods_receipt_number',
            'supplier_invoice', 'supplier_invoice_number',
            'return_reason', 'status',
            'subtotal', 'tax_amount', 'total_amount',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_notes',
            'processed_by', 'processed_by_name', 'processed_at',
            'completed_by', 'completed_by_name', 'completed_at',
            'remarks',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'created_at', 'updated_at',
            'items', 'history', 'attachments',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'status',
            'created_at', 'updated_at',
        ]

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return ''

    def get_processed_by_name(self, obj):
        if obj.processed_by:
            return obj.processed_by.get_full_name() or obj.processed_by.email
        return ''

    def get_completed_by_name(self, obj):
        if obj.completed_by:
            return obj.completed_by.get_full_name() or obj.completed_by.email
        return ''

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.email
        return ''

    def get_purchase_order_number(self, obj):
        if obj.purchase_order:
            return obj.purchase_order.order_number
        return ''

    def get_goods_receipt_number(self, obj):
        if obj.goods_receipt:
            return obj.goods_receipt.grn_number
        return ''

    def get_supplier_invoice_number(self, obj):
        if obj.supplier_invoice:
            return obj.supplier_invoice.invoice_number
        return ''

    def get_history(self, obj):
        from inventory.services.purchase_return_service import get_history
        qs = get_history(obj)
        return PurchaseReturnHistorySerializer(qs, many=True).data


class CreatePurchaseReturnSerializer(serializers.Serializer):
    return_number = serializers.CharField()
    return_date = serializers.DateField()
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True)
    purchase_order = serializers.UUIDField(required=False, allow_null=True)
    goods_receipt = serializers.UUIDField(required=False, allow_null=True)
    supplier_invoice = serializers.UUIDField(required=False, allow_null=True)
    return_reason = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField()

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("At least one item is required.")
        for item in items:
            if 'item' not in item:
                raise serializers.ValidationError("Each item must have 'item'.")
            if 'return_quantity' not in item:
                raise serializers.ValidationError("Each item must have 'return_quantity'.")
            if float(item['return_quantity']) <= 0:
                raise serializers.ValidationError("Return quantity must be greater than 0.")
        return items


class UpdatePurchaseReturnSerializer(serializers.Serializer):
    return_date = serializers.DateField(required=False)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True)
    purchase_order = serializers.UUIDField(required=False, allow_null=True)
    goods_receipt = serializers.UUIDField(required=False, allow_null=True)
    supplier_invoice = serializers.UUIDField(required=False, allow_null=True)
    return_reason = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(required=False)

    def validate_items(self, items):
        if not items:
            return items
        for item in items:
            if 'item' not in item:
                raise serializers.ValidationError("Each item must have 'item'.")
            if 'return_quantity' not in item:
                raise serializers.ValidationError("Each item must have 'return_quantity'.")
            if float(item['return_quantity']) <= 0:
                raise serializers.ValidationError("Return quantity must be greater than 0.")
        return items


# ============================================================================
# SUPPLIER PAYMENT SERIALIZERS (Section 14)
# ============================================================================

class SupplierPaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(
        source='supplier_invoice.invoice_number', read_only=True
    )
    invoice_total = serializers.DecimalField(
        source='supplier_invoice.grand_total', max_digits=20,
        decimal_places=4, read_only=True
    )
    invoice_outstanding = serializers.DecimalField(
        source='supplier_invoice.outstanding_amount', max_digits=20,
        decimal_places=4, read_only=True
    )

    class Meta:
        model = InventorySupplierPaymentAllocation
        fields = [
            'id', 'payment', 'supplier_invoice', 'invoice_number',
            'invoice_total', 'invoice_outstanding',
            'allocated_amount', 'remarks',
        ]


class SupplierPaymentAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventorySupplierPaymentAttachment
        fields = ['id', 'payment', 'file_url', 'file_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class SupplierPaymentHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventorySupplierPaymentHistory
        fields = [
            'id', 'payment', 'action', 'from_status', 'to_status',
            'performed_by', 'performed_by_name', 'remarks', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.email
        return ''


class SupplierPaymentListSerializer(serializers.ModelSerializer):
    supplier_display = serializers.SerializerMethodField()
    allocation_count = serializers.SerializerMethodField()

    class Meta:
        model = InventorySupplierPayment
        fields = [
            'id', 'payment_number', 'payment_date',
            'supplier', 'supplier_name', 'supplier_display',
            'payment_method', 'reference_number',
            'total_amount', 'allocated_amount', 'unallocated_amount',
            'status', 'allocation_count',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_supplier_display(self, obj):
        if obj.supplier_name:
            return obj.supplier_name
        if obj.supplier:
            return getattr(obj.supplier, 'name', str(obj.supplier))
        return ''

    def get_allocation_count(self, obj):
        return obj.allocations.count()


class SupplierPaymentDetailSerializer(serializers.ModelSerializer):
    allocations = SupplierPaymentAllocationSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()
    attachments = SupplierPaymentAttachmentSerializer(many=True, read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    posted_by_name = serializers.SerializerMethodField()
    completed_by_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventorySupplierPayment
        fields = [
            'id', 'tenant_id', 'payment_number', 'payment_date',
            'supplier', 'supplier_name',
            'payment_method', 'bank_account', 'reference_number',
            'currency', 'exchange_rate',
            'total_amount', 'allocated_amount', 'unallocated_amount',
            'status',
            'approved_by', 'approved_by_name', 'approved_at', 'approval_notes',
            'posted_by', 'posted_by_name', 'posted_at',
            'completed_by', 'completed_by_name', 'completed_at',
            'remarks',
            'created_by', 'created_by_name', 'updated_by', 'updated_by_name',
            'created_at', 'updated_at',
            'allocations', 'history', 'attachments',
        ]
        read_only_fields = [
            'id', 'tenant_id', 'status',
            'created_at', 'updated_at',
        ]

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.email
        return ''

    def get_posted_by_name(self, obj):
        if obj.posted_by:
            return obj.posted_by.get_full_name() or obj.posted_by.email
        return ''

    def get_completed_by_name(self, obj):
        if obj.completed_by:
            return obj.completed_by.get_full_name() or obj.completed_by.email
        return ''

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return ''

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.email
        return ''

    def get_history(self, obj):
        from inventory.services.supplier_payment_service import get_history
        qs = get_history(obj)
        return SupplierPaymentHistorySerializer(qs, many=True).data


class CreateSupplierPaymentSerializer(serializers.Serializer):
    payment_number = serializers.CharField(required=False, allow_blank=True)
    payment_date = serializers.DateField()
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=[
            ('UPI', 'UPI'), ('Bank Transfer', 'Bank Transfer'),
            ('Cash', 'Cash'), ('Card', 'Card'),
            ('Cheque', 'Cheque'), ('Net Banking', 'Net Banking'),
            ('DD', 'Demand Draft'), ('Other', 'Other'),
        ],
        default='Bank Transfer',
    )
    bank_account = serializers.CharField(required=False, allow_blank=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(required=False, default='INR')
    exchange_rate = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, default=1
    )
    total_amount = serializers.DecimalField(max_digits=20, decimal_places=4)
    remarks = serializers.CharField(required=False, allow_blank=True)
    allocations = serializers.ListField(required=False, default=[])

    def validate_total_amount(self, amount):
        if float(amount) <= 0:
            raise serializers.ValidationError("Total amount must be greater than 0.")
        return amount

    def validate_allocations(self, allocations):
        for alloc in allocations:
            if 'supplier_invoice' not in alloc:
                raise serializers.ValidationError("Each allocation must have 'supplier_invoice'.")
            if 'allocated_amount' not in alloc:
                raise serializers.ValidationError("Each allocation must have 'allocated_amount'.")
            if float(alloc['allocated_amount']) <= 0:
                raise serializers.ValidationError("Allocated amount must be greater than 0.")
        return allocations


class UpdateSupplierPaymentSerializer(serializers.Serializer):
    payment_date = serializers.DateField(required=False)
    supplier = serializers.UUIDField(required=False, allow_null=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=[
            ('UPI', 'UPI'), ('Bank Transfer', 'Bank Transfer'),
            ('Cash', 'Cash'), ('Card', 'Card'),
            ('Cheque', 'Cheque'), ('Net Banking', 'Net Banking'),
            ('DD', 'Demand Draft'), ('Other', 'Other'),
        ],
        required=False,
    )
    bank_account = serializers.CharField(required=False, allow_blank=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(required=False)
    exchange_rate = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False
    )
    total_amount = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False
    )
    remarks = serializers.CharField(required=False, allow_blank=True)
    allocations = serializers.ListField(required=False)

    def validate_total_amount(self, amount):
        if float(amount) <= 0:
            raise serializers.ValidationError("Total amount must be greater than 0.")
        return amount


class StockSummarySerializer(serializers.ModelSerializer):
    """Serializer for StockSummary report."""
    item_code = serializers.CharField(source='item.item_code', read_only=True)
    item_name = serializers.CharField(source='item.item_name', read_only=True)
    category_name = serializers.CharField(
        source='item.category.category_name', read_only=True, default=''
    )
    unit_name = serializers.CharField(
        source='item.unit.unit_name', read_only=True, default=''
    )
    location_name = serializers.CharField(
        source='location.location_name', read_only=True, default=''
    )
    available_quantity = serializers.DecimalField(
        max_digits=20, decimal_places=4, read_only=True
    )

    class Meta:
        model = StockSummary
        fields = [
            'id', 'item', 'item_code', 'item_name',
            'category_name', 'unit_name',
            'location', 'location_name',
            'physical_quantity', 'reserved_quantity',
            'in_transit_quantity', 'damaged_quantity',
            'available_quantity',
        ]
        read_only_fields = fields


class AllocatePaymentSerializer(serializers.Serializer):
    allocations = serializers.ListField()

    def validate_allocations(self, allocations):
        if not allocations:
            raise serializers.ValidationError("At least one allocation is required.")
        for alloc in allocations:
            if 'supplier_invoice' not in alloc:
                raise serializers.ValidationError("Each allocation must have 'supplier_invoice'.")
            if 'allocated_amount' not in alloc:
                raise serializers.ValidationError("Each allocation must have 'allocated_amount'.")
            if float(alloc['allocated_amount']) <= 0:
                raise serializers.ValidationError("Allocated amount must be greater than 0.")
        return allocations
