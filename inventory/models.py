import uuid
from django.db import models
from django.core.exceptions import ValidationError
from core.models import Main, GlobalDefaultManager


class StatusTransitionMixin:
    """
    Mixin that validates status transitions in clean().
    Subclasses must define VALID_TRANSITIONS as a dict:
        'CURRENT_STATUS': {'NEXT_STATUS1', 'NEXT_STATUS2', ...}
    """

    _original_status = None

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_status = dict(zip(field_names, values)).get('status')
        return instance

    def clean(self):
        original = getattr(self, '_original_status', None)
        if original is not None and self.pk and original != self.status:
            allowed = self.VALID_TRANSITIONS.get(original, set())
            if self.status not in allowed:
                raise ValidationError(
                    f"Invalid status transition from '{original}' to '{self.status}'. "
                    f"Allowed transitions from '{original}': {', '.join(sorted(allowed)) or 'none'}."
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        self._original_status = self.status


class ItemCategory(Main):
    """Hierarchical item categories — e.g. Electronics → Laptops"""

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ARCHIVED', 'Archived'),
    )

    # Tenant isolation
    tenant_id = models.UUIDField(db_index=True, default=uuid.uuid4)

    category_code = models.CharField(max_length=100, db_index=True, default='')
    category_name = models.CharField(max_length=255, default='')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )

    # Tracking & audit
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_categories'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_categories'
    )

    class Meta:
        ordering = ['category_name']
        verbose_name = 'Item Category'
        verbose_name_plural = 'Item Categories'
        unique_together = ('tenant_id', 'category_code')
        indexes = [
            models.Index(fields=['tenant_id', 'category_code']),
            models.Index(fields=['tenant_id', 'category_name']),
            models.Index(fields=['tenant_id', 'parent']),
            models.Index(fields=['tenant_id', 'status']),
        ]

    def __str__(self):
        return f"{self.category_code} — {self.category_name}"


class Unit(Main):
    """Units of measurement — e.g. Piece, Kg, Meter, Liter, Box"""

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ARCHIVED', 'Archived'),
    )

    # Tenant isolation
    tenant_id = models.UUIDField(db_index=True, default=uuid.uuid4)

    unit_code = models.CharField(max_length=100, db_index=True, default='')
    unit_name = models.CharField(max_length=255, default='')
    symbol = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )

    class Meta:
        ordering = ['unit_name']
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'
        unique_together = ('tenant_id', 'unit_code')
        indexes = [
            models.Index(fields=['tenant_id', 'unit_code']),
            models.Index(fields=['tenant_id', 'unit_name']),
            models.Index(fields=['tenant_id', 'status']),
        ]

    def __str__(self):
        return f"{self.unit_code} — {self.unit_name}"


class UnitConversion(Main):
    """Conversion relationships between units — e.g. 1 Box = 12 Pieces"""

    # Tenant isolation
    tenant_id = models.UUIDField(db_index=True)

    from_unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, related_name='conversions_from'
    )
    to_unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, related_name='conversions_to'
    )
    conversion_factor = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        ordering = ['from_unit', 'to_unit']
        verbose_name = 'Unit Conversion'
        verbose_name_plural = 'Unit Conversions'
        unique_together = ('tenant_id', 'from_unit', 'to_unit')
        indexes = [
            models.Index(fields=['tenant_id', 'from_unit']),
            models.Index(fields=['tenant_id', 'to_unit']),
        ]

    def __str__(self):
        return f"1 {self.from_unit.unit_name} = {self.conversion_factor} {self.to_unit.unit_name}"


class Brand(Main):
    """Brand or manufacturer of items — e.g. Apple, Samsung, Dell"""

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ARCHIVED', 'Archived'),
    )

    # Tenant isolation
    tenant_id = models.UUIDField(db_index=True, default=uuid.uuid4)

    brand_code = models.CharField(max_length=100, db_index=True, default='')
    brand_name = models.CharField(max_length=255, default='')
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True, max_length=2000)
    website = models.URLField(blank=True, max_length=2000)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )

    # Tracking & audit
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_brands'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_brands'
    )

    class Meta:
        ordering = ['brand_name']
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        unique_together = ('tenant_id', 'brand_code')
        indexes = [
            models.Index(fields=['tenant_id', 'brand_code']),
            models.Index(fields=['tenant_id', 'brand_name']),
            models.Index(fields=['tenant_id', 'status']),
        ]

    def __str__(self):
        return f"{self.brand_code} — {self.brand_name}"


class InventoryItem(Main):
    """Central item master — every stockable/service item lives here."""

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ARCHIVED', 'Archived'),
    )

    # Tenant isolation
    tenant_id = models.UUIDField(db_index=True)

    item_code = models.CharField(max_length=100, db_index=True)
    item_name = models.CharField(max_length=500)
    category = models.ForeignKey(
        ItemCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items'
    )
    sub_category = models.CharField(max_length=255, blank=True)
    unit = models.ForeignKey(
        Unit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items'
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items'
    )
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True, max_length=2000)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )
    custom_fields = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Tracking & audit
    imported_from = models.CharField(max_length=255, blank=True,
                                       help_text="Source of import (e.g. Excel file name)")
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_inventory_items'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_inventory_items'
    )

    # Cloned-from reference
    cloned_from = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='clones'
    )

    # Stock management fields
    min_stock_level = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Minimum stock before low-stock alert'
    )
    reorder_level = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Stock level at which to reorder'
    )
    max_stock_level = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Maximum desired stock level'
    )
    cost_price = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Unit cost price for valuation'
    )
    selling_price = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Unit selling price'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inventory Item'
        verbose_name_plural = 'Inventory Items'
        unique_together = ('tenant_id', 'item_code')
        indexes = [
            models.Index(fields=['tenant_id', 'item_code']),
            models.Index(fields=['tenant_id', 'item_name']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'category']),
            models.Index(fields=['tenant_id', 'brand']),
        ]

    def __str__(self):
        return f"{self.item_code} — {self.item_name}"


class CustomFieldDefinition(Main):
    """Dynamic custom field schema per organization/tenant.

    Travel Client may need Destination, Hotel Name, Tour Duration.
    Retail Client may need Color, Size, Warranty.
    No code changes required — admins configure these via the UI.
    """
    FIELD_TYPE_CHOICES = (
        ('TEXT', 'Text'),
        ('NUMBER', 'Number'),
        ('DATE', 'Date'),
        ('BOOLEAN', 'Boolean'),
        ('SELECT', 'Select'),
        ('MULTI_SELECT', 'Multi Select'),
    )

    field_name = models.CharField(max_length=255)
    field_label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='TEXT')
    options = models.JSONField(default=list, blank=True,
                                help_text="For SELECT/MULTI_SELECT types")
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'field_name']
        verbose_name = 'Custom Field Definition'
        verbose_name_plural = 'Custom Field Definitions'

    def __str__(self):
        return f"{self.field_label} ({self.get_field_type_display()})"


class InventoryLocationType(Main):
    """Configurable location types — Warehouse, Branch, Store, Office, Depot, etc.
    Clients can create custom types without code changes.
    """

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    )

    tenant_id = models.UUIDField(db_index=True)
    type_code = models.CharField(max_length=50, db_index=True)
    type_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )

    class Meta:
        ordering = ['type_name']
        verbose_name = 'Location Type'
        verbose_name_plural = 'Location Types'
        unique_together = ('tenant_id', 'type_code')
        indexes = [
            models.Index(fields=['tenant_id', 'type_code']),
            models.Index(fields=['tenant_id', 'type_name']),
            models.Index(fields=['tenant_id', 'status']),
        ]

    def __str__(self):
        return f"{self.type_code} — {self.type_name}"


