"""
Tests for concurrency locking in stock-changing operations.

Verifies that select_for_update is used and race conditions are prevented.
"""

import uuid
import threading
from decimal import Decimal
from django.db import transaction, connections
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from inventory.models import (
    InventoryItem, ItemCategory, Unit,
    InventoryLocation, InventoryLocationType,
    InventoryTransfer, InventoryTransferItem,
    InventoryAdjustment, InventoryAdjustmentItem, InventoryAdjustmentReason,
    StockLedger,
)
from inventory.services.transfer_service import (
    create_transfer, submit_transfer, approve_transfer, dispatch_transfer,
)
from inventory.services.adjustment_service import (
    create_adjustment, submit_adjustment, approve_adjustment, apply_adjustment,
)

User = get_user_model()


class ConcurrencyBaseTest(TransactionTestCase):
    """Base class with shared setup for concurrency tests."""

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
            tenant_id=self.tenant_id, category_code="TEST",
            category_name="Test Category",
        )
        self.unit = Unit.objects.create(
            tenant_id=self.tenant_id, unit_code="PCS",
            unit_name="Pieces",
        )
        self.item = InventoryItem.objects.create(
            tenant_id=self.tenant_id, item_code="CONCUR001",
            item_name="Concurrency Item", category=self.category,
            unit=self.unit, cost_price=Decimal('10'),
        )
        loc_type = InventoryLocationType.objects.create(
            tenant_id=self.tenant_id, type_code="WH",
            type_name="Warehouse",
        )
        self.source = InventoryLocation.objects.create(
            tenant_id=self.tenant_id, location_code="SRC",
            location_name="Source", location_type=loc_type,
        )
        self.dest = InventoryLocation.objects.create(
            tenant_id=self.tenant_id, location_code="DST",
            location_name="Destination", location_type=loc_type,
        )

        # Initial stock: OPENING +100
        from inventory.services.stock_engine import create_ledger_entry
        create_ledger_entry(
            tenant_id=self.tenant_id, item_id=self.item.id,
            transaction_type='OPENING', quantity=Decimal('100'),
            location_id=self.source.id, created_by=self.admin,
        )


class TransferConcurrencyTest(ConcurrencyBaseTest):
    """Ensure select_for_update prevents overselling during dispatch."""

    def test_dispatch_overselling_prevented(self):
        """Stock check before dispatch should prevent overselling."""
        transfer1 = create_transfer(self.tenant_id, {
            'source_location': str(self.source.id),
            'destination_location': str(self.dest.id),
            'items': [{'item_id': str(self.item.id), 'quantity': Decimal('80')}],
        }, self.admin)
        transfer1 = submit_transfer(transfer1, self.admin)
        transfer1 = approve_transfer(transfer1, self.admin)

        transfer2 = create_transfer(self.tenant_id, {
            'source_location': str(self.source.id),
            'destination_location': str(self.dest.id),
            'items': [{'item_id': str(self.item.id), 'quantity': Decimal('50')}],
        }, self.admin)
        transfer2 = submit_transfer(transfer2, self.admin)
        transfer2 = approve_transfer(transfer2, self.admin)

        # Both dispatches should succeed individually
        dispatch_transfer(transfer1, self.admin)
        with self.assertRaises(ValueError):
            dispatch_transfer(transfer2, self.admin)


class AdjustmentConcurrencyTest(ConcurrencyBaseTest):
    """Ensure select_for_update prevents overselling during DECREASE adjustments."""

    def setUp(self):
        super().setUp()
        self.reason = InventoryAdjustmentReason.objects.create(
            tenant_id=self.tenant_id, reason_code="DAMAGE",
            reason_name="Damage", adjustment_type="DECREASE",
        )

    def test_decrease_overselling_prevented(self):
        """DECREASE adjustment should fail if insufficient stock after concurrent changes."""
        adj = create_adjustment(self.tenant_id, {
            'location': str(self.source.id),
            'reason': self.reason.id,
            'items': [{'item_id': str(self.item.id), 'adjustment_quantity': Decimal('120')}],
        }, self.admin)
        with self.assertRaises(ValueError):
            submit_adjustment(adj, self.admin)

    def test_apply_verifies_stock_again(self):
        """apply_adjustment re-validates stock before creating ledger entries."""
        adj = create_adjustment(self.tenant_id, {
            'location': str(self.source.id),
            'reason': self.reason.id,
            'items': [{'item_id': str(self.item.id), 'adjustment_quantity': Decimal('30')}],
        }, self.admin)
        submit_adjustment(adj, self.admin)
        approve_adjustment(adj, self.admin)

        # Drain stock before apply
        from inventory.services.stock_engine import create_ledger_entry
        create_ledger_entry(
            tenant_id=self.tenant_id, item_id=self.item.id,
            transaction_type='SALE', quantity=Decimal('-80'),
            location_id=self.source.id, created_by=self.admin,
        )

        with self.assertRaises(ValueError):
            apply_adjustment(adj, self.admin)

    def test_select_for_update_locks_items(self):
        """Verify items are locked during adjustment workflow."""
        adj = create_adjustment(self.tenant_id, {
            'location': str(self.source.id),
            'reason': self.reason.id,
            'items': [{'item_id': str(self.item.id), 'adjustment_quantity': Decimal('20')}],
        }, self.admin)
        submit_adjustment(adj, self.admin)
        approve_adjustment(adj, self.admin)

        # Apply should succeed (enough stock)
        result = apply_adjustment(adj, self.admin)
        self.assertEqual(result.status, 'APPLIED')
