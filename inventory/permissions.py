from rest_framework import permissions


def _user_has_role(user, allowed_roles):
    """Check if a user has one of the allowed roles."""
    return bool(
        user and
        user.is_authenticated and
        user.role in allowed_roles
    )


def _owns_object(user, obj):
    """Check if the object belongs to the user's organization (tenant)."""
    if not user or not user.is_authenticated:
        return False
    tenant_id = getattr(obj, 'tenant_id', None)
    if tenant_id is None:
        return True  # Objects without tenant_id are accessible
    return str(tenant_id) == str(user.organization_id)


class TenantAwarePermission(permissions.BasePermission):
    """
    Base permission that provides tenant-aware object-level permission.
    All inventory permission classes should inherit from this.
    """
    role_required = None  # Override in subclasses — list of allowed roles

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if self.role_required is None:
            return True
        return request.user.role in self.role_required

    def has_object_permission(self, request, view, obj):
        return _owns_object(request.user, obj)


# ============================================================================
# ITEM PERMISSIONS
# ============================================================================

class CanViewItems(TenantAwarePermission):
    """inventory.items.view"""


class CanCreateItems(TenantAwarePermission):
    """inventory.items.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditItems(TenantAwarePermission):
    """inventory.items.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteItems(TenantAwarePermission):
    """inventory.items.delete"""
    role_required = ['Superadmin', 'Admin']


class CanImportItems(TenantAwarePermission):
    """inventory.items.import"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanExportItems(TenantAwarePermission):
    """inventory.items.export"""


# ============================================================================
# CATEGORY PERMISSIONS
# ============================================================================

class CanViewCategories(TenantAwarePermission):
    """inventory.categories.view"""


class CanCreateCategories(TenantAwarePermission):
    """inventory.categories.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditCategories(TenantAwarePermission):
    """inventory.categories.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteCategories(TenantAwarePermission):
    """inventory.categories.delete"""
    role_required = ['Superadmin', 'Admin']


# ============================================================================
# UNIT PERMISSIONS
# ============================================================================

class CanViewUnits(TenantAwarePermission):
    """inventory.units.view"""


class CanCreateUnits(TenantAwarePermission):
    """inventory.units.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditUnits(TenantAwarePermission):
    """inventory.units.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteUnits(TenantAwarePermission):
    """inventory.units.delete"""
    role_required = ['Superadmin', 'Admin']


# ============================================================================
# BRAND PERMISSIONS
# ============================================================================

class CanViewBrands(TenantAwarePermission):
    """inventory.brands.view"""


class CanCreateBrands(TenantAwarePermission):
    """inventory.brands.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditBrands(TenantAwarePermission):
    """inventory.brands.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteBrands(TenantAwarePermission):
    """inventory.brands.delete"""
    role_required = ['Superadmin', 'Admin']


# ============================================================================
# LOCATION TYPE PERMISSIONS
# ============================================================================

class CanViewLocationTypes(TenantAwarePermission):
    """inventory.location_types.view"""


class CanCreateLocationTypes(TenantAwarePermission):
    """inventory.location_types.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditLocationTypes(TenantAwarePermission):
    """inventory.location_types.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteLocationTypes(TenantAwarePermission):
    """inventory.location_types.delete"""
    role_required = ['Superadmin', 'Admin']


# ============================================================================
# LOCATION PERMISSIONS
# ============================================================================

class CanViewLocations(TenantAwarePermission):
    """inventory.locations.view"""


class CanCreateLocations(TenantAwarePermission):
    """inventory.locations.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditLocations(TenantAwarePermission):
    """inventory.locations.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteLocations(TenantAwarePermission):
    """inventory.locations.delete"""
    role_required = ['Superadmin', 'Admin']


# ============================================================================
# STOCK PERMISSIONS
# ============================================================================

class CanViewStock(TenantAwarePermission):
    """inventory.stock.view"""


class CanExportStock(TenantAwarePermission):
    """inventory.stock.export"""


class CanViewStockSnapshot(TenantAwarePermission):
    """inventory.stock.snapshot"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanViewStockValuation(TenantAwarePermission):
    """inventory.stock.valuation"""
    role_required = ['Superadmin', 'Admin', 'Manager']


# ============================================================================
# TRANSFER PERMISSIONS
# ============================================================================

class CanViewTransfers(TenantAwarePermission):
    """inventory.transfers.view"""


class CanCreateTransfers(TenantAwarePermission):
    """inventory.transfers.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditTransfers(TenantAwarePermission):
    """inventory.transfers.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteTransfers(TenantAwarePermission):
    """inventory.transfers.delete"""
    role_required = ['Superadmin', 'Admin']


class CanSubmitTransfer(TenantAwarePermission):
    """inventory.transfers.submit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanApproveTransfer(TenantAwarePermission):
    """inventory.transfers.approve"""
    role_required = ['Superadmin', 'Admin']


class CanReceiveTransfer(TenantAwarePermission):
    """inventory.transfers.receive"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanExportTransfers(TenantAwarePermission):
    """inventory.transfers.export"""