class InventoryLocation(Main):
    """Locations define where inventory exists — warehouse, branch, store, office, etc.
    Supports hierarchy: India HQ → Bangalore Branch → Section A.
    Stock quantities are NOT stored here — use Stock Ledger (Section 4).
    """

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ARCHIVED', 'Archived'),
    )

    # Tenant isolation
    tenant_id = models.UUIDField(db_index=True)

    # Core identification
    location_code = models.CharField(max_length=100, db_index=True)
    location_name = models.CharField(max_length=500)
    location_type = models.ForeignKey(
        InventoryLocationType, on_delete=models.PROTECT,
        related_name='locations'
    )
    parent_location = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='child_locations'
    )

    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Contact
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    mobile = models.CharField(max_length=50, blank=True)

    # Manager assignment
    manager = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='managed_locations'
    )

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )

    # Capacity (optional)
    max_capacity = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Maximum storage capacity'
    )
    capacity_unit = models.CharField(
        max_length=50, blank=True,
        help_text='e.g. PCS, KG, Seats'
    )

    # Location settings (configurable toggles)
    allow_reservations = models.BooleanField(default=True)
    allow_transfers = models.BooleanField(default=True)
    allow_sales = models.BooleanField(default=True)
    allow_purchases = models.BooleanField(default=True)
    allow_audits = models.BooleanField(default=True)

    # Tracking & audit
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_locations'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_locations'
    )

    class Meta:
        ordering = ['location_name']
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'
        unique_together = ('tenant_id', 'location_code')
        indexes = [
            models.Index(fields=['tenant_id', 'location_code']),
            models.Index(fields=['tenant_id', 'location_name']),
            models.Index(fields=['tenant_id', 'location_type']),
            models.Index(fields=['tenant_id', 'parent_location']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'city']),
        ]

    def __str__(self):
        return f"{self.location_code} — {self.location_name}"


class InventoryTransfer(StatusTransitionMixin, Main):
    """Stock transfer between locations with full workflow."""

    VALID_TRANSITIONS = {
        'DRAFT': {'PENDING_APPROVAL', 'CANCELLED'},
        'PENDING_APPROVAL': {'APPROVED', 'REJECTED', 'CANCELLED'},
        'APPROVED': {'IN_TRANSIT'},
        'IN_TRANSIT': {'RECEIVED', 'PARTIALLY_RECEIVED'},
        'RECEIVED': {'COMPLETED'},
        'PARTIALLY_RECEIVED': {'RECEIVED', 'COMPLETED'},
        'REJECTED': set(),
        'COMPLETED': set(),
        'CANCELLED': set(),
    }

    TRANSFER_TYPES = (
        ('STANDARD', 'Standard Transfer'),
        ('EMERGENCY', 'Emergency Transfer'),
        ('RETURN', 'Return Transfer'),
        ('DAMAGED', 'Damaged Stock Transfer'),
    )

    TRANSFER_STATUSES = (
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('IN_TRANSIT', 'In Transit'),
        ('RECEIVED', 'Received'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    tenant_id = models.UUIDField(db_index=True)
    transfer_number = models.CharField(max_length=100, db_index=True)
    transfer_date = models.DateField()

    source_location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT,
        related_name='transfers_from'
    )
    destination_location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT,
        related_name='transfers_to'
    )

    transfer_type = models.CharField(
        max_length=30, choices=TRANSFER_TYPES, default='STANDARD'
    )
    status = models.CharField(
        max_length=30, choices=TRANSFER_STATUSES, default='DRAFT'
    )

    # Approval
    approved_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_transfers'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    # Dispatch / Receipt
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='received_transfers'
    )

    remarks = models.TextField(blank=True)

    # Tracking
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_transfers'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_transfers'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Transfer'
        verbose_name_plural = 'Stock Transfers'
        unique_together = ('tenant_id', 'transfer_number')
        indexes = [
            models.Index(fields=['tenant_id', 'transfer_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'source_location']),
            models.Index(fields=['tenant_id', 'destination_location']),
            models.Index(fields=['tenant_id', 'transfer_date']),
        ]

    def __str__(self):
        return f"{self.transfer_number} ({self.get_status_display()})"


class InventoryTransferItem(Main):
    """Line items for a stock transfer."""

    transfer = models.ForeignKey(
        InventoryTransfer, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='transfer_items'
    )
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    received_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True
    )
    damaged_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True
    )
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Transfer Line Item'
        verbose_name_plural = 'Transfer Line Items'

    def __str__(self):
        return f"{self.item.item_code} x {self.quantity}"


