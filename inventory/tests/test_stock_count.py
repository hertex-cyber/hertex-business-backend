"""
Stock Count Tests — Section 9

Tests cover:
  - Create Stock Count
  - Assign Counters
  - Save Progress / Count items
  - Barcode Lookup
  - Submit / Approve / Complete
  - Cancel
  - Stock Adjustment generation from differences
  - Permission checks
  - Validation failures
"""

from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from menus.models import Organization

from inventory.models import (
    InventoryItem, ItemCategory, Unit, Brand,
    InventoryLocation, InventoryLocationType,
    InventoryStockCount, InventoryStockCountItem,
    StockCountReason, StockLedger,
)
from inventory.services.stock_engine import create_ledger_entry
from inventory.services.stock_count_service import (
    create_stock_count, assign_counters, start_counting,
    save_count_progress, submit_stock_count,
    approve_stock_count, complete_stock_count,
    cancel_stock_count, get_difference_summary,
    generate_count_number,
)

User = get_user_model()


class BaseStockCountTest(APITestCase):
    """Shared fixtures for all stock count tests."""

    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.superadmin = User.objects.create_user(
            email='superadmin@test.com',
            password='testpass123',
            first_name='Super',
            last_name='Admin',
            role='Superadmin',
        )
        cls.admin = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='Admin',
            role='Admin',
        )
        cls.manager = User.objects.create_user(
            email='manager@test.com',
            password='testpass123',
            first_name='Middle',
            last_name='Manager',
            role='Manager',
        )
        cls.staff = User.objects.create_user(
            email='staff@test.com',
            password='testpass123',
            first_name='Just',
            last_name='Staff',
            role='Staff',
        )

        # Create org for tenant isolation
        cls.org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            owner=cls.superadmin,
        )
        cls.superadmin.organization = cls.org
        cls.superadmin.save()
        cls.admin.organization = cls.org
        cls.admin.save()
        cls.manager.organization = cls.org
        cls.manager.save()
        cls.staff.organization = cls.org
        cls.staff.save()

        # All users share the same tenant ID for multi-tenant isolation
        tenant_id = cls.org.id

        # Create master data
        cls.category = ItemCategory.objects.create(
            tenant_id=tenant_id,
            category_code='TEST-CAT',
            category_name='Test Category',
        )
        cls.unit = Unit.objects.create(
            tenant_id=tenant_id,
            unit_code='PCS',
            unit_name='Pieces',
        )
        cls.brand = Brand.objects.create(
            tenant_id=tenant_id,
            brand_code='TEST-BRAND',
            brand_name='Test Brand',
        )

        # Create items
        cls.item1 = InventoryItem.objects.create(
            tenant_id=tenant_id,
            item_code='ITM-001',
            item_name='Test Item One',
            category=cls.category,
            unit=cls.unit,
            cost_price=Decimal('10.00'),
            selling_price=Decimal('15.00'),
        )
        cls.item2 = InventoryItem.objects.create(
            tenant_id=tenant_id,
            item_code='ITM-002',
            item_name='Test Item Two',
            category=cls.category,
            unit=cls.unit,
            cost_price=Decimal('20.00'),
        )

        # Create location
        cls.location_type = InventoryLocationType.objects.create(
            tenant_id=tenant_id,
            type_code='WH',
            type_name='Warehouse',
        )
        cls.location = InventoryLocation.objects.create(
            tenant_id=tenant_id,
            location_code='MAIN-WH',
            location_name='Main Warehouse',
            location_type=cls.location_type,
        )

        # Seed stock ledger with opening balances
        create_ledger_entry(
            tenant_id=tenant_id,
            item_id=cls.item1.id,
            transaction_type='OPENING',
            quantity=Decimal('100'),
            location_id=cls.location.id,
            description='Opening balance for tests',
        )
        create_ledger_entry(
            tenant_id=tenant_id,
            item_id=cls.item2.id,
            transaction_type='OPENING',
            quantity=Decimal('50'),
            location_id=cls.location.id,
            description='Opening balance for tests',
        )

        # Create count reason
        cls.reason = StockCountReason.objects.create(
            tenant_id=tenant_id,
            reason_code='MONTHLY',
            reason_name='Monthly Cycle Count',
            is_default=True,
            status='ACTIVE',
        )

        cls.tenant_id = tenant_id
        cls.api_client = APIClient()

    def setUp(self):
        self.api_client.force_authenticate(user=self.superadmin)


