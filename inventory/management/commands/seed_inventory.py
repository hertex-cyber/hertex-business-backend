"""
Seed dummy data for all inventory modules so reports can be tested.

Usage:
    python manage.py seed_inventory
    python manage.py seed_inventory --tenant=<uuid> --noinput
"""

import uuid
import secrets
from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from inventory.models import (
    ItemCategory, Unit, Brand, InventoryItem,
    InventoryLocationType, InventoryLocation,
    InventoryTransfer, InventoryTransferItem,
    InventoryAdjustmentReason, InventoryAdjustment, InventoryAdjustmentItem,
    InventoryReservationReason, InventoryReservation, InventoryReservationItem,
    StockCountReason, InventoryStockCount, InventoryStockCountItem,
    PurchaseOrder, PurchaseOrderItem,
    InventoryGoodsReceipt, InventoryGoodsReceiptItem,
    InventorySupplierInvoice, InventorySupplierInvoiceItem,
    InventoryPurchaseReturn, InventoryPurchaseReturnItem,
    InventorySupplierPayment, InventorySupplierPaymentAllocation,
    StockLedger,
)
from inventory.services.stock_engine import create_ledger_entry


class Command(BaseCommand):
    help = 'Seed dummy inventory data for report testing'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Existing tenant UUID')
        parser.add_argument('--noinput', action='store_true', help='Skip confirmation')

    def handle(self, *args, **options):
        self.noinput = options.get('noinput', False)
        self.stdout.write(self.style.WARNING('Seed: Inventory dummy data generator'))

        provided_tenant = options.get('tenant')
        if provided_tenant:
            self.tenant_id = uuid.UUID(provided_tenant)
            self.stdout.write(f'  Using provided tenant: {self.tenant_id}')
        else:
            self.tenant_id = uuid.uuid4()
            self.stdout.write(f'  Generated tenant UUID: {self.tenant_id}')

        if not self.noinput:
            self.stdout.write('')
            answer = input('  This will CREATE sample data. Continue? [y/N]: ')
            if answer.lower() != 'y':
                self.stdout.write(self.style.WARNING('  Aborted.'))
                return

        with transaction.atomic():
            self._seed_master_data()
            self._seed_items()
            self._seed_purchase_order()
            self._seed_grn_and_ledger()
            self._seed_transfer()
            self._seed_adjustment()
            self._seed_reservation()
            self._seed_stock_count()
            self._seed_invoice_and_return_and_payment()

        total = dict(
            categories=ItemCategory.objects.filter(tenant_id=self.tenant_id).count(),
            units=Unit.objects.filter(tenant_id=self.tenant_id).count(),
            brands=Brand.objects.filter(tenant_id=self.tenant_id).count(),
            locations=InventoryLocation.objects.filter(tenant_id=self.tenant_id).count(),
            items=InventoryItem.objects.filter(tenant_id=self.tenant_id).count(),
            transfers=InventoryTransfer.objects.filter(tenant_id=self.tenant_id).count(),
            adjustments=InventoryAdjustment.objects.filter(tenant_id=self.tenant_id).count(),
            reservations=InventoryReservation.objects.filter(tenant_id=self.tenant_id).count(),
            stock_counts=InventoryStockCount.objects.filter(tenant_id=self.tenant_id).count(),
            purchase_orders=PurchaseOrder.objects.filter(tenant_id=self.tenant_id).count(),
            goods_receipts=InventoryGoodsReceipt.objects.filter(tenant_id=self.tenant_id).count(),
            invoices=InventorySupplierInvoice.objects.filter(tenant_id=self.tenant_id).count(),
            returns=InventoryPurchaseReturn.objects.filter(tenant_id=self.tenant_id).count(),
            payments=InventorySupplierPayment.objects.filter(tenant_id=self.tenant_id).count(),
            ledger_entries=StockLedger.objects.filter(tenant_id=self.tenant_id).count(),
        )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('  Seed complete.'))
        self.stdout.write(f'  Tenant ID: {self.tenant_id}')
        for k, v in total.items():
            self.stdout.write(f'    {k}: {v}')

    # ------------------------------------------------------------------
    # Master data
    # ------------------------------------------------------------------

    def _seed_master_data(self):
        self.stdout.write('  Creating master data...')

        self.cat_a = ItemCategory.objects.create(
            tenant_id=self.tenant_id, category_code='CAT-ELEC',
            category_name='Electronics', status='ACTIVE',
        )
        self.cat_b = ItemCategory.objects.create(
            tenant_id=self.tenant_id, category_code='CAT-OFFICE',
            category_name='Office Supplies', status='ACTIVE',
        )
        self.cat_c = ItemCategory.objects.create(
            tenant_id=self.tenant_id, category_code='CAT-RAW',
            category_name='Raw Materials', status='ACTIVE',
        )

        self.unit_pcs = Unit.objects.create(
            tenant_id=self.tenant_id, unit_code='PCS',
            unit_name='Pieces', symbol='pcs', status='ACTIVE',
        )
        self.unit_kg = Unit.objects.create(
            tenant_id=self.tenant_id, unit_code='KG',
            unit_name='Kilogram', symbol='kg', status='ACTIVE',
        )
        self.unit_box = Unit.objects.create(
            tenant_id=self.tenant_id, unit_code='BOX',
            unit_name='Box', symbol='box', status='ACTIVE',
        )

        self.brand_a = Brand.objects.create(
            tenant_id=self.tenant_id, brand_code='BRD-ACE',
            brand_name='Acme Corp', status='ACTIVE',
        )
        self.brand_b = Brand.objects.create(
            tenant_id=self.tenant_id, brand_code='BRD-GLOB',
            brand_name='GlobalTech', status='ACTIVE',
        )

        self.loc_type_wh = InventoryLocationType.objects.create(
            tenant_id=self.tenant_id, type_code='WH',
            type_name='Warehouse', status='ACTIVE',
        )
        self.loc_type_st = InventoryLocationType.objects.create(
            tenant_id=self.tenant_id, type_code='ST',
            type_name='Store', status='ACTIVE',
        )

        self.loc_a = InventoryLocation.objects.create(
            tenant_id=self.tenant_id, location_code='WH-MAIN',
            location_name='Main Warehouse',
            location_type=self.loc_type_wh, status='ACTIVE',
        )
        self.loc_b = InventoryLocation.objects.create(
            tenant_id=self.tenant_id, location_code='ST-DOWNTOWN',
            location_name='Downtown Store',
            location_type=self.loc_type_st, status='ACTIVE',
        )

        self.adj_reason = InventoryAdjustmentReason.objects.create(
            tenant_id=self.tenant_id, reason_code='ADJ-DMG',
            reason_name='Damage Write-off',
            adjustment_type='DECREASE', status='ACTIVE',
        )
        self.resv_reason = InventoryReservationReason.objects.create(
            tenant_id=self.tenant_id, reason_code='RSV-CUST',
            reason_name='Customer Order',
            status='ACTIVE',
        )
        self.sc_reason = StockCountReason.objects.create(
            tenant_id=self.tenant_id, reason_code='SC-ANNUAL',
            reason_name='Annual Physical Count',
            status='ACTIVE',
        )

    def _seed_items(self):
        self.stdout.write('  Creating items...')

        items_data = [
            dict(item_code='ITM-LAPTOP-001', item_name='Laptop Pro 15"',
                 category=self.cat_a, unit=self.unit_pcs, brand=self.brand_a,
                 cost_price=Decimal('75000'), selling_price=Decimal('89999'),
                 min_stock_level=Decimal('5'), reorder_level=Decimal('10'),
                 max_stock_level=Decimal('50'), status='ACTIVE'),
            dict(item_code='ITM-MOUSE-001', item_name='Wireless Mouse',
                 category=self.cat_a, unit=self.unit_pcs, brand=self.brand_b,
                 cost_price=Decimal('500'), selling_price=Decimal('799'),
                 min_stock_level=Decimal('10'), reorder_level=Decimal('20'),
                 max_stock_level=Decimal('100'), status='ACTIVE'),
            dict(item_code='ITM-KEYB-001', item_name='Mechanical Keyboard',
                 category=self.cat_a, unit=self.unit_pcs, brand=self.brand_b,
                 cost_price=Decimal('2000'), selling_price=Decimal('3499'),
                 min_stock_level=Decimal('5'), reorder_level=Decimal('15'),
                 max_stock_level=Decimal('50'), status='ACTIVE'),
            dict(item_code='ITM-PAPER-001', item_name='A4 Printer Paper (5000 sheets)',
                 category=self.cat_b, unit=self.unit_box, brand=self.brand_a,
                 cost_price=Decimal('250'), selling_price=Decimal('399'),
                 min_stock_level=Decimal('10'), reorder_level=Decimal('20'),
                 max_stock_level=Decimal('200'), status='ACTIVE'),
            dict(item_code='ITM-STEEL-001', item_name='Steel Rod 12mm',
                 category=self.cat_c, unit=self.unit_kg, brand=self.brand_a,
                 cost_price=Decimal('80'), selling_price=Decimal('120'),
                 min_stock_level=Decimal('100'), reorder_level=Decimal('500'),
                 max_stock_level=Decimal('5000'), status='ACTIVE'),
            dict(item_code='ITM-BOLT-001', item_name='Hex Bolt M10',
                 category=self.cat_c, unit=self.unit_pcs, brand=self.brand_a,
                 cost_price=Decimal('2'), selling_price=Decimal('5'),
                 min_stock_level=Decimal('500'), reorder_level=Decimal('1000'),
                 max_stock_level=Decimal('50000'), status='ACTIVE'),
            dict(item_code='ITM-LAPTOP-002', item_name='Laptop Pro 14"',
                 category=self.cat_a, unit=self.unit_pcs, brand=self.brand_a,
                 cost_price=Decimal('65000'), selling_price=Decimal('79999'),
                 min_stock_level=Decimal('3'), reorder_level=Decimal('8'),
                 max_stock_level=Decimal('30'), status='ACTIVE'),
            dict(item_code='ITM-MON-001', item_name='27" 4K Monitor',
                 category=self.cat_a, unit=self.unit_pcs, brand=self.brand_b,
                 cost_price=Decimal('22000'), selling_price=Decimal('29999'),
                 min_stock_level=Decimal('5'), reorder_level=Decimal('10'),
                 max_stock_level=Decimal('40'), status='ACTIVE'),
            dict(item_code='ITM-STAP-001', item_name='Stapler Heavy Duty',
                 category=self.cat_b, unit=self.unit_pcs, brand=self.brand_a,
                 cost_price=Decimal('150'), selling_price=Decimal('299'),
                 min_stock_level=Decimal('5'), reorder_level=Decimal('20'),
                 max_stock_level=Decimal('50'), status='ACTIVE'),
            dict(item_code='ITM-SHEET-001', item_name='Aluminium Sheet 2mm',
                 category=self.cat_c, unit=self.unit_kg, brand=self.brand_b,
                 cost_price=Decimal('120'), selling_price=Decimal('200'),
                 min_stock_level=Decimal('50'), reorder_level=Decimal('100'),
                 max_stock_level=Decimal('1000'), status='INACTIVE'),
        ]

        self.items = []
        for data in items_data:
            obj = InventoryItem.objects.create(tenant_id=self.tenant_id, **data)
            self.items.append(obj)

    # ------------------------------------------------------------------
    # Purchase Order
    # ------------------------------------------------------------------

    def _seed_purchase_order(self):
        self.stdout.write('  Creating purchase order...')

        today = timezone.now().date()
        self.po = PurchaseOrder.objects.create(
            tenant_id=self.tenant_id,
            order_number='PO-2024-0001',
            order_date=today - timedelta(days=14),
            expected_delivery_date=today - timedelta(days=7),
            supplier_name='TechDistributor Inc.',
            status='CLOSED',
            subtotal=Decimal('325000'),
            tax_amount=Decimal('58500'),
            total_amount=Decimal('383500'),
        )

        po_items = [
            dict(item=self.items[0], ordered_quantity=Decimal('10'),
                 unit_price=Decimal('75000'), line_total=Decimal('750000')),
            dict(item=self.items[1], ordered_quantity=Decimal('50'),
                 unit_price=Decimal('500'), line_total=Decimal('25000')),
            dict(item=self.items[2], ordered_quantity=Decimal('20'),
                 unit_price=Decimal('2000'), line_total=Decimal('40000')),
            dict(item=self.items[3], ordered_quantity=Decimal('30'),
                 unit_price=Decimal('250'), line_total=Decimal('7500')),
            dict(item=self.items[4], ordered_quantity=Decimal('3000'),
                 unit_price=Decimal('80'), line_total=Decimal('240000')),
        ]
        self.po_items = []
        for d in po_items:
            pi = PurchaseOrderItem.objects.create(
                purchase_order=self.po, received_quantity=d['ordered_quantity'],
                **d,
            )
            self.po_items.append(pi)

    # ------------------------------------------------------------------
    # GRN + StockLedger entries
    # ------------------------------------------------------------------

    def _seed_grn_and_ledger(self):
        self.stdout.write('  Creating goods receipt & ledger entries...')

        today = timezone.now().date()

        self.grn = InventoryGoodsReceipt.objects.create(
            tenant_id=self.tenant_id,
            grn_number='GRN-2024-0001',
            receipt_date=today - timedelta(days=10),
            purchase_order=self.po,
            supplier_name='TechDistributor Inc.',
            location=self.loc_a,
            status='COMPLETED',
        )

        for po_item in self.po_items:
            InventoryGoodsReceiptItem.objects.create(
                goods_receipt=self.grn,
                item=po_item.item,
                purchase_order_item=po_item,
                ordered_quantity=po_item.ordered_quantity,
                received_quantity=po_item.ordered_quantity,
                accepted_quantity=po_item.ordered_quantity,
                unit_price=po_item.unit_price,
            )
            create_ledger_entry(
                tenant_id=self.tenant_id,
                item_id=po_item.item_id,
                transaction_type='PURCHASE',
                quantity=po_item.ordered_quantity,
                location_id=self.loc_a.id,
                unit_cost=po_item.unit_price,
                total_cost=po_item.unit_price * po_item.ordered_quantity,
                reference_type='PURCHASE_ORDER',
                reference_id=str(self.po.id),
                created_by=None,
            )

        # Also create an opening balance for a few items
        for item in self.items[:3]:
            create_ledger_entry(
                tenant_id=self.tenant_id,
                item_id=item.id,
                transaction_type='OPENING',
                quantity=Decimal('100'),
                location_id=self.loc_a.id,
                unit_cost=item.cost_price,
                total_cost=Decimal('100') * (item.cost_price or Decimal('0')),
                reference_type='OPENING',
                reference_id='',
                created_by=None,
            )

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    def _seed_transfer(self):
        self.stdout.write('  Creating transfer...')

        today = timezone.now().date()
        transfer = InventoryTransfer.objects.create(
            tenant_id=self.tenant_id,
            transfer_number='TRF-2024-0001',
            transfer_date=today - timedelta(days=5),
            source_location=self.loc_a,
            destination_location=self.loc_b,
            transfer_type='STANDARD',
            status='COMPLETED',
        )

        items_data = [
            dict(item=self.items[0], quantity=Decimal('3')),
            dict(item=self.items[1], quantity=Decimal('10')),
        ]
        for d in items_data:
            InventoryTransferItem.objects.create(transfer=transfer, **d)
            create_ledger_entry(
                tenant_id=self.tenant_id,
                item_id=d['item'].id,
                transaction_type='TRANSFER_OUT',
                quantity=-d['quantity'],
                location_id=self.loc_a.id,
                reference_type='TRANSFER',
                reference_id=str(transfer.id),
                created_by=None,
            )
            create_ledger_entry(
                tenant_id=self.tenant_id,
                item_id=d['item'].id,
                transaction_type='TRANSFER_IN',
                quantity=d['quantity'],
                location_id=self.loc_b.id,
                reference_type='TRANSFER',
                reference_id=str(transfer.id),
                created_by=None,
            )

    # ------------------------------------------------------------------
    # Adjustment
    # ------------------------------------------------------------------

    def _seed_adjustment(self):
        self.stdout.write('  Creating adjustment...')

        today = timezone.now().date()
        adj = InventoryAdjustment.objects.create(
            tenant_id=self.tenant_id,
            adjustment_number='ADJ-2024-0001',
            adjustment_date=today - timedelta(days=3),
            location=self.loc_a,
            adjustment_type='DECREASE',
            reason=self.adj_reason,
            status='APPLIED',
        )

        adj_items_data = [
            dict(item=self.items[2], adjustment_quantity=Decimal('-5')),
        ]
        for d in adj_items_data:
            InventoryAdjustmentItem.objects.create(adjustment=adj, **d)
            create_ledger_entry(
                tenant_id=self.tenant_id,
                item_id=d['item'].id,
                transaction_type='ADJUSTMENT_OUT',
                quantity=d['adjustment_quantity'],
                location_id=self.loc_a.id,
                reference_type='ADJUSTMENT',
                reference_id=str(adj.id),
                created_by=None,
            )

    # ------------------------------------------------------------------
    # Reservation
    # ------------------------------------------------------------------

    def _seed_reservation(self):
        self.stdout.write('  Creating reservation...')

        today = timezone.now().date()
        reserve = InventoryReservation.objects.create(
            tenant_id=self.tenant_id,
            reservation_number='RSV-2024-0001',
            reservation_date=today - timedelta(days=7),
            expiry_date=today + timedelta(days=23),
            source_location=self.loc_a,
            reservation_type='SALES_ORDER',
            status='ACTIVE',
            customer_name='Big Customer Corp',
            priority='HIGH',
            reason=self.resv_reason,
        )

        res_items_data = [
            dict(item=self.items[1], requested_quantity=Decimal('20'),
                 reserved_quantity=Decimal('20')),
            dict(item=self.items[0], requested_quantity=Decimal('2'),
                 reserved_quantity=Decimal('2')),
        ]
        for d in res_items_data:
            InventoryReservationItem.objects.create(reservation=reserve, **d)
            create_ledger_entry(
                tenant_id=self.tenant_id,
                item_id=d['item'].id,
                transaction_type='RESERVATION',
                quantity=d['reserved_quantity'],
                location_id=self.loc_a.id,
                reference_type='RESERVATION',
                reference_id=str(reserve.id),
                created_by=None,
            )

    # ------------------------------------------------------------------
    # Stock Count
    # ------------------------------------------------------------------

    def _seed_stock_count(self):
        self.stdout.write('  Creating stock count...')

        today = timezone.now().date()
        sc = InventoryStockCount.objects.create(
            tenant_id=self.tenant_id,
            count_number='CNT-2024-0001',
            count_date=today - timedelta(days=2),
            count_type='CYCLE',
            location=self.loc_a,
            reason=self.sc_reason,
            status='COMPLETED',
        )
        for item in self.items[:4]:
            InventoryStockCountItem.objects.create(
                count=sc, item=item,
                expected_quantity=Decimal('100'),
                counted_quantity=Decimal('98'),
                difference_quantity=Decimal('-2'),
            )

    # ------------------------------------------------------------------
    # Invoice + Return + Payment
    # ------------------------------------------------------------------

    def _seed_invoice_and_return_and_payment(self):
        self.stdout.write('  Creating invoice, return & payment...')

        today = timezone.now().date()

        invoice = InventorySupplierInvoice.objects.create(
            tenant_id=self.tenant_id,
            invoice_number='INV-2024-0001',
            invoice_date=today - timedelta(days=8),
            due_date=today + timedelta(days=22),
            supplier_name='TechDistributor Inc.',
            purchase_order=self.po,
            status='PAID',
            payment_status='PAID',
            subtotal=Decimal('325000'),
            tax_amount=Decimal('58500'),
            grand_total=Decimal('383500'),
            outstanding_amount=Decimal('0'),
        )

        # Invoice items
        invoice_items_data = [
            dict(item=self.items[0], quantity=Decimal('10'), unit_price=Decimal('75000'),
                 line_total=Decimal('750000')),
            dict(item=self.items[1], quantity=Decimal('50'), unit_price=Decimal('500'),
                 line_total=Decimal('25000')),
        ]
        for d in invoice_items_data:
            InventorySupplierInvoiceItem.objects.create(invoice=invoice, **d)

        invoice.goods_receipts.add(self.grn)

        # Purchase Return
        pret = InventoryPurchaseReturn.objects.create(
            tenant_id=self.tenant_id,
            return_number='RET-2024-0001',
            return_date=today - timedelta(days=1),
            supplier_name='TechDistributor Inc.',
            purchase_order=self.po,
            goods_receipt=self.grn,
            supplier_invoice=invoice,
            return_reason='Defective items',
            status='COMPLETED',
            subtotal=Decimal('1000'),
            tax_amount=Decimal('180'),
            total_amount=Decimal('1180'),
        )
        InventoryPurchaseReturnItem.objects.create(
            purchase_return=pret, item=self.items[1],
            return_quantity=Decimal('2'), unit_cost=Decimal('500'),
            total_amount=Decimal('1000'),
        )

        # Supplier Payment
        payment = InventorySupplierPayment.objects.create(
            tenant_id=self.tenant_id,
            payment_number='PAY-2024-0001',
            payment_date=today,
            supplier_name='TechDistributor Inc.',
            payment_method='Bank Transfer',
            currency='INR',
            total_amount=Decimal('383500'),
            allocated_amount=Decimal('383500'),
            unallocated_amount=Decimal('0'),
            status='COMPLETED',
        )
        InventorySupplierPaymentAllocation.objects.create(
            payment=payment, supplier_invoice=invoice,
            allocated_amount=Decimal('383500'),
        )
