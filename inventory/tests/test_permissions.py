"""
Tests for permission hardening — verifies tenant isolation and role-based access.
"""

import uuid
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient

API_BASE = '/api/inventory/'

from inventory.models import (
    InventoryItem, ItemCategory, Unit,
    InventoryLocation, InventoryLocationType,
)

User = get_user_model()


class TenantIsolationTest(APITestCase):
    """Verify users from Org A cannot access Org B data."""

    @classmethod
    def setUpTestData(cls):
        from menus.models import Organization

        cls.user_a = User.objects.create_user(
            email=f"user_a_{uuid.uuid4().hex[:6]}@test.com",
            password="testpass123", role="Superadmin",
            is_active=True,
        )
        cls.user_b = User.objects.create_user(
            email=f"user_b_{uuid.uuid4().hex[:6]}@test.com",
            password="testpass123", role="Superadmin",
            is_active=True,
        )

        cls.org_a = Organization.objects.create(
            name=f"Org A {uuid.uuid4().hex[:6]}",
            slug=f"org-a-{uuid.uuid4().hex[:6]}",
            owner=cls.user_a,
        )
        cls.org_b = Organization.objects.create(
            name=f"Org B {uuid.uuid4().hex[:6]}",
            slug=f"org-b-{uuid.uuid4().hex[:6]}",
            owner=cls.user_b,
        )

        cls.user_a.organization = cls.org_a
        cls.user_a.role = "Admin"
        cls.user_a.save()
        cls.user_b.organization = cls.org_b
        cls.user_b.role = "Admin"
        cls.user_b.save()

        cls.tenant_a_id = cls.org_a.id
        cls.tenant_b_id = cls.org_b.id

        # Create data for both tenants
        cat_a = ItemCategory.objects.create(
            tenant_id=cls.tenant_a_id, category_code="CAT-A",
            category_name="Category A",
        )
        cat_b = ItemCategory.objects.create(
            tenant_id=cls.tenant_b_id, category_code="CAT-B",
            category_name="Category B",
        )

        cls.item_a = InventoryItem.objects.create(
            tenant_id=cls.tenant_a_id, item_code="ITEM-A",
            item_name="Item A", category=cat_a,
        )
        cls.item_b = InventoryItem.objects.create(
            tenant_id=cls.tenant_b_id, item_code="ITEM-B",
            item_name="Item B", category=cat_b,
        )

    def test_user_a_cannot_see_item_b(self):
        """User from Org A should not see Org B's items via API."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'{API_BASE}items/')
        self.assertEqual(response.status_code, 200)
        item_codes = [i['item_code'] for i in response.data['results']]
        self.assertIn('ITEM-A', item_codes)
        self.assertNotIn('ITEM-B', item_codes)

    def test_user_b_cannot_see_item_a(self):
        """User from Org B should not see Org A's items via API."""
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(f'{API_BASE}items/')
        self.assertEqual(response.status_code, 200)
        item_codes = [i['item_code'] for i in response.data['results']]
        self.assertNotIn('ITEM-A', item_codes)
        self.assertIn('ITEM-B', item_codes)

    def test_user_b_cannot_access_item_a_detail(self):
        """Direct access to Org A's item by Org B user should 404."""
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(f'{API_BASE}items/{self.item_a.id}/')
        self.assertEqual(response.status_code, 404)

    def test_tenant_isolation_in_categories(self):
        """Tenant isolation works for categories."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'{API_BASE}categories/')
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        codes = [c['category_code'] for c in data]
        self.assertIn('CAT-A', codes)
        self.assertNotIn('CAT-B', codes)

    def test_tenant_isolation_in_locations(self):
        """Tenant isolation works for locations."""
        loc_type = InventoryLocationType.objects.create(
            tenant_id=self.tenant_a_id, type_code="WH",
            type_name="Warehouse",
        )
        InventoryLocation.objects.create(
            tenant_id=self.tenant_a_id, location_code="LOC-A",
            location_name="Location A", location_type=loc_type,
        )
        InventoryLocation.objects.create(
            tenant_id=self.tenant_b_id, location_code="LOC-B",
            location_name="Location B", location_type=loc_type,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'{API_BASE}locations/')
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        codes = [l['location_code'] for l in data]
        self.assertIn('LOC-A', codes)
        self.assertNotIn('LOC-B', codes)


class RoleBasedAccessTest(APITestCase):
    """Verify role-based access control works correctly."""

    @classmethod
    def setUpTestData(cls):
        from menus.models import Organization
        cls.superadmin = User.objects.create_user(
            email=f"sa_{uuid.uuid4().hex[:6]}@test.com",
            password="testpass123", role="Superadmin",
            is_active=True,
        )
        cls.org = Organization.objects.create(
            name=f"Org {uuid.uuid4().hex[:6]}",
            slug=f"org-{uuid.uuid4().hex[:6]}",
            owner=cls.superadmin,
        )
        cls.tenant_id = cls.org.id

        cls.superadmin.organization = cls.org
        cls.superadmin.save()

        cls.admin_user = User.objects.create_user(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            password="testpass123", role="Admin",
            organization=cls.org, is_active=True,
        )
        cls.manager = User.objects.create_user(
            email=f"mgr_{uuid.uuid4().hex[:6]}@test.com",
            password="testpass123", role="Manager",
            organization=cls.org, is_active=True,
        )
        cls.staff = User.objects.create_user(
            email=f"staff_{uuid.uuid4().hex[:6]}@test.com",
            password="testpass123", role="Staff",
            organization=cls.org, is_active=True,
        )

    def test_staff_cannot_create_items(self):
        """Staff role cannot create items."""
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(f'{API_BASE}items/', {
            'item_code': 'NEW-ITEM', 'item_name': 'New Item',
        })
        self.assertIn(response.status_code, (403, 401, 400, 404))

    def test_manager_can_create_items(self):
        """Manager role can create items."""
        cat = ItemCategory.objects.create(
            tenant_id=self.tenant_id, category_code="CAT",
            category_name="Category",
        )
        unit = Unit.objects.create(
            tenant_id=self.tenant_id, unit_code="PCS",
            unit_name="Pieces",
        )
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(f'{API_BASE}items/', {
            'item_code': 'MGR-ITEM', 'item_name': 'Manager Item',
            'category': str(cat.id), 'unit': str(unit.id),
        })
        self.assertEqual(response.status_code, 201)

    def test_staff_cannot_delete_items(self):
        """Staff role cannot delete items."""
        cat = ItemCategory.objects.create(
            tenant_id=self.tenant_id, category_code="CAT2",
            category_name="Category",
        )
        item = InventoryItem.objects.create(
            tenant_id=self.tenant_id, item_code="DEL-ITEM",
            item_name="Delete Test", category=cat,
        )
        self.client.force_authenticate(user=self.staff)
        response = self.client.delete(f'{API_BASE}items/{item.id}/')
        self.assertIn(response.status_code, (403, 401, 404))

    def test_unauthenticated_user_blocked(self):
        """Unauthenticated requests should be blocked."""
        from rest_framework import status
        response = self.client.get(f'{API_BASE}items/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