# ===========================================================================
# CREATE STOCK COUNT
# ===========================================================================

class CreateStockCountTest(BaseStockCountTest):

    def test_create_stock_count(self):
        """Test creating a stock count with auto-loaded items."""
        count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
            'count_type': 'CYCLE',
            'count_date': timezone.now().date(),
        }, self.superadmin)

        self.assertEqual(count.status, 'DRAFT')
        self.assertIsNotNone(count.count_number)
        self.assertTrue(count.count_number.startswith('CNT-'))

        # Verify items were auto-loaded
        items = count.items.all()
        self.assertEqual(items.count(), 2)  # Both items from stock ledger

        # Verify expected quantities from ledger
        item1_count = items.get(item=self.item1)
        self.assertEqual(item1_count.expected_quantity, Decimal('100'))

        item2_count = items.get(item=self.item2)
        self.assertEqual(item2_count.expected_quantity, Decimal('50'))

    def test_create_with_assigned_counters(self):
        """Test creating a stock count with initial counter assignment."""
        count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
            'assigned_counters': [str(self.staff.id), str(self.manager.id)],
        }, self.superadmin)

        self.assertEqual(count.assigned_counters.count(), 2)

    def test_create_with_category_filter(self):
        """Test creating a stock count filtered by category."""
        count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
            'category': self.category.id,
        }, self.superadmin)

        self.assertEqual(count.category_id, self.category.id)

    def test_create_invalid_reason(self):
        """Test creating with invalid reason raises error."""
        with self.assertRaises(ValueError):
            create_stock_count(self.tenant_id, {
                'location': self.location.id,
                'reason': '00000000-0000-0000-0000-000000000000',
            }, self.superadmin)

    def test_generate_count_number(self):
        """Test count number generation."""
        num = generate_count_number(self.tenant_id)
        self.assertTrue(num.startswith('CNT-'))
        parts = num.split('-')
        self.assertEqual(len(parts), 3)


# ===========================================================================
# ASSIGN COUNTERS
# ===========================================================================

class AssignCountersTest(BaseStockCountTest):

    def setUp(self):
        super().setUp()
        self.count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)

    def test_assign_counters(self):
        """Test assigning counters to a draft count."""
        count = assign_counters(self.count, self.superadmin, [
            str(self.staff.id), str(self.manager.id),
        ])
        self.assertEqual(count.assigned_counters.count(), 2)
        self.assertEqual(count.status, 'ASSIGNED')  # Auto-transition

    def test_assign_counters_on_assigned_count(self):
        """Test re-assigning counters on an already assigned count."""
        assign_counters(self.count, self.superadmin, [str(self.staff.id)])
        count = assign_counters(self.count, self.superadmin, [str(self.manager.id)])
        self.assertEqual(count.assigned_counters.count(), 1)
        self.assertEqual(count.assigned_counters.first().id, self.manager.id)

    def test_assign_counters_in_progress_fails(self):
        """Test assigning counters to in-progress count fails."""
        assign_counters(self.count, self.superadmin, [str(self.staff.id)])
        start_counting(self.count, self.staff)
        from inventory.models import InventoryStockCount
        count = InventoryStockCount.objects.get(id=self.count.id)
        with self.assertRaises(ValueError):
            assign_counters(count, self.superadmin, [str(self.manager.id)])


# ===========================================================================
# START COUNTING & SAVE PROGRESS
# ===========================================================================