# ============================================================================
# ADJUSTMENT PERMISSIONS (Section 7)
# ============================================================================

class CanViewAdjustments(TenantAwarePermission):
    """inventory.adjustments.view"""


class CanCreateAdjustments(TenantAwarePermission):
    """inventory.adjustments.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditAdjustments(TenantAwarePermission):
    """inventory.adjustments.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteAdjustments(TenantAwarePermission):
    """inventory.adjustments.delete"""
    role_required = ['Superadmin', 'Admin']


class CanSubmitAdjustment(TenantAwarePermission):
    """inventory.adjustments.submit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanApproveAdjustment(TenantAwarePermission):
    """inventory.adjustments.approve"""
    role_required = ['Superadmin', 'Admin']


class CanApplyAdjustment(TenantAwarePermission):
    """inventory.adjustments.apply"""
    role_required = ['Superadmin', 'Admin']


class CanExportAdjustments(TenantAwarePermission):
    """inventory.adjustments.export"""


# ============================================================================
# RESERVATION PERMISSIONS (Section 8)
# ============================================================================

class CanViewReservations(TenantAwarePermission):
    """inventory.reservations.view"""


class CanCreateReservations(TenantAwarePermission):
    """inventory.reservations.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditReservations(TenantAwarePermission):
    """inventory.reservations.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteReservations(TenantAwarePermission):
    """inventory.reservations.delete"""
    role_required = ['Superadmin', 'Admin']


class CanActivateReservations(TenantAwarePermission):
    """inventory.reservations.activate"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanFulfillReservations(TenantAwarePermission):
    """inventory.reservations.fulfill"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCancelReservations(TenantAwarePermission):
    """inventory.reservations.cancel"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanExportReservations(TenantAwarePermission):
    """inventory.reservations.export"""


# ============================================================================
# STOCK COUNT PERMISSIONS (Section 9)
# ============================================================================

class CanViewStockCounts(TenantAwarePermission):
    """inventory.stock_counts.view"""


class CanCreateStockCounts(TenantAwarePermission):
    """inventory.stock_counts.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditStockCounts(TenantAwarePermission):
    """inventory.stock_counts.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanAssignStockCounts(TenantAwarePermission):
    """inventory.stock_counts.assign"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCountStockItems(TenantAwarePermission):
    """inventory.stock_counts.count — only assigned counters can count"""
    def has_object_permission(self, request, view, obj):
        """Check if the user is assigned to this specific stock count."""
        if not _owns_object(request.user, obj):
            return False
        return bool(
            request.user.role in ['Superadmin', 'Admin'] or
            obj.assigned_counters.filter(id=request.user.id).exists()
        )


class CanSubmitStockCounts(TenantAwarePermission):
    """inventory.stock_counts.submit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanApproveStockCounts(TenantAwarePermission):
    """inventory.stock_counts.approve"""
    role_required = ['Superadmin', 'Admin']


class CanCancelStockCounts(TenantAwarePermission):
    """inventory.stock_counts.cancel"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanExportStockCounts(TenantAwarePermission):
    """inventory.stock_counts.export"""


class CanPrintStockCounts(TenantAwarePermission):
    """inventory.stock_counts.print"""


# ============================================================================
# PURCHASE ORDER PERMISSIONS (Section 10)
# ============================================================================

class CanViewPurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.view"""


class CanCreatePurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditPurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeletePurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.delete"""
    role_required = ['Superadmin', 'Admin']


class CanSendPurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.send"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanReceivePurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.receive"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCancelPurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.cancel"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanClosePurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.close"""
    role_required = ['Superadmin', 'Admin']


class CanExportPurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.export"""


class CanPrintPurchaseOrders(TenantAwarePermission):
    """inventory.purchase_orders.print"""


# ============================================================================
# GOODS RECEIPT NOTE PERMISSIONS (Section 11)
# ============================================================================

class CanViewGRNs(TenantAwarePermission):
    """inventory.grns.view"""


class CanCreateGRNs(TenantAwarePermission):
    """inventory.grns.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditGRNs(TenantAwarePermission):
    """inventory.grns.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteGRNs(TenantAwarePermission):
    """inventory.grns.delete"""
    role_required = ['Superadmin', 'Admin']


class CanSubmitGRN(TenantAwarePermission):
    """inventory.grns.submit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanApproveGRN(TenantAwarePermission):
    """inventory.grns.approve"""
    role_required = ['Superadmin', 'Admin']


class CanReceiveGRN(TenantAwarePermission):
    """inventory.grns.receive"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCancelGRN(TenantAwarePermission):
    """inventory.grns.cancel"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanExportGRNs(TenantAwarePermission):
    """inventory.grns.export"""