class InventoryTransferAttachment(Main):
    """Files attached to a transfer (delivery notes, receipts, etc.)."""

    transfer = models.ForeignKey(
        InventoryTransfer, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Transfer Attachment'
        verbose_name_plural = 'Transfer Attachments'

    def __str__(self):
        return self.file_name


class InventoryTransferHistory(Main):
    """Audit trail for stock transfers — logs every status change."""

    ACTIONS = (
        ('CREATED', 'Transfer Created'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('DISPATCHED', 'Dispatched'),
        ('RECEIVED', 'Received'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('UPDATED', 'Updated'),
    )

    transfer = models.ForeignKey(
        InventoryTransfer, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventoryTransfer.TRANSFER_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventoryTransfer.TRANSFER_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transfer_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Transfer History Entry'
        verbose_name_plural = 'Transfer History Entries'
        indexes = [
            models.Index(fields=['transfer', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.transfer.transfer_number}: {self.action} ({self.timestamp})"


# ============================================================================
# INVENTORY ADJUSTMENT (Section 7)
# ============================================================================

class InventoryAdjustmentReason(Main):
    """Configurable adjustment reasons — Damage, Loss, Theft, Expired, etc."""

    ADJUSTMENT_TYPES = (
        ('INCREASE', 'Stock Increase'),
        ('DECREASE', 'Stock Decrease'),
    )

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    )

    # Use GlobalDefaultManager to support tenant-specific + global default lookups
    objects = GlobalDefaultManager()

    tenant_id = models.UUIDField(db_index=True)
    reason_code = models.CharField(max_length=100, db_index=True)
    reason_name = models.CharField(max_length=255)
    adjustment_type = models.CharField(
        max_length=20, choices=ADJUSTMENT_TYPES
    )
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Pre-seeded system reason'
    )

    class Meta:
        ordering = ['reason_name']
        verbose_name = 'Adjustment Reason'
        verbose_name_plural = 'Adjustment Reasons'
        unique_together = ('tenant_id', 'reason_code')
        indexes = [
            models.Index(fields=['tenant_id', 'reason_code']),
            models.Index(fields=['tenant_id', 'adjustment_type']),
            models.Index(fields=['tenant_id', 'status']),
        ]

    def __str__(self):
        return f"{self.reason_code} — {self.reason_name}"


class InventoryAdjustment(StatusTransitionMixin, Main):
    """Stock adjustment — increases or decreases stock with full audit trail.
    Never updates stock directly. Always uses Stock Ledger.
    """

    VALID_TRANSITIONS = {
        'DRAFT': {'PENDING_APPROVAL', 'CANCELLED'},
        'PENDING_APPROVAL': {'APPROVED', 'REJECTED', 'CANCELLED'},
        'APPROVED': {'APPLIED'},
        'APPLIED': set(),
        'REJECTED': set(),
        'CANCELLED': set(),
    }

    ADJUSTMENT_STATUSES = (
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('APPLIED', 'Applied'),
        ('CANCELLED', 'Cancelled'),
    )

    tenant_id = models.UUIDField(db_index=True)
    adjustment_number = models.CharField(max_length=100, db_index=True)
    adjustment_date = models.DateField()

    location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT,
        related_name='adjustments'
    )
    adjustment_type = models.CharField(
        max_length=20, choices=InventoryAdjustmentReason.ADJUSTMENT_TYPES
    )
    reason = models.ForeignKey(
        InventoryAdjustmentReason, on_delete=models.PROTECT,
        related_name='adjustments'
    )

    status = models.CharField(
        max_length=30, choices=ADJUSTMENT_STATUSES, default='DRAFT'
    )

    # Approval
    approved_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_adjustments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    # Application
    applied_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='applied_adjustments'
    )
    applied_at = models.DateTimeField(null=True, blank=True)

    remarks = models.TextField(blank=True)

    # Tracking
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_adjustments'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_adjustments'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Adjustment'
        verbose_name_plural = 'Stock Adjustments'
        unique_together = ('tenant_id', 'adjustment_number')
        indexes = [
            models.Index(fields=['tenant_id', 'adjustment_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'location']),
            models.Index(fields=['tenant_id', 'adjustment_type']),
            models.Index(fields=['tenant_id', 'adjustment_date']),
        ]

    def __str__(self):
        return f"{self.adjustment_number} ({self.get_status_display()})"


class InventoryAdjustmentItem(Main):
    """Line items for a stock adjustment."""

    adjustment = models.ForeignKey(
        InventoryAdjustment, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='adjustment_items'
    )
    available_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
        help_text='Current available stock at time of adjustment'
    )
    adjustment_quantity = models.DecimalField(
        max_digits=20, decimal_places=4,
        help_text='Positive = increase, Negative = decrease'
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='adjustment_items'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Adjustment Line Item'
        verbose_name_plural = 'Adjustment Line Items'

    def __str__(self):
        return f"{self.item.item_code} x {self.adjustment_quantity}"


class InventoryAdjustmentHistory(Main):
    """Audit trail for stock adjustments — logs every status change."""

    ACTIONS = (
        ('CREATED', 'Adjustment Created'),
        ('UPDATED', 'Adjustment Updated'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('APPLIED', 'Applied'),
        ('CANCELLED', 'Cancelled'),
    )

    adjustment = models.ForeignKey(
        InventoryAdjustment, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventoryAdjustment.ADJUSTMENT_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventoryAdjustment.ADJUSTMENT_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='adjustment_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Adjustment History Entry'
        verbose_name_plural = 'Adjustment History Entries'
        indexes = [
            models.Index(fields=['adjustment', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.adjustment.adjustment_number}: {self.action} ({self.timestamp})"


class InventoryAdjustmentAttachment(Main):
    """Files attached to an adjustment (damage photos, documents, etc.)."""

    adjustment = models.ForeignKey(
        InventoryAdjustment, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Adjustment Attachment'
        verbose_name_plural = 'Adjustment Attachments'

    def __str__(self):
        return self.file_name


# ============================================================================
# STOCK RESERVATION (Section 8)
# ============================================================================

class InventoryReservationReason(Main):
    """Configurable reservation reasons — Customer Order, Internal Job, Transfer, etc."""

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    )

    objects = GlobalDefaultManager()

    tenant_id = models.UUIDField(db_index=True)
    reason_code = models.CharField(max_length=100, db_index=True)
    reason_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Pre-seeded system reason'
    )

    class Meta:
        ordering = ['reason_name']
        verbose_name = 'Reservation Reason'
        verbose_name_plural = 'Reservation Reasons'
        unique_together = ('tenant_id', 'reason_code')
        indexes = [
            models.Index(fields=['tenant_id', 'reason_code']),
            models.Index(fields=['tenant_id', 'status']),
        ]

    def __str__(self):
        return f"{self.reason_code} — {self.reason_name}"


class InventoryReservation(StatusTransitionMixin, Main):
    """Stock reservation — reserves stock for future use without affecting physical stock.

    When Active:
        - Reserved Stock increases
        - Available Stock decreases
        - Physical Stock remains unchanged

    When Cancelled / Expired:
        - Reserved Stock decreases
        - Available Stock restores

    When Fulfilled:
        - Reserved Stock decreases
        - Physical stock must be moved via existing inventory transaction logic
    """

    VALID_TRANSITIONS = {
        'DRAFT': {'ACTIVE', 'CANCELLED'},
        'ACTIVE': {'PARTIALLY_FULFILLED', 'FULFILLED', 'CANCELLED', 'EXPIRED'},
        'PARTIALLY_FULFILLED': {'FULFILLED', 'CANCELLED'},
        'FULFILLED': set(),
        'CANCELLED': set(),
        'EXPIRED': set(),
    }

    RESERVATION_TYPES = (
        ('SALES_ORDER', 'Sales Order'),
        ('TRANSFER', 'Transfer'),
        ('PRODUCTION', 'Production'),
        ('INTERNAL', 'Internal Use'),
        ('CUSTOMER', 'Customer Reservation'),
        ('OTHER', 'Other'),
    )

    RESERVATION_STATUSES = (
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('PARTIALLY_FULFILLED', 'Partially Fulfilled'),
        ('FULFILLED', 'Fulfilled'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    )

    PRIORITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )

    tenant_id = models.UUIDField(db_index=True)
    reservation_number = models.CharField(max_length=100, db_index=True)
    reservation_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)

    source_location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT,
        related_name='reservations'
    )

    reservation_type = models.CharField(
        max_length=30, choices=RESERVATION_TYPES, default='OTHER'
    )
    status = models.CharField(
        max_length=30, choices=RESERVATION_STATUSES, default='DRAFT'
    )

    # Customer / Reference
    customer_name = models.CharField(max_length=500, blank=True)
    reference_number = models.CharField(max_length=200, blank=True)

    # Priority
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM'
    )

    # Reason
    reason = models.ForeignKey(
        InventoryReservationReason, on_delete=models.PROTECT,
        null=True, blank=True, related_name='reservations'
    )

    remarks = models.TextField(blank=True)

    # Tracking
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_reservations'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_reservations'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Reservation'
        verbose_name_plural = 'Stock Reservations'
        unique_together = ('tenant_id', 'reservation_number')
        indexes = [
            models.Index(fields=['tenant_id', 'reservation_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'source_location']),
            models.Index(fields=['tenant_id', 'reservation_date']),
            models.Index(fields=['tenant_id', 'expiry_date']),
            models.Index(fields=['tenant_id', 'reservation_type']),
        ]

    def __str__(self):
        return f"{self.reservation_number} ({self.get_status_display()})"


class InventoryReservationItem(Main):
    """Line items for a stock reservation."""

    reservation = models.ForeignKey(
        InventoryReservation, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='reservation_items'
    )
    requested_quantity = models.DecimalField(max_digits=20, decimal_places=4)
    reserved_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    fulfilled_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reservation_items'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Reservation Line Item'
        verbose_name_plural = 'Reservation Line Items'

    @property
    def remaining_quantity(self):
        """Remaining = Requested - Fulfilled"""
        return self.requested_quantity - self.fulfilled_quantity

    def __str__(self):
        return f"{self.item.item_code} x {self.requested_quantity}"


class InventoryReservationHistory(Main):
    """Audit trail for stock reservations — logs every status change."""

    ACTIONS = (
        ('CREATED', 'Reservation Created'),
        ('UPDATED', 'Reservation Updated'),
        ('ACTIVATED', 'Reservation Activated'),
        ('FULFILLED', 'Reservation Fulfilled'),
        ('PARTIALLY_FULFILLED', 'Partially Fulfilled'),
        ('CANCELLED', 'Reservation Cancelled'),
        ('EXPIRED', 'Reservation Expired'),
    )

    reservation = models.ForeignKey(
        InventoryReservation, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventoryReservation.RESERVATION_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventoryReservation.RESERVATION_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reservation_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Reservation History Entry'
        verbose_name_plural = 'Reservation History Entries'
        indexes = [
            models.Index(fields=['reservation', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.reservation.reservation_number}: {self.action} ({self.timestamp})"


class InventoryReservationAttachment(Main):
    """Files attached to a reservation (customer requests, approval letters, etc.)."""

    reservation = models.ForeignKey(
        InventoryReservation, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Reservation Attachment'
        verbose_name_plural = 'Reservation Attachments'

    def __str__(self):
        return self.file_name


class StockLedger(Main):
    """Stock Ledger — the single source of truth for all inventory quantities.

    NEVER store quantities directly. Every stock movement creates a ledger entry.
    Current stock is calculated by summing all ledger entries for an item+location.
    """

    TRANSACTION_TYPES = (
        ('OPENING', 'Opening Balance'),
        ('PURCHASE', 'Purchase'),
        ('PURCHASE_IN', 'Purchase In'),
        ('GOODS_RECEIPT', 'Goods Receipt'),
        ('PURCHASE_RETURN', 'Purchase Return'),
        ('SALE', 'Sale'),
        ('TRANSFER_IN', 'Transfer In'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('RETURN', 'Return'),
        ('DAMAGE', 'Damage'),
        ('LOST', 'Lost'),
        ('EXPIRED', 'Expired'),
        ('CONSUMPTION', 'Consumption'),
        ('ADJUSTMENT', 'Adjustment'),
        ('ADJUSTMENT_IN', 'Adjustment In'),
        ('ADJUSTMENT_OUT', 'Adjustment Out'),
        ('RESERVATION', 'Reservation'),
        ('RESERVATION_RELEASE', 'Reservation Release'),
    )

    tenant_id = models.UUIDField(db_index=True)

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='stock_ledger_entries'
    )
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.CASCADE,
        related_name='stock_ledger_entries',
        null=True, blank=True
    )

    transaction_type = models.CharField(
        max_length=30, choices=TRANSACTION_TYPES
    )
    quantity = models.DecimalField(
        max_digits=20, decimal_places=4,
        help_text='Positive = in, Negative = out'
    )

    # Unit cost/total cost for valuation
    unit_cost = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True
    )
    total_cost = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True
    )

    # Polymorphic reference to source document
    reference_type = models.CharField(
        max_length=50, blank=True,
        help_text='e.g. PURCHASE_ORDER, SALES_ORDER, TRANSFER'
    )
    reference_id = models.CharField(
        max_length=100, blank=True,
        help_text='ID of the source document'
    )

    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_ledger_entries'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Ledger Entry'
        verbose_name_plural = 'Stock Ledger Entries'
        indexes = [
            models.Index(fields=['tenant_id', 'item', 'location']),
            models.Index(fields=['tenant_id', 'item']),
            models.Index(fields=['tenant_id', 'location']),
            models.Index(fields=['tenant_id', 'transaction_type']),
            models.Index(fields=['tenant_id', 'created_at']),
        ]

    def __str__(self):
        return f"{self.item.item_code} @ {self.location} = {self.quantity} ({self.transaction_type})"


class StockSummary(Main):
    """Cached stock summary for fast lookups.
    Updated automatically when ledger entries are created.
    Never update this directly — always use the ledger.
    """

    tenant_id = models.UUIDField(db_index=True)

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='stock_summaries'
    )
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.CASCADE,
        related_name='stock_summaries',
        null=True, blank=True
    )

    physical_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    reserved_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    in_transit_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    damaged_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )

    class Meta:
        verbose_name = 'Stock Summary'
        verbose_name_plural = 'Stock Summaries'
        unique_together = ('tenant_id', 'item', 'location')
        indexes = [
            models.Index(fields=['tenant_id', 'item']),
            models.Index(fields=['tenant_id', 'location']),
            models.Index(fields=['tenant_id', 'physical_quantity']),
        ]

    def __str__(self):
        return f"{self.item.item_code} @ {self.location}: {self.physical_quantity}"

    @property
    def available_quantity(self):
        """Available = Physical - Reserved"""
        return self.physical_quantity - self.reserved_quantity


# ============================================================================
# PHYSICAL STOCK COUNT — SECTION 9
# ============================================================================

class StockCountReason(Main):
    """
    Configurable master reasons for stock counts.
    e.g. Monthly Cycle Count, Yearly Audit, Random Spot Check, New Location Setup
    """

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    )

    objects = GlobalDefaultManager()

    tenant_id = models.UUIDField(db_index=True)
    reason_code = models.CharField(max_length=100, db_index=True)
    reason_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ACTIVE'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Pre-seeded system reason'
    )

    class Meta:
        ordering = ['reason_name']
        verbose_name = 'Stock Count Reason'
        verbose_name_plural = 'Stock Count Reasons'
        unique_together = ('tenant_id', 'reason_code')
        indexes = [
            models.Index(fields=['tenant_id', 'reason_code']),
            models.Index(fields=['tenant_id', 'status']),
        ]

    def __str__(self):
        return f"{self.reason_code} — {self.reason_name}"


class InventoryStockCount(StatusTransitionMixin, Main):
    """
    Physical Stock Count (Cycle Count) — the authoritative count of physical inventory.

    Workflow:
      DRAFT → ASSIGNED → IN_PROGRESS → SUBMITTED → APPROVED → COMPLETED
                                                          → CANCELLED
    """

    VALID_TRANSITIONS = {
        'DRAFT': {'ASSIGNED', 'CANCELLED'},
        'ASSIGNED': {'IN_PROGRESS', 'CANCELLED'},
        'IN_PROGRESS': {'SUBMITTED', 'CANCELLED'},
        'SUBMITTED': {'APPROVED'},
        'APPROVED': {'COMPLETED'},
        'COMPLETED': set(),
        'CANCELLED': set(),
    }

    COUNT_TYPES = (
        ('FULL', 'Full Count'),
        ('CYCLE', 'Cycle Count'),
        ('SPOT', 'Spot Check'),
        ('ANNUAL', 'Annual Physical Count'),
    )

    COUNT_STATUSES = (
        ('DRAFT', 'Draft'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    tenant_id = models.UUIDField(db_index=True)
    count_number = models.CharField(max_length=100, db_index=True)
    count_date = models.DateField()
    count_type = models.CharField(
        max_length=20, choices=COUNT_TYPES, default='CYCLE'
    )
    status = models.CharField(
        max_length=30, choices=COUNT_STATUSES, default='DRAFT'
    )

    # Scope: location and optional category filter
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT,
        related_name='stock_counts'
    )
    category = models.ForeignKey(
        ItemCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_counts',
        help_text='Optional — if set, only items in this category are counted'
    )

    # Reason
    reason = models.ForeignKey(
        StockCountReason, on_delete=models.PROTECT,
        related_name='stock_counts'
    )

    # Counters assigned to perform the count
    assigned_counters = models.ManyToManyField(
        'authentication.User',
        blank=True,
        related_name='assigned_stock_counts',
        help_text='Users assigned to perform the physical count'
    )

    # Approval
    approved_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_stock_counts'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    # Completion
    completed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='completed_stock_counts'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # Difference summary (populated when adjustment is generated)
    total_items_counted = models.PositiveIntegerField(default=0)
    total_items_with_difference = models.PositiveIntegerField(default=0)
    total_difference_value = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )

    # Generated adjustment reference (populated on COMPLETED)
    generated_adjustment = models.ForeignKey(
        'InventoryAdjustment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='source_stock_counts',
        help_text='Adjustment auto-generated from count differences'
    )

    remarks = models.TextField(blank=True)

    # Tracking
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_stock_counts'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_stock_counts'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Physical Stock Count'
        verbose_name_plural = 'Physical Stock Counts'
        unique_together = ('tenant_id', 'count_number')
        indexes = [
            models.Index(fields=['tenant_id', 'count_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'location']),
            models.Index(fields=['tenant_id', 'count_date']),
            models.Index(fields=['tenant_id', 'count_type']),
        ]

    def __str__(self):
        return f"{self.count_number} ({self.get_status_display()})"


class InventoryStockCountItem(Main):
    """Line items for a stock count — each item counted physically."""

    count = models.ForeignKey(
        InventoryStockCount, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='stock_count_items'
    )

    # System/source quantities
    expected_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='System quantity at time count was created (from Stock Ledger)'
    )
    reserved_quantity_at_count = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Reserved stock at time count was created'
    )

    # Physical count entry
    counted_quantity = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        help_text='Actual physical quantity counted (null = not yet counted)'
    )
    counted_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='counted_items'
    )
    counted_at = models.DateTimeField(null=True, blank=True)

    # Barcode scan support
    scanned_barcode = models.CharField(
        max_length=255, blank=True,
        help_text='Barcode scanned during counting (if applicable)'
    )

    # Difference (computed)
    difference_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Difference = counted - expected. Positive = surplus, Negative = shortage'
    )

    unit = models.ForeignKey(
        Unit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_count_items'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Stock Count Line Item'
        verbose_name_plural = 'Stock Count Line Items'
        unique_together = ('count', 'item')
        indexes = [
            models.Index(fields=['count', 'item']),
            models.Index(fields=['item']),
        ]

    def __str__(self):
        return f"{self.item.item_code} — Expected: {self.expected_quantity}, Counted: {self.counted_quantity or 'N/A'}"


class InventoryStockCountHistory(Main):
    """Audit trail for stock counts — logs every workflow transition."""

    ACTIONS = (
        ('CREATED', 'Count Created'),
        ('UPDATED', 'Count Updated'),
        ('ASSIGNED', 'Counters Assigned'),
        ('STARTED', 'Counting Started'),
        ('ITEM_COUNTED', 'Item Counted'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ADJUSTMENT_GENERATED', 'Adjustment Generated'),
    )

    count = models.ForeignKey(
        InventoryStockCount, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventoryStockCount.COUNT_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventoryStockCount.COUNT_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_count_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Stock Count History Entry'
        verbose_name_plural = 'Stock Count History Entries'
        indexes = [
            models.Index(fields=['count', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.count.count_number}: {self.action} ({self.timestamp})"


class InventoryStockCountAttachment(Main):
    """Files attached to a stock count (counting sheets, photos, evidence)."""

    count = models.ForeignKey(
        InventoryStockCount, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Stock Count Attachment'
        verbose_name_plural = 'Stock Count Attachments'

    def __str__(self):
        return self.file_name



# ============================================================================
# PURCHASE MANAGEMENT — SECTION 10
# ============================================================================

class PurchaseOrder(StatusTransitionMixin, Main):
    """
    Purchase Order — procurement of goods from suppliers.

    Workflow:
      DRAFT → SENT → PARTIALLY_RECEIVED → RECEIVED → CLOSED
                                              → CANCELLED
    """

    VALID_TRANSITIONS = {
        'DRAFT': {'SENT', 'CANCELLED'},
        'SENT': {'PARTIALLY_RECEIVED', 'RECEIVED', 'CANCELLED'},
        'PARTIALLY_RECEIVED': {'RECEIVED'},
        'RECEIVED': {'CLOSED'},
        'CLOSED': set(),
        'CANCELLED': set(),
    }

    ORDER_STATUSES = (
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Received'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    )

    tenant_id = models.UUIDField(db_index=True)
    order_number = models.CharField(max_length=100, db_index=True)
    order_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)

    # Supplier (reusing contacts module)
    supplier = models.ForeignKey(
        'contacts.Contact', on_delete=models.PROTECT,
        null=True, blank=True, related_name='purchase_orders'
    )
    supplier_name = models.CharField(
        max_length=500, blank=True,
        help_text='Denormalized supplier name for display'
    )
    supplier_reference = models.CharField(
        max_length=200, blank=True,
        help_text='Supplier reference number on their PO'
    )

    # Receiving location
    location = models.ForeignKey(
        'InventoryLocation', on_delete=models.PROTECT,
        null=True, blank=True, related_name='purchase_orders'
    )

    status = models.CharField(
        max_length=30, choices=ORDER_STATUSES, default='DRAFT'
    )

    # Financial
    subtotal = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    discount_amount = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    total_amount = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    # Dates
    sent_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)

    # Tracking
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_purchase_orders'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_purchase_orders'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
        unique_together = ('tenant_id', 'order_number')
        indexes = [
            models.Index(fields=['tenant_id', 'order_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'supplier']),
            models.Index(fields=['tenant_id', 'location']),
            models.Index(fields=['tenant_id', 'order_date']),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.get_status_display()})"


class PurchaseOrderItem(Main):
    """Line items for a purchase order."""

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'InventoryItem', on_delete=models.PROTECT,
        related_name='purchase_order_items'
    )
    ordered_quantity = models.DecimalField(max_digits=20, decimal_places=4)
    received_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    unit_price = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    tax_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Tax rate in percentage (e.g. 10.00 for 10%%)'
    )
    discount_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Discount rate in percentage (e.g. 5.00 for 5%%)'
    )
    line_total = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Calculated: (qty * unit_price) * (1 + tax_rate/100) * (1 - discount_rate/100)'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Purchase Order Line Item'
        verbose_name_plural = 'Purchase Order Line Items'
        indexes = [
            models.Index(fields=['purchase_order', 'item']),
        ]

    @property
    def outstanding_quantity(self):
        """Quantity not yet received."""
        return self.ordered_quantity - self.received_quantity

    def __str__(self):
        return f"{self.item.item_code} x {self.ordered_quantity}"


class PurchaseOrderHistory(Main):
    """Audit trail for purchase orders — logs every workflow transition."""

    ACTIONS = (
        ('CREATED', 'PO Created'),
        ('UPDATED', 'PO Updated'),
        ('SENT', 'Sent to Supplier'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    )

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=PurchaseOrder.ORDER_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=PurchaseOrder.ORDER_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='purchase_order_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Purchase Order History Entry'
        verbose_name_plural = 'Purchase Order History Entries'
        indexes = [
            models.Index(fields=['purchase_order', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.purchase_order.order_number}: {self.action} ({self.timestamp})"


class PurchaseOrderAttachment(Main):
    """Files attached to a purchase order (quotations, contracts, etc.)."""

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Purchase Order Attachment'
        verbose_name_plural = 'Purchase Order Attachments'

    def __str__(self):
        return self.file_name


class PurchaseReceipt(Main):
    """Goods Receipt Note (GRN) — records physical receipt of goods."""

    tenant_id = models.UUIDField(db_index=True)
    receipt_number = models.CharField(max_length=100, db_index=True)
    receipt_date = models.DateField()

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT,
        related_name='receipts'
    )
    location = models.ForeignKey(
        'InventoryLocation', on_delete=models.PROTECT,
        related_name='purchase_receipts'
    )
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_purchase_receipts'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Receipt'
        verbose_name_plural = 'Purchase Receipts'
        unique_together = ('tenant_id', 'receipt_number')
        indexes = [
            models.Index(fields=['tenant_id', 'receipt_number']),
            models.Index(fields=['tenant_id', 'purchase_order']),
            models.Index(fields=['tenant_id', 'receipt_date']),
        ]

    def __str__(self):
        return f"{self.receipt_number} ({self.purchase_order.order_number})"


class PurchaseReceiptItem(Main):
    """Line items for a goods receipt."""

    purchase_receipt = models.ForeignKey(
        PurchaseReceipt, on_delete=models.CASCADE,
        related_name='items'
    )
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem, on_delete=models.PROTECT,
        related_name='receipt_items'
    )
    item = models.ForeignKey(
        'InventoryItem', on_delete=models.PROTECT,
        related_name='purchase_receipt_items'
    )
    received_quantity = models.DecimalField(max_digits=20, decimal_places=4)
    unit_price = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )

    class Meta:
        verbose_name = 'Purchase Receipt Item'
        verbose_name_plural = 'Purchase Receipt Items'

    def __str__(self):
        return f"{self.item.item_code} x {self.received_quantity}"


# ============================================================================
# GOODS RECEIPT NOTE (GRN) — Section 11
# ============================================================================

class InventoryGoodsReceipt(StatusTransitionMixin, Main):
    """
    Goods Receipt Note (GRN) — records physical receipt of goods against a Purchase Order.

    Workflow:
      DRAFT → PENDING_APPROVAL → APPROVED → RECEIVED → COMPLETED
                                                       → CANCELLED
    """

    VALID_TRANSITIONS = {
        'DRAFT': {'PENDING_APPROVAL', 'CANCELLED'},
        'PENDING_APPROVAL': {'APPROVED', 'CANCELLED'},
        'APPROVED': {'RECEIVED', 'CANCELLED'},
        'RECEIVED': {'COMPLETED'},
        'COMPLETED': set(),
        'CANCELLED': set(),
    }

    GRN_STATUSES = (
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('RECEIVED', 'Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    tenant_id = models.UUIDField(db_index=True)
    grn_number = models.CharField(max_length=100, db_index=True)
    receipt_date = models.DateField()

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT,
        related_name='goods_receipts'
    )
    supplier = models.ForeignKey(
        'contacts.Contact', on_delete=models.PROTECT,
        null=True, blank=True, related_name='goods_receipts'
    )
    supplier_name = models.CharField(
        max_length=500, blank=True,
        help_text='Denormalized supplier name for display'
    )
    location = models.ForeignKey(
        'InventoryLocation', on_delete=models.PROTECT,
        related_name='goods_receipts'
    )

    status = models.CharField(
        max_length=30, choices=GRN_STATUSES, default='DRAFT'
    )
    remarks = models.TextField(blank=True)

    # Approval
    approved_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_grns'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    # Receiving
    received_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='received_grns'
    )
    received_at = models.DateTimeField(null=True, blank=True)

    # Completed
    completed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='completed_grns'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # Tracking
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_grns'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_grns'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Goods Receipt Note'
        verbose_name_plural = 'Goods Receipt Notes'
        unique_together = ('tenant_id', 'grn_number')
        indexes = [
            models.Index(fields=['tenant_id', 'grn_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'purchase_order']),
            models.Index(fields=['tenant_id', 'supplier']),
            models.Index(fields=['tenant_id', 'location']),
            models.Index(fields=['tenant_id', 'receipt_date']),
        ]

    def __str__(self):
        return f"{self.grn_number} ({self.get_status_display()})"


class InventoryGoodsReceiptItem(Main):
    """Line items for a Goods Receipt Note."""

    goods_receipt = models.ForeignKey(
        InventoryGoodsReceipt, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'InventoryItem', on_delete=models.PROTECT,
        related_name='goods_receipt_items'
    )
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='goods_receipt_items'
    )

    ordered_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Quantity ordered on the PO'
    )
    received_quantity = models.DecimalField(
        max_digits=20, decimal_places=4,
        help_text='Total quantity received'
    )
    accepted_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Quantity accepted (good condition)'
    )
    rejected_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Quantity rejected (quality issues)'
    )
    damage_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Quantity damaged in transit'
    )

    unit_price = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    returned_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Total quantity returned to supplier'
    )
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'GRN Line Item'
        verbose_name_plural = 'GRN Line Items'
        indexes = [
            models.Index(fields=['goods_receipt', 'item']),
        ]

    def __str__(self):
        return f"{self.item.item_code} x {self.received_quantity}"