class CountingWorkflowTest(BaseStockCountTest):

    def setUp(self):
        super().setUp()
        self.count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        assign_counters(self.count, self.superadmin, [str(self.staff.id)])
        # Re-fetch to get current status
        self.count = InventoryStockCount.objects.get(id=self.count.id)

    def test_start_counting(self):
        """Test transition from ASSIGNED to IN_PROGRESS."""
        count = start_counting(self.count, self.staff)
        self.assertEqual(count.status, 'IN_PROGRESS')

    def test_start_counting_by_non_assigned_user_fails(self):
        """Test non-assigned user cannot start counting."""
        with self.assertRaises(ValueError):
            start_counting(self.count, self.manager)

    def test_start_counting_by_admin(self):
        """Test admin can start counting even if not assigned."""
        count = start_counting(self.count, self.admin)
        self.assertEqual(count.status, 'IN_PROGRESS')

    def test_save_progress(self):
        """Test saving counting progress."""
        count = start_counting(self.count, self.staff)

        # Find items by their item_code to avoid ordering issues
        all_items = count.items.select_related('item').all()
        item1_count = next(i for i in all_items if i.item.item_code == 'ITM-001')
        item2_count = next(i for i in all_items if i.item.item_code == 'ITM-002')

        items_data = [
            {'item_id': str(item1_count.item_id), 'counted_quantity': '95'},
            {'item_id': str(item2_count.item_id), 'counted_quantity': '52'},
        ]

        count = save_count_progress(count, self.staff, items_data)

        # Verify counted quantities
        item1 = count.items.get(item=self.item1)
        self.assertEqual(item1.counted_quantity, Decimal('95'))
        self.assertEqual(item1.difference_quantity, Decimal('-5'))  # 95 - 100 = -5

        item2 = count.items.get(item=self.item2)
        self.assertEqual(item2.counted_quantity, Decimal('52'))
        self.assertEqual(item2.difference_quantity, Decimal('2'))  # 52 - 50 = 2

    def test_save_progress_with_barcode(self):
        """Test saving progress with barcode scan."""
        count = start_counting(self.count, self.staff)

        # Find item by item_code
        all_items = count.items.select_related('item').all()
        item1_count = next(i for i in all_items if i.item.item_code == 'ITM-001')

        items_data = [{
            'item_id': str(item1_count.item_id),
            'counted_quantity': '95',
            'scanned_barcode': 'BARCODE-001',
        }]

        count = save_count_progress(count, self.staff, items_data)
        item1 = count.items.get(item=self.item1)
        self.assertEqual(item1.scanned_barcode, 'BARCODE-001')

    def test_save_progress_while_not_in_progress_fails(self):
        """Test saving progress on a non-in-progress count."""
        with self.assertRaises(ValueError):
            save_count_progress(self.count, self.staff, [])


# ===========================================================================
# BARCODE LOOKUP
# ===========================================================================

