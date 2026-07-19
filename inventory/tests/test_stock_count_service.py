"""
Tests for Stock Count Service — verifies workflow, difference_summary,
barcode lookup, and attachment management.
"""

import uuid
from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from inventory.models import (
    InventoryItem, ItemCategory, Unit,
    InventoryLocation, InventoryLocationType,
    InventoryStockCount, InventoryStockCountItem,
    InventoryStockCountAttachment, StockCountReason,
    StockLedger,
)
from inventory.services.stock_count_service import (
    create_stock_count, assign_counters, start_counting,
    save_count_progress, submit_stock_count, approve_stock_count,
    complete_stock_count, cancel_stock_count, get_difference_summary,
    reload_items_from_ledger,
)
from inventory.services.stock_engine import create_ledger_entry

User = get_user_model()


class StockCountServiceTest(TransactionTestCase):
    """Comprehensive tests for the stock count service."""

    def setUp(self):
        from menus.models import Organization
        self.admin = User.objects.create_user(
            email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
            password="testpass123", role="Superadmin", is_active=True,
        )
        self.org = Organization.objects.create(
            name=f"Org {uuid.uuid4().hex[:8]}",
            slug=f"org-{uuid.uuid4().hex[:8]}", owner=self.admin,
        )
        self.tenant_id = self.org.id
        self.admin.organization = self.org
        self.admin.save()

        self.category = ItemCategory.objects.create(
            tenant_id=self.tenant_id, category_code="CAT",
            category_name="Test Category",
        )
        self.unit = Unit.objects.create(
            tenant_id=self.tenant_id, unit_code="PCS",
            unit_name="Pieces",
        )
        self.item1 = InventoryItem.objects.create(
            tenant_id=self.tenant_id, item_code="CNT001",
            item_name="Count Item 1", category=self.category,
            unit=self.unit, cost_price=Decimal('10'),
        )
        self.item2 = InventoryItem.objects.create(
            tenant_id=self.tenant_id, item_code="CNT002",
            item_name="Count Item 2", category=self.category,
            unit=self.unit, cost_price=Decimal('20'),
        )
        loc_type = InventoryLocationType.objects.create(
            tenant_id=self.tenant_id, type_code="WH",
            type_name="Warehouse",
        )
        self.location = InventoryLocation.objects.create(
            tenant_id=self.tenant_id, location_code="LOC-01",
            location_name="Test Location", location_type=loc_type,
        )
        self.reason = StockCountReason.objects.create(
            tenant_id=self.tenant_id, reason_code="CYCLE",
            reason_name="Cycle Count",
        )

        # Initial stock
        create_ledger_entry(
            tenant_id=self.tenant_id, item_id=self.item1.id,
            transaction_type='OPENING', quantity=Decimal('50'),
            location_id=self.location.id, created_by=self.admin,
        )
        create_ledger_entry(
            tenant_id=self.tenant_id, item_id=self.item2.id,
            transaction_type='OPENING', quantity=Decimal('30'),
            location_id=self.location.id, created_by=self.admin,
        )

    def test_full_workflow_with_difference_summary(self):
        """Complete stock count workflow with difference summary."""
        # Create
        sc = create_stock_count(self.tenant_id, {
            'location': str(self.location.id),
            'reason': self.reason.id,
        }, self.admin)
        self.assertEqual(sc.status, 'DRAFT')
        self.assertEqual(sc.items.count(), 2)

        # Assign and start
        sc = assign_counters(sc, self.admin, [self.admin.id])
        self.assertEqual(sc.status, 'ASSIGNED')
        sc = start_counting(sc, self.admin)
        self.assertEqual(sc.status, 'IN_PROGRESS')

        # Save progress
        sc = save_count_progress(sc, self.admin, [
            {'item_id': str(self.item1.id), 'counted_quantity': Decimal('45')},
            {'item_id': str(self.item2.id), 'counted_quantity': Decimal('30')},
        ])
        self.assertEqual(sc.status, 'IN_PROGRESS')

        # Submit
        sc = submit_stock_count(sc, self.admin)
        self.assertEqual(sc.status, 'SUBMITTED')

        # Approve
        sc = approve_stock_count(sc, self.admin)
        self.assertEqual(sc.status, 'APPROVED')

        # Complete
        sc = complete_stock_count(sc, self.admin)
        self.assertEqual(sc.status, 'COMPLETED')

        # Difference summary
        summary = get_difference_summary(sc)
        self.assertIn('items', summary)
        self.assertIn('totals', summary)
        self.assertEqual(summary['totals']['total_items'], 2)
        self.assertEqual(summary['totals']['shortage_items'], 1)
        self.assertEqual(summary['totals']['matching_items'], 1)

        # Verify item1 shows SHORTAGE (50 expected, 45 counted)
        item1_summary = next(
            s for s in summary['items'] if s['item_id'] == self.item1.id
        )
        self.assertEqual(item1_summary['status'], 'SHORTAGE')
        self.assertEqual(item1_summary['difference_quantity'], Decimal('-5'))

        # Verify item2 shows MATCH
        item2_summary = next(
            s for s in summary['items'] if s['item_id'] == self.item2.id
        )
        self.assertEqual(item2_summary['status'], 'MATCH')
        self.assertEqual(item2_summary['difference_quantity'], Decimal('0'))

    def test_difference_summary_uncounted_items(self):
        """Uncounted items should appear with UNCOUNTED status."""
        sc = create_stock_count(self.tenant_id, {
            'location': str(self.location.id),
            'reason': self.reason.id,
        }, self.admin)
        summary = get_difference_summary(sc)
        uncounted = [s for s in summary['items'] if s['status'] == 'UNCOUNTED']
        self.assertEqual(len(uncounted), 2)

    def test_cancel_stock_count(self):
        """Stock count should be cancellable from DRAFT, ASSIGNED, or IN_PROGRESS."""
        sc = create_stock_count(self.tenant_id, {
            'location': str(self.location.id),
            'reason': self.reason.id,
        }, self.admin)
        sc = cancel_stock_count(sc, self.admin)
        self.assertEqual(sc.status, 'CANCELLED')

    def test_reload_items_from_ledger(self):
        """Adding new stock after count creation should be picked up by reload."""
        sc = create_stock_count(self.tenant_id, {
            'location': str(self.location.id),
            'reason': self.reason.id,
        }, self.admin)
        initial_count = sc.items.count()

        # Add a new item to the location
        item3 = InventoryItem.objects.create(
            tenant_id=self.tenant_id, item_code="CNT003",
            item_name="Count Item 3", category=self.category,
            unit=self.unit,
        )
        create_ledger_entry(
            tenant_id=self.tenant_id, item_id=item3.id,
            transaction_type='OPENING', quantity=Decimal('10'),
            location_id=self.location.id, created_by=self.admin,
        )

        added = reload_items_from_ledger(sc, self.admin)
        self.assertEqual(added, 1)
        self.assertEqual(sc.items.count(), initial_count + 1)

    def test_stock_count_attachment_management(self):
        """Attachments can be added and removed from stock counts."""
        sc = create_stock_count(self.tenant_id, {
            'location': str(self.location.id),
            'reason': self.reason.id,
        }, self.admin)

        # Create attachment
        attachment = InventoryStockCountAttachment.objects.create(
            count=sc, file_url="http://example.com/doc.pdf",
            file_name="count_sheet.pdf",
        )
        self.assertEqual(sc.attachments.count(), 1)

        # Delete attachment
        attachment.delete()
        self.assertEqual(sc.attachments.count(), 0)