class InventoryGoodsReceiptHistory(Main):
    """Audit trail for GRNs — logs every status change."""

    ACTIONS = (
        ('CREATED', 'GRN Created'),
        ('UPDATED', 'GRN Updated'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('RECEIVED', 'Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    goods_receipt = models.ForeignKey(
        InventoryGoodsReceipt, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventoryGoodsReceipt.GRN_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventoryGoodsReceipt.GRN_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='grn_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'GRN History Entry'
        verbose_name_plural = 'GRN History Entries'
        indexes = [
            models.Index(fields=['goods_receipt', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.goods_receipt.grn_number}: {self.action} ({self.timestamp})"


class InventoryGoodsReceiptAttachment(Main):
    """Files attached to a GRN (delivery challans, inspection reports, etc.)."""

    goods_receipt = models.ForeignKey(
        InventoryGoodsReceipt, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'GRN Attachment'
        verbose_name_plural = 'GRN Attachments'

    def __str__(self):
        return self.file_name


# ============================================================================
# SUPPLIER INVOICE — Section 12
# ============================================================================

class InventorySupplierInvoice(Main):
    """
    Supplier Invoice (Purchase Bill) — records vendor invoices against GRNs.

    Workflow:
      DRAFT → PENDING_APPROVAL → APPROVED → POSTED → PARTIALLY_PAID → PAID
                                                     → CANCELLED
                                                     → VOIDED

    Integrates with:
      - InventoryGoodsReceipt (linked GRNs)
      - payments.Payment (partial/full payments)
      - PurchaseOrder (optional reference)
    """

    INVOICE_STATUSES = (
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('POSTED', 'Posted'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
        ('VOIDED', 'Voided'),
    )

    PAYMENT_STATUSES = (
        ('UNPAID', 'Unpaid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
    )

    tenant_id = models.UUIDField(db_index=True)
    invoice_number = models.CharField(max_length=100, db_index=True)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    # Supplier (reusing contacts module)
    supplier = models.ForeignKey(
        'contacts.Contact', on_delete=models.PROTECT,
        null=True, blank=True, related_name='supplier_invoices'
    )
    supplier_name = models.CharField(
        max_length=500, blank=True,
        help_text='Denormalized supplier name for display'
    )
    supplier_invoice_number = models.CharField(
        max_length=200, blank=True,
        help_text="Vendor's invoice reference number"
    )

    # Currency
    currency = models.CharField(max_length=10, default='INR')
    exchange_rate = models.DecimalField(
        max_digits=20, decimal_places=6, default=1.0,
        help_text='Exchange rate from invoice currency to base currency'
    )

    # Purchase order reference (optional)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT,
        null=True, blank=True, related_name='supplier_invoices'
    )

    # Linked GRNs (multiple GRNs can be on one invoice)
    goods_receipts = models.ManyToManyField(
        InventoryGoodsReceipt, blank=True,
        related_name='supplier_invoices',
        help_text='Goods Receipt Notes covered by this invoice'
    )

    # Status
    status = models.CharField(
        max_length=30, choices=INVOICE_STATUSES, default='DRAFT'
    )
    payment_status = models.CharField(
        max_length=30, choices=PAYMENT_STATUSES, default='UNPAID'
    )

    # Financial fields
    subtotal = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    discount_amount = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    shipping_charges = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    other_charges = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    outstanding_amount = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )

    # Approval
    approved_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_supplier_invoices'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    # Posting
    posted_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='posted_supplier_invoices'
    )
    posted_at = models.DateTimeField(null=True, blank=True)

    # Remarks
    remarks = models.TextField(blank=True)
    terms = models.TextField(blank=True)

    # Tracking
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_supplier_invoices'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_supplier_invoices'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Supplier Invoice'
        verbose_name_plural = 'Supplier Invoices'
        unique_together = ('tenant_id', 'invoice_number')
        indexes = [
            models.Index(fields=['tenant_id', 'invoice_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'payment_status']),
            models.Index(fields=['tenant_id', 'supplier']),
            models.Index(fields=['tenant_id', 'purchase_order']),
            models.Index(fields=['tenant_id', 'invoice_date']),
            models.Index(fields=['tenant_id', 'due_date']),
        ]

    def __str__(self):
        return f"{self.invoice_number} ({self.get_status_display()})"


class InventorySupplierInvoiceItem(Main):
    """Line items for a Supplier Invoice."""

    invoice = models.ForeignKey(
        InventorySupplierInvoice, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'InventoryItem', on_delete=models.PROTECT,
        null=True, blank=True, related_name='supplier_invoice_items'
    )
    item_description = models.CharField(
        max_length=1000, blank=True,
        help_text='Description of the item/service'
    )

    # Reference to GRN item (tracks which received quantity is being invoiced)
    goods_receipt_item = models.ForeignKey(
        InventoryGoodsReceiptItem, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='supplier_invoice_items'
    )

    # Quantities
    quantity = models.DecimalField(max_digits=20, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    # Tax & discount per line
    tax_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Tax rate in percentage (e.g. 18.00 for 18%%)'
    )
    discount_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Discount rate in percentage (e.g. 5.00 for 5%%)'
    )

    # Calculated
    line_total = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Calculated: (qty * unit_price) * (1 + tax_rate/100) * (1 - discount_rate/100)'
    )

    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Supplier Invoice Line Item'
        verbose_name_plural = 'Supplier Invoice Line Items'
        indexes = [
            models.Index(fields=['invoice', 'item']),
        ]

    def __str__(self):
        return f"{self.item.item_code if self.item else self.item_description} x {self.quantity}"


class InventorySupplierInvoiceHistory(Main):
    """Audit trail for Supplier Invoices — logs every status change."""

    ACTIONS = (
        ('CREATED', 'Invoice Created'),
        ('UPDATED', 'Invoice Updated'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('POSTED', 'Posted'),
        ('PAYMENT_RECORDED', 'Payment Recorded'),
        ('CANCELLED', 'Cancelled'),
        ('VOIDED', 'Voided'),
    )

    invoice = models.ForeignKey(
        InventorySupplierInvoice, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventorySupplierInvoice.INVOICE_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventorySupplierInvoice.INVOICE_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='supplier_invoice_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Supplier Invoice History Entry'
        verbose_name_plural = 'Supplier Invoice History Entries'
        indexes = [
            models.Index(fields=['invoice', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number}: {self.action} ({self.timestamp})"


class InventorySupplierInvoiceAttachment(Main):
    """Files attached to a Supplier Invoice (vendor bill PDF, supporting docs, etc.)."""

    invoice = models.ForeignKey(
        InventorySupplierInvoice, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Supplier Invoice Attachment'
        verbose_name_plural = 'Supplier Invoice Attachments'

    def __str__(self):
        return self.file_name


# ============================================================================
# PURCHASE RETURN — Section 13
# ============================================================================

class InventoryPurchaseReturn(StatusTransitionMixin, Main):
    """
    Purchase Return — returning goods to suppliers against received GRNs/invoices.

    Workflow:
      DRAFT → PENDING_APPROVAL → APPROVED → RETURNED → COMPLETED
                                     → REJECTED
      (CANCEL from DRAFT/PENDING_APPROVAL/APPROVED)

    VALID_TRANSITIONS = {
        'DRAFT': {'PENDING_APPROVAL', 'CANCELLED'},
        'PENDING_APPROVAL': {'APPROVED', 'REJECTED', 'CANCELLED'},
        'APPROVED': {'RETURNED', 'CANCELLED'},
        'RETURNED': {'COMPLETED'},
        'REJECTED': set(),
        'COMPLETED': set(),
        'CANCELLED': set(),
    }

    Integrates with:
      - InventoryGoodsReceipt (source GRN)
      - InventorySupplierInvoice (financial adjustment)
      - PurchaseOrder (quantity update)
      - Stock Ledger (PURCHASE_RETURN entries)
    """

    RETURN_STATUSES = (
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('RETURNED', 'Returned'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    tenant_id = models.UUIDField(db_index=True)
    return_number = models.CharField(max_length=100, db_index=True)
    return_date = models.DateField()

    supplier = models.ForeignKey(
        'contacts.Contact', on_delete=models.PROTECT,
        null=True, blank=True, related_name='purchase_returns'
    )
    supplier_name = models.CharField(
        max_length=500, blank=True,
        help_text='Denormalized supplier name for display'
    )

    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT,
        null=True, blank=True, related_name='purchase_returns'
    )
    goods_receipt = models.ForeignKey(
        InventoryGoodsReceipt, on_delete=models.PROTECT,
        null=True, blank=True, related_name='purchase_returns'
    )
    supplier_invoice = models.ForeignKey(
        InventorySupplierInvoice, on_delete=models.PROTECT,
        null=True, blank=True, related_name='purchase_returns'
    )

    return_reason = models.CharField(
        max_length=500, blank=True,
        help_text='Reason for returning goods'
    )

    status = models.CharField(
        max_length=30, choices=RETURN_STATUSES, default='DRAFT'
    )

    subtotal = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    total_amount = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    approved_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_purchase_returns'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    processed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='processed_purchase_returns'
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    completed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='completed_purchase_returns'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    remarks = models.TextField(blank=True)

    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_purchase_returns'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_purchase_returns'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Return'
        verbose_name_plural = 'Purchase Returns'
        unique_together = ('tenant_id', 'return_number')
        indexes = [
            models.Index(fields=['tenant_id', 'return_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'supplier']),
            models.Index(fields=['tenant_id', 'goods_receipt']),
            models.Index(fields=['tenant_id', 'supplier_invoice']),
            models.Index(fields=['tenant_id', 'return_date']),
        ]

    def __str__(self):
        return f"{self.return_number} ({self.get_status_display()})"


class InventoryPurchaseReturnItem(Main):
    """Line items for a Purchase Return."""

    purchase_return = models.ForeignKey(
        InventoryPurchaseReturn, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'InventoryItem', on_delete=models.PROTECT,
        related_name='purchase_return_items'
    )
    goods_receipt_item = models.ForeignKey(
        InventoryGoodsReceiptItem, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='purchase_return_items'
    )

    received_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Original received quantity for reference'
    )
    return_quantity = models.DecimalField(
        max_digits=20, decimal_places=4,
        help_text='Quantity being returned'
    )
    damaged_quantity = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Of the returned qty, how much is damaged'
    )

    unit_cost = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    tax_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Tax rate in percentage'
    )
    total_amount = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Calculated: (return_qty * unit_cost) * (1 + tax_rate/100)'
    )

    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Purchase Return Line Item'
        verbose_name_plural = 'Purchase Return Line Items'
        indexes = [
            models.Index(fields=['purchase_return', 'item']),
        ]

    def __str__(self):
        return f"{self.item.item_code} x {self.return_quantity}"


class InventoryPurchaseReturnHistory(Main):
    """Audit trail for Purchase Returns — logs every status change."""

    ACTIONS = (
        ('CREATED', 'Return Created'),
        ('UPDATED', 'Return Updated'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('RETURNED', 'Returned to Supplier'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    purchase_return = models.ForeignKey(
        InventoryPurchaseReturn, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventoryPurchaseReturn.RETURN_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventoryPurchaseReturn.RETURN_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='purchase_return_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Purchase Return History Entry'
        verbose_name_plural = 'Purchase Return History Entries'
        indexes = [
            models.Index(fields=['purchase_return', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.purchase_return.return_number}: {self.action} ({self.timestamp})"


class InventoryPurchaseReturnAttachment(Main):
    """Files attached to a Purchase Return (return slips, photos, etc.)."""

    purchase_return = models.ForeignKey(
        InventoryPurchaseReturn, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Purchase Return Attachment'
        verbose_name_plural = 'Purchase Return Attachments'

    def __str__(self):
        return self.file_name


# ============================================================================
# SUPPLIER PAYMENT / ACCOUNTS PAYABLE — Section 14
# ============================================================================

class InventorySupplierPayment(Main):
    """
    Supplier Payment — records payments made to suppliers against invoices.

    Workflow:
      DRAFT -> PENDING_APPROVAL -> APPROVED -> POSTED -> COMPLETED
      (CANCEL from DRAFT/PENDING_APPROVAL)
      (VOID from APPROVED/POSTED/COMPLETED)

    Supports:
      - Single/multiple invoice allocation per payment
      - Partial payments on invoices
      - Advance payments (no invoice linked initially)
      - Full audit trail
    """

    PAYMENT_STATUSES = (
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('POSTED', 'Posted'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('VOIDED', 'Voided'),
    )

    PAYMENT_METHODS = (
        ('UPI', 'UPI'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Cheque', 'Cheque'),
        ('Net Banking', 'Net Banking'),
        ('DD', 'Demand Draft'),
        ('Other', 'Other'),
    )

    tenant_id = models.UUIDField(db_index=True)
    payment_number = models.CharField(max_length=100, db_index=True)
    payment_date = models.DateField()

    supplier = models.ForeignKey(
        'contacts.Contact', on_delete=models.PROTECT,
        null=True, blank=True, related_name='supplier_payments'
    )
    supplier_name = models.CharField(
        max_length=500, blank=True,
        help_text='Denormalized supplier name'
    )

    payment_method = models.CharField(
        max_length=30, choices=PAYMENT_METHODS, default='Bank Transfer'
    )
    bank_account = models.CharField(
        max_length=200, blank=True,
        help_text='Bank account or payment source reference'
    )
    reference_number = models.CharField(
        max_length=200, blank=True,
        help_text='Cheque number, transaction ID, UPI ref, etc.'
    )

    currency = models.CharField(max_length=10, default='INR')
    exchange_rate = models.DecimalField(
        max_digits=20, decimal_places=6, default=1
    )

    total_amount = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    allocated_amount = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Amount allocated to specific invoices'
    )
    unallocated_amount = models.DecimalField(
        max_digits=20, decimal_places=4, default=0,
        help_text='Unallocated / advance amount'
    )

    status = models.CharField(
        max_length=30, choices=PAYMENT_STATUSES, default='DRAFT'
    )

    approved_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_supplier_payments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    posted_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='posted_supplier_payments'
    )
    posted_at = models.DateTimeField(null=True, blank=True)

    completed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='completed_supplier_payments'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    remarks = models.TextField(blank=True)

    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_supplier_payments'
    )
    updated_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_supplier_payments'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Supplier Payment'
        verbose_name_plural = 'Supplier Payments'
        unique_together = ('tenant_id', 'payment_number')
        indexes = [
            models.Index(fields=['tenant_id', 'payment_number']),
            models.Index(fields=['tenant_id', 'status']),
            models.Index(fields=['tenant_id', 'supplier']),
            models.Index(fields=['tenant_id', 'payment_date']),
            models.Index(fields=['tenant_id', 'payment_method']),
        ]

    def __str__(self):
        return f"{self.payment_number} ({self.get_status_display()})"


class InventorySupplierPaymentAllocation(Main):
    """
    Allocation of a payment to a specific Supplier Invoice.

    One payment can allocate to multiple invoices.
    One invoice can receive multiple payment allocations.
    """

    payment = models.ForeignKey(
        InventorySupplierPayment, on_delete=models.CASCADE,
        related_name='allocations'
    )
    supplier_invoice = models.ForeignKey(
        InventorySupplierInvoice, on_delete=models.PROTECT,
        related_name='payment_allocations'
    )
    allocated_amount = models.DecimalField(
        max_digits=20, decimal_places=4,
        help_text='Amount allocated to this invoice'
    )

    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Payment Allocation'
        verbose_name_plural = 'Payment Allocations'
        indexes = [
            models.Index(fields=['payment', 'supplier_invoice']),
            models.Index(fields=['supplier_invoice']),
        ]
        unique_together = ('payment', 'supplier_invoice')

    def __str__(self):
        return f"{self.payment.payment_number} -> {self.supplier_invoice.invoice_number}: {self.allocated_amount}"


class InventorySupplierPaymentHistory(Main):
    """Audit trail for Supplier Payments."""

    ACTIONS = (
        ('CREATED', 'Payment Created'),
        ('UPDATED', 'Payment Updated'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('POSTED', 'Posted'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('VOIDED', 'Voided'),
    )

    payment = models.ForeignKey(
        InventorySupplierPayment, on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(max_length=30, choices=ACTIONS)
    from_status = models.CharField(
        max_length=30, blank=True,
        choices=InventorySupplierPayment.PAYMENT_STATUSES
    )
    to_status = models.CharField(
        max_length=30,
        choices=InventorySupplierPayment.PAYMENT_STATUSES
    )
    performed_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='supplier_payment_history_entries'
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Supplier Payment History Entry'
        verbose_name_plural = 'Supplier Payment History Entries'
        indexes = [
            models.Index(fields=['payment', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.payment.payment_number}: {self.action} ({self.timestamp})"


class InventorySupplierPaymentAttachment(Main):
    """Files attached to a Supplier Payment (payment receipts, bank statements, etc.)."""

    payment = models.ForeignKey(
        InventorySupplierPayment, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file_url = models.URLField(max_length=2000, blank=True)
    file_name = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Supplier Payment Attachment'
        verbose_name_plural = 'Supplier Payment Attachments'

    def __str__(self):
        return self.file_name


# ============================================================================
# INVENTORY FEATURE MANAGEMENT (Section 23)
# ============================================================================

class InventoryFeature(Main):
    """
    Master list of all inventory features (features that can be toggled per company).

    Designed to be future-ready — can evolve into a generic 'Feature' model
    shared across Sales, CRM, HR, etc. without major refactoring.
    """

    code = models.CharField(
        max_length=100, unique=True,
        help_text="Unique feature code: 'dashboard', 'items', 'stock', etc."
    )
    name = models.CharField(
        max_length=255,
        help_text="Display name: 'Dashboard', 'Items', 'Stock Availability'"
    )
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=100, blank=True,
        help_text="Lucide icon name: 'LayoutDashboard', 'Box', etc."
    )
    route = models.CharField(
        max_length=255, blank=True,
        help_text="Frontend route path: '/inventory/dashboard', '/inventory/items'"
    )
    display_order = models.IntegerField(default=0, help_text="Sort order")
    is_active = models.BooleanField(default=True, help_text="Globally active")

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Inventory Feature'
        verbose_name_plural = 'Inventory Features'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class CompanyInventoryFeature(Main):
    """
    Company-specific toggle for each inventory feature.

    Links an Organization (company) to an InventoryFeature.
    When enabled=False, the feature is hidden from that company's UI and blocked at the API level.

    Future-ready: can evolve into a generic 'CompanyFeature' model
    shared across all ERP modules.
    """

    company = models.ForeignKey(
        'menus.Organization', on_delete=models.CASCADE,
        related_name='inventory_feature_configs'
    )
    inventory_feature = models.ForeignKey(
        InventoryFeature, on_delete=models.CASCADE,
        related_name='company_configs'
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Company Inventory Feature'
        verbose_name_plural = 'Company Inventory Feature Configs'
        unique_together = ('company', 'inventory_feature')
        indexes = [
            models.Index(fields=['company', 'enabled']),
            models.Index(fields=['company', 'inventory_feature']),
        ]

    def __str__(self):
        status = 'enabled' if self.enabled else 'disabled'
        return f"{self.company.name} → {self.inventory_feature.code} ({status})"