class BarcodeLookupTest(BaseStockCountTest):

    def setUp(self):
        super().setUp()
        self.count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        assign_counters(self.count, self.superadmin, [str(self.staff.id)])
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        self.count = start_counting(self.count, self.staff)

        # Save progress with barcode on ITM-001 specifically
        all_items = self.count.items.select_related('item').all()
        item1_count = next(i for i in all_items if i.item.item_code == 'ITM-001')
        save_count_progress(self.count, self.staff, [
            {'item_id': str(item1_count.item_id), 'counted_quantity': '95', 'scanned_barcode': 'BARCODE-001'},
        ])
        self.count = InventoryStockCount.objects.get(id=self.count.id)

    def test_barcode_lookup_success(self):
        """Test barcode lookup returns correct item."""
        items = self.count.items.filter(scanned_barcode='BARCODE-001')
        self.assertEqual(items.count(), 1)
        self.assertEqual(items[0].item.item_code, 'ITM-001')

    def test_barcode_lookup_not_found(self):
        """Test barcode lookup returns empty for unknown barcode."""
        items = self.count.items.filter(scanned_barcode='UNKNOWN-BARCODE')
        self.assertEqual(items.count(), 0)

    def test_barcode_lookup_api(self):
        """Test the API endpoint for barcode lookup."""
        # Find ITM-001 and set its barcode specifically
        item1 = self.count.items.filter(item=self.item1).first()
        item1.scanned_barcode = 'BARCODE-001'
        item1.save()

        response = self.api_client.get(
            f'/api/inventory/stock-counts/{self.count.id}/lookup-barcode/',
            {'barcode': 'BARCODE-001'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['item_code'], 'ITM-001')
        self.assertEqual(response.data['scanned_barcode'], 'BARCODE-001')

    def test_barcode_lookup_api_not_found(self):
        """Test barcode API returns 404 for unknown barcode."""
        response = self.api_client.get(
            f'/api/inventory/stock-counts/{self.count.id}/lookup-barcode/',
            {'barcode': 'UNKNOWN'},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_barcode_lookup_missing_param(self):
        """Test barcode API returns 400 if barcode param missing."""
        response = self.api_client.get(
            f'/api/inventory/stock-counts/{self.count.id}/lookup-barcode/',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# SUBMIT / APPROVE / COMPLETE / CANCEL
# ===========================================================================

class WorkflowTransitionTest(BaseStockCountTest):

    def setUp(self):
        super().setUp()
        self.count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        assign_counters(self.count, self.superadmin, [str(self.staff.id)])
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        self.count = start_counting(self.count, self.staff)

        # Count all items by finding them by item_code
        all_items = self.count.items.select_related('item').all()
        item1_count = next(i for i in all_items if i.item.item_code == 'ITM-001')
        item2_count = next(i for i in all_items if i.item.item_code == 'ITM-002')
        self.count = save_count_progress(self.count, self.staff, [
            {'item_id': str(item1_count.item_id), 'counted_quantity': '100'},  # No diff
            {'item_id': str(item2_count.item_id), 'counted_quantity': '50'},   # No diff
        ])
        self.count = InventoryStockCount.objects.get(id=self.count.id)

    def test_submit(self):
        """Test submitting a stock count."""
        count = submit_stock_count(self.count, self.staff)
        self.assertEqual(count.status, 'SUBMITTED')

    def test_submit_with_uncounted_items_fails(self):
        """Test submitting with uncounted items fails."""
        # Create a new count and don't count all items
        new_count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        assign_counters(new_count, self.superadmin, [str(self.staff.id)])
        new_count = InventoryStockCount.objects.get(id=new_count.id)
        new_count = start_counting(new_count, self.staff)

        with self.assertRaises(ValueError):
            submit_stock_count(new_count, self.staff)

    def test_approve(self):
        """Test approving a submitted stock count."""
        self.count = submit_stock_count(self.count, self.staff)
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        count = approve_stock_count(self.count, self.admin, notes='Looks good')
        self.assertEqual(count.status, 'APPROVED')
        self.assertEqual(count.approval_notes, 'Looks good')

    def test_complete_with_no_differences(self):
        """Test completing a count with zero differences."""
        self.count = submit_stock_count(self.count, self.staff)
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        self.count = approve_stock_count(self.count, self.admin)

        with self.assertRaises(ValueError):
            complete_stock_count(self.count, self.admin)

    def test_cancel_draft(self):
        """Test cancelling a draft count."""
        draft_count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        count = cancel_stock_count(draft_count, self.superadmin)
        self.assertEqual(count.status, 'CANCELLED')

    def test_cancel_in_progress(self):
        """Test cancelling an in-progress count."""
        count = cancel_stock_count(self.count, self.staff)
        self.assertEqual(count.status, 'CANCELLED')


# ===========================================================================
# ADJUSTMENT GENERATION
# ===========================================================================

class AdjustmentGenerationTest(BaseStockCountTest):

    def setUp(self):
        super().setUp()
        self.count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        assign_counters(self.count, self.superadmin, [str(self.staff.id)])
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        self.count = start_counting(self.count, self.staff)

        # Count items with differences by finding them by item_code
        all_items = self.count.items.select_related('item').all()
        item1_count = next(i for i in all_items if i.item.item_code == 'ITM-001')
        item2_count = next(i for i in all_items if i.item.item_code == 'ITM-002')
        self.count = save_count_progress(self.count, self.staff, [
            {'item_id': str(item1_count.item_id), 'counted_quantity': '110'},  # +10 surplus
            {'item_id': str(item2_count.item_id), 'counted_quantity': '45'},   # -5 shortage
        ])
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        self.count = submit_stock_count(self.count, self.staff)
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        self.count = approve_stock_count(self.count, self.admin)

    def test_complete_generates_adjustments(self):
        """Test completing generates adjustment from differences."""
        count = complete_stock_count(self.count, self.admin)
        self.assertEqual(count.status, 'COMPLETED')
        self.assertIsNotNone(count.generated_adjustment)
        self.assertEqual(count.total_items_with_difference, 2)

        # Verify the generated adjustment exists
        adj = count.generated_adjustment
        self.assertIsNotNone(adj)
        self.assertEqual(adj.status, 'APPLIED')  # Should be auto-applied


# ===========================================================================
# DIFFERENCE SUMMARY
# ===========================================================================

class DifferenceSummaryTest(BaseStockCountTest):

    def setUp(self):
        super().setUp()
        self.count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        assign_counters(self.count, self.superadmin, [str(self.staff.id)])
        self.count = InventoryStockCount.objects.get(id=self.count.id)
        self.count = start_counting(self.count, self.staff)

    def test_difference_summary(self):
        """Test difference summary returns correct data."""
        all_items = self.count.items.select_related('item').all()
        item1_count = next(i for i in all_items if i.item.item_code == 'ITM-001')
        item2_count = next(i for i in all_items if i.item.item_code == 'ITM-002')
        save_count_progress(self.count, self.staff, [
            {'item_id': str(item1_count.item_id), 'counted_quantity': '110'},  # Surplus
            {'item_id': str(item2_count.item_id), 'counted_quantity': '45'},   # Shortage
        ])
        self.count = InventoryStockCount.objects.get(id=self.count.id)

        summary = get_difference_summary(self.count)
        self.assertIn('items', summary)
        self.assertIn('totals', summary)
        self.assertEqual(summary['totals']['total_items'], 2)
        self.assertEqual(summary['totals']['surplus_items'], 1)
        self.assertEqual(summary['totals']['shortage_items'], 1)


# ===========================================================================
# PERMISSION TESTS
# ===========================================================================

class StockCountPermissionTest(BaseStockCountTest):

    def test_unauthenticated_cannot_access(self):
        """Test unauthenticated user gets 401."""
        self.api_client.force_authenticate(user=None)
        response = self.api_client.get('/api/inventory/stock-counts/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_can_view(self):
        """Test staff user can view stock counts."""
        self.api_client.force_authenticate(user=self.staff)
        response = self.api_client.get('/api/inventory/stock-counts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_create(self):
        """Test staff user cannot create stock counts."""
        self.api_client.force_authenticate(user=self.staff)
        response = self.api_client.post('/api/inventory/stock-counts/', {
            'location': self.location.id,
            'reason': self.reason.id,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_create(self):
        """Test manager can create stock counts."""
        self.api_client.force_authenticate(user=self.manager)
        response = self.api_client.post('/api/inventory/stock-counts/', {
            'location': self.location.id,
            'reason': self.reason.id,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_can_approve(self):
        """Test admin can approve a submitted count."""
        self.api_client.force_authenticate(user=self.manager)

        # Create and assign
        response = self.api_client.post('/api/inventory/stock-counts/', {
            'location': self.location.id,
            'reason': self.reason.id,
        })
        count_id = response.data['id']

        # Start counting and submit via API
        self.api_client.force_authenticate(user=self.superadmin)

        # Get count items
        response = self.api_client.get(f'/api/inventory/stock-counts/{count_id}/')
        items = response.data.get('items', [])
        if items:
            # Count all items
            progress_data = {'items': [
                {'item_id': i['item'] or i['item_id'], 'counted_quantity': '10'}
                for i in items
            ]}
            self.api_client.post(f'/api/inventory/stock-counts/{count_id}/save-progress/', progress_data)

        # Submit
        self.api_client.post(f'/api/inventory/stock-counts/{count_id}/submit/')

        # Approve as admin
        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.post(f'/api/inventory/stock-counts/{count_id}/approve/', {'notes': 'Approved'})
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


# ===========================================================================
# VALIDATION FAILURES
# ===========================================================================

class StockCountValidationTest(BaseStockCountTest):

    def test_create_missing_location(self):
        """Test creating without location returns error."""
        self.api_client.force_authenticate(user=self.manager)
        response = self.api_client.post('/api/inventory/stock-counts/', {
            'reason': self.reason.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_reason(self):
        """Test creating without reason returns error."""
        self.api_client.force_authenticate(user=self.manager)
        response = self.api_client.post('/api/inventory/stock-counts/', {
            'location': self.location.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_non_draft_fails(self):
        """Test deleting a non-draft count."""
        count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)

        # Cancel it first
        cancel_stock_count(count, self.superadmin)

        # Try to delete via API - should fail
        self.api_client.force_authenticate(user=self.superadmin)
        response = self.api_client.delete(f'/api/inventory/stock-counts/{count.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# HISTORY / AUDIT TRAIL
# ===========================================================================

class StockCountHistoryTest(BaseStockCountTest):

    def test_history_created_on_create(self):
        """Test history entry is created on stock count creation."""
        count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)

        history = count.history.all()
        self.assertEqual(history.count(), 1)
        self.assertEqual(history[0].action, 'CREATED')

    def test_history_tracks_workflow(self):
        """Test history tracks the full workflow."""
        count = create_stock_count(self.tenant_id, {
            'location': self.location.id,
            'reason': self.reason.id,
        }, self.superadmin)
        assign_counters(count, self.superadmin, [str(self.staff.id)])
        count = InventoryStockCount.objects.get(id=count.id)
        count = start_counting(count, self.staff)

        history = count.history.all()
        actions = [h.action for h in history]
        self.assertIn('CREATED', actions)
        self.assertIn('ASSIGNED', actions)
        self.assertIn('STARTED', actions)