class CanPrintGRNs(TenantAwarePermission):
    """inventory.grns.print"""


# ============================================================================
# SUPPLIER INVOICE PERMISSIONS (Section 12)
# ============================================================================

class CanViewSupplierInvoices(TenantAwarePermission):
    """inventory.supplier_invoices.view"""


class CanCreateSupplierInvoices(TenantAwarePermission):
    """inventory.supplier_invoices.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditSupplierInvoices(TenantAwarePermission):
    """inventory.supplier_invoices.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteSupplierInvoices(TenantAwarePermission):
    """inventory.supplier_invoices.delete"""
    role_required = ['Superadmin', 'Admin']


class CanSubmitSupplierInvoice(TenantAwarePermission):
    """inventory.supplier_invoices.submit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanApproveSupplierInvoice(TenantAwarePermission):
    """inventory.supplier_invoices.approve"""
    role_required = ['Superadmin', 'Admin']


class CanPostSupplierInvoice(TenantAwarePermission):
    """inventory.supplier_invoices.post"""
    role_required = ['Superadmin', 'Admin']


class CanRecordPaymentSupplierInvoice(TenantAwarePermission):
    """inventory.supplier_invoices.record_payment"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCancelSupplierInvoice(TenantAwarePermission):
    """inventory.supplier_invoices.cancel"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanVoidSupplierInvoice(TenantAwarePermission):
    """inventory.supplier_invoices.void"""
    role_required = ['Superadmin', 'Admin']


class CanExportSupplierInvoices(TenantAwarePermission):
    """inventory.supplier_invoices.export"""


class CanPrintSupplierInvoices(TenantAwarePermission):
    """inventory.supplier_invoices.print"""


# ============================================================================
# PURCHASE RETURN PERMISSIONS (Section 13)
# ============================================================================

class CanViewPurchaseReturns(TenantAwarePermission):
    """inventory.purchase_returns.view"""


class CanCreatePurchaseReturns(TenantAwarePermission):
    """inventory.purchase_returns.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditPurchaseReturns(TenantAwarePermission):
    """inventory.purchase_returns.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeletePurchaseReturns(TenantAwarePermission):
    """inventory.purchase_returns.delete"""
    role_required = ['Superadmin', 'Admin']


class CanSubmitPurchaseReturn(TenantAwarePermission):
    """inventory.purchase_returns.submit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanApprovePurchaseReturn(TenantAwarePermission):
    """inventory.purchase_returns.approve"""
    role_required = ['Superadmin', 'Admin']


class CanReturnPurchaseReturn(TenantAwarePermission):
    """inventory.purchase_returns.return_items"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCompletePurchaseReturn(TenantAwarePermission):
    """inventory.purchase_returns.complete"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCancelPurchaseReturn(TenantAwarePermission):
    """inventory.purchase_returns.cancel"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanExportPurchaseReturns(TenantAwarePermission):
    """inventory.purchase_returns.export"""


# ============================================================================
# SUPPLIER PAYMENT PERMISSIONS (Section 14)
# ============================================================================

class CanViewSupplierPayments(TenantAwarePermission):
    """inventory.supplier_payments.view"""


class CanCreateSupplierPayments(TenantAwarePermission):
    """inventory.supplier_payments.create"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanEditSupplierPayments(TenantAwarePermission):
    """inventory.supplier_payments.edit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanDeleteSupplierPayments(TenantAwarePermission):
    """inventory.supplier_payments.delete"""
    role_required = ['Superadmin', 'Admin']


class CanSubmitSupplierPayment(TenantAwarePermission):
    """inventory.supplier_payments.submit"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanApproveSupplierPayment(TenantAwarePermission):
    """inventory.supplier_payments.approve"""
    role_required = ['Superadmin', 'Admin']


class CanPostSupplierPayment(TenantAwarePermission):
    """inventory.supplier_payments.post"""
    role_required = ['Superadmin', 'Admin']


class CanAllocateSupplierPayment(TenantAwarePermission):
    """inventory.supplier_payments.allocate"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanCancelSupplierPayment(TenantAwarePermission):
    """inventory.supplier_payments.cancel"""
    role_required = ['Superadmin', 'Admin', 'Manager']


class CanVoidSupplierPayment(TenantAwarePermission):
    """inventory.supplier_payments.void"""
    role_required = ['Superadmin', 'Admin']


class CanExportSupplierPayments(TenantAwarePermission):
    """inventory.supplier_payments.export"""


# ============================================================================
# DASHBOARD & REPORTS PERMISSIONS (Section 21)
# ============================================================================

class CanViewDashboard(TenantAwarePermission):
    """inventory.dashboard.view"""


class CanViewReports(TenantAwarePermission):
    """inventory.reports.view"""


class CanExportReports(TenantAwarePermission):
    """inventory.reports.export"""


class CanPrintReports(TenantAwarePermission):
    """inventory.reports.print"""
