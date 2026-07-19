from django.urls import path, include
from rest_framework.routers import DefaultRouter
from inventory.views import (
    ItemCategoryViewSet, UnitViewSet, BrandViewSet,
    InventoryItemViewSet, CustomFieldDefinitionViewSet,
    LocationTypeViewSet, LocationViewSet,
    StockLedgerViewSet, StockLedgerEntryView, StockAvailabilityViewSet,
    TransferViewSet,
    AdjustmentViewSet, AdjustmentReasonViewSet,
    ReservationViewSet, ReservationReasonViewSet,
    StockCountReasonViewSet, StockCountViewSet,
    PurchaseOrderViewSet, PurchaseReceiptViewSet,
    GoodsReceiptViewSet, GoodsReceiptAttachmentViewSet,
    SupplierInvoiceViewSet, SupplierInvoiceAttachmentViewSet,
    PurchaseReturnViewSet, PurchaseReturnAttachmentViewSet,
    SupplierPaymentViewSet, SupplierPaymentAttachmentViewSet,
    DashboardViewSet,
)

router = DefaultRouter()
router.register(r'categories', ItemCategoryViewSet, basename='item-categories')
router.register(r'units', UnitViewSet, basename='units')
router.register(r'brands', BrandViewSet, basename='brands')
router.register(r'items', InventoryItemViewSet, basename='inventory-items')
router.register(r'custom-fields', CustomFieldDefinitionViewSet, basename='custom-fields')
router.register(r'location-types', LocationTypeViewSet, basename='location-types')
router.register(r'locations', LocationViewSet, basename='locations')
router.register(r'transfers', TransferViewSet, basename='transfers')
router.register(r'adjustments', AdjustmentViewSet, basename='adjustments')
router.register(r'adjustment-reasons', AdjustmentReasonViewSet, basename='adjustment-reasons')
router.register(r'reservations', ReservationViewSet, basename='reservations')
router.register(r'reservation-reasons', ReservationReasonViewSet, basename='reservation-reasons')
router.register(r'stock/ledger', StockLedgerViewSet, basename='stock-ledger')
router.register(r'stock/availability', StockAvailabilityViewSet, basename='stock-availability')
router.register(r'stock-count-reasons', StockCountReasonViewSet, basename='stock-count-reasons')
router.register(r'stock-counts', StockCountViewSet, basename='stock-counts')
router.register(r'purchase-orders', PurchaseOrderViewSet, basename='purchase-orders')
router.register(r'purchase-receipts', PurchaseReceiptViewSet, basename='purchase-receipts')
router.register(r'goods-receipts', GoodsReceiptViewSet, basename='goods-receipts')
router.register(r'supplier-invoices', SupplierInvoiceViewSet, basename='supplier-invoices')
router.register(r'purchase-returns', PurchaseReturnViewSet, basename='purchase-returns')
router.register(r'supplier-payments', SupplierPaymentViewSet, basename='supplier-payments')

router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    # Custom URL for export - placed before router to avoid conflict with detail pk pattern
    path('purchase-orders/export/', PurchaseOrderViewSet.as_view({'get': 'export'}), name='purchase-orders-export'),
    path('goods-receipts/export/', GoodsReceiptViewSet.as_view({'get': 'export'}), name='goods-receipts-export'),
    path('supplier-invoices/export/', SupplierInvoiceViewSet.as_view({'get': 'export'}), name='supplier-invoices-export'),
    path('purchase-returns/export/', PurchaseReturnViewSet.as_view({'get': 'export'}), name='purchase-returns-export'),
    path('supplier-payments/export/', SupplierPaymentViewSet.as_view({'get': 'export'}), name='supplier-payments-export'),
    path('', include(router.urls)),
    path('stock/ledger/entries/', StockLedgerEntryView.as_view({'post': 'create'}), name='stock-ledger-entry'),
]
