# Menu System Implementation Report

## Overview

The menu system is a **fully dynamic, database-driven sidebar navigation** with role-based access control (RBAC), product gating, multi-tenant organization scoping, and both system-level and custom menus. The backend (`crm_backend/menus/`) serves data via DRF endpoints; the frontend (`crm_frontend/`) consumes it via a React context provider.

---

## Backend Architecture (`crm_backend/menus/`)

### Models (`models.py` — 6 models, 231 lines)

| Model | Table | Purpose | Key Fields |
|-------|-------|---------|------------|
| `Organization` | `menus_organization` | Multi-tenant orgs | `name`, `owner` (FK User) |
| `Product` | `menus_product` | Purchasable modules | `name`, `code`, `is_active` |
| `OrgProductPurchase` | `menus_orgproductpurchase` | Product licensing per org | `organization`, `product`, `is_valid` (computed) |
| **`Menu`** | `menus_menu` | Core menu item | `type` (SYSTEM/CUSTOM), `code`, `name`, `href`, `icon`, `section`, `order`, `description`, `is_active`, `created_by`, `organization`, `required_product` |
| **`MenuRole`** | `menus_menurole` | Role-to-menu assignments | `menu`, `role` (6 choices), `organization` |
| **`MenuUser`** | `menus_menuuser` | User-to-menu overrides | `menu`, `user` |

**Constraints:**
- `unique_together = (organization, code)` — menu code unique per org
- `UniqueConstraint(code)` where `organization__isnull=True` — SYSTEM menu codes globally unique
- `unique_together = (menu, role, organization)` — MenuRole per org context
- Indexes on `(organization, is_active)`, `(type, is_active)`, `(section, order)`
- UUID primary keys on all models

**Model permission methods:**
- `can_edit(user)` — SYSTEM: Superadmin only; CUSTOM: org Admin/Superadmin
- `can_assign_user(user)` — SYSTEM: Superadmin/Admin; CUSTOM: same as `can_edit`
- `can_delete(user)` — SYSTEM: Superadmin only; CUSTOM: creator or org Superadmin

### Serializers (`serializers.py` — 160 lines)

| Serializer | Purpose |
|------------|---------|
| `MenuListSerializer` | Minimal list output — includes `roles` as `SerializerMethodField` filtered by org context |
| `MenuDetailSerializer` | Full detail with nested `roles`, `user_assignments`, creator/org/product names |
| `MenuCreateUpdateSerializer` | Create/update — validates `code` (alphanumeric + underscores) and `href` (must start with `/`) |
| `MenuMyMenusResponseSerializer` | Response shape: `{ sections: {...}, all_menus: [...] }` |
| `MenuRoleSerializer` | MenuRole CRUD |
| `MenuUserSerializer` | MenuUser with `user_email`, `user_name` read-only fields |
| `AssignMenuToRoleSerializer` | Validates `role` is one of 6 valid roles |
| `AssignMenuToUserSerializer` | Validates `user_id` exists |
| `ProductSerializer` | Product CRUD |
| `OrgProductPurchaseSerializer` | Purchase records with `is_valid` computed field |
| `OrganizationSerializer` | Org with nested product purchases |

### Views / API Endpoints (`views.py` — 701 lines)

**`MenuViewSet`** — Core CRUD + custom actions:

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/menus/` | List all menus (filtered by role/org) |
| `POST` | `/api/menus/` | Create custom menu |
| `GET` | `/api/menus/{id}/` | Menu detail |
| `PUT/PATCH` | `/api/menus/{id}/` | Update menu |
| `DELETE` | `/api/menus/{id}/` | Soft-delete (sets `is_active=False`) |
| **`GET`** | **`/api/menus/my-menus/`** | **Main sidebar endpoint — returns pre-grouped, filtered menus** |
| `POST` | `/api/menus/{id}/assign-role/` | Assign menu to role |
| `POST` | `/api/menus/{id}/remove-role/` | Remove menu from role |
| `POST` | `/api/menus/{id}/assign-user/` | Assign menu to individual user |
| `POST` | `/api/menus/{id}/remove-user/` | Remove menu from user |
| `GET/POST` | `/api/menus/user-assignments/` | Bulk get/set menu assignments per user |
| `GET` | `/api/menus/user-effective-menus/` | Admin inspection: shows all menus with role-based/direct/effective flags |

**`ProductViewSet`** — `GET /api/products/`, `GET /api/products/{id}/`
**`OrganizationViewSet`** — Full CRUD on orgs + `assign-product`/`revoke-product` actions

### Core Visibility Logic — `_get_visible_menus()` (lines 132-164)

```
1. Role-based menu IDs:  MenuRole where role=user.role (global + org-scoped)
2. User-specific menu IDs:  MenuUser where user=current_user
3. Union of both ID sets
4. Filter:  is_active=True
            AND (required_product IS NULL OR required_product IN purchased_products)
            AND (SYSTEM + org_isnull OR CUSTOM + org=user.organization)
5. Order by: section, order
```

### Permissions (`permissions.py` — 90 lines)

| Class | Type | Logic |
|-------|------|-------|
| `IsSuperadmin` | Global | `user.role == 'Superadmin'` |
| `IsOrgOwner` | Global | User == org.owner |
| `CanEditMenu` | Object-level | Delegates to `menu.can_edit(user)` |
| `CanDeleteMenu` | Object-level | Delegates to `menu.can_delete(user)` |
| `IsOrgAdminOrSuperadmin` | Global | `role in ['Superadmin', 'Admin']` |

### URL Routing (`urls.py`)

Mounted at `/api/` in `core/urls.py`. Uses DRF `DefaultRouter`:
- `menus/` → MenuViewSet
- `products/` → ProductViewSet
- `organizations/` → OrganizationViewSet

### Default Menu Seeding

**Data migration** (`0002_seed_default_menus.py`): Creates 15 SYSTEM menus on first `migrate`.

**Management command** (`seed_menus.py` — 314 lines): Idempotent re-seeding with `--reset` and `--dry-run` flags. Defines role groups:
- `ALL_ROLES` — Superadmin, Admin, Manager, Staff, Vendor, User
- `MANAGER_PLUS_ROLES` — Superadmin, Admin, Manager
- `ADMIN_ONLY_ROLES` — Superadmin, Admin
- Per-menu overrides: `dashboard` + `settings_pref` → ALL_ROLES; `admin` → ADMIN_ONLY; rest → MANAGER_PLUS

**Default menus:**

| Code | Name | Section | Icon | Access |
|------|------|---------|------|--------|
| `dashboard` | Dashboard | Operations | LayoutDashboard | All |
| `contacts` | Contacts | Operations | Contact | Manager+ |
| `crm` | CRM | Operations | Briefcase | Manager+ |
| `docs` | Doc Tools | Operations | FileText | Manager+ |
| `inventory` | Inventory | Operations | Box | Manager+ |
| `hr` | HR | Operations | Users | Manager+ |
| `accounts` | Accounts | Operations | CreditCard | Manager+ |
| `media` | Media | Operations | ImageIcon | Manager+ |
| `lms` | LMS | Operations | GraduationCap | Manager+ |
| `sales` | Sales | Operations | TrendingUp | Manager+ |
| `sales-tasks` | Sales Tasks | Operations | Target | Manager+ |
| `sales-targets` | Targets | Operations | Crosshair | Manager+ |
| `invoices` | Invoices | Operations | FileText | Manager+ |
| `settings_pref` | Preferences | Settings | Settings | All |
| `admin` | Admin | Admin | ShieldCheck | Admin+ |

---

## Frontend Architecture (`crm_frontend/`)

### State Management — `MenuContext.jsx` (151 lines)

- **Fetches** `GET /api/menus/my-menus/` on mount / user change
- **Caches** in `sessionStorage` (key: `menus_v2_{userId}`, TTL: 30s)
- **Refreshes** imperatively via `refreshMenus(force=false)` — pass `true` to bypass cache
- **Exports** via `useMenu()` hook: `{ menus, sections, loading, error, refreshMenus }`
- **Provider hierarchy**: `AuthProvider > MenuProvider` (in `App.jsx`)

### Sidebar Rendering — `Sidebar.jsx` (163 lines)

- Iterates `sections` object (e.g., `{ Operations: [...], Admin: [...] }`)
- Renders section headings (uppercase, e.g. "OPERATIONS")
- Sorts items by `item.order` within each section
- Each item renders as `<Link>` with:
  - Dynamic icon via `getLucideIcon(item.icon)` (from `iconMapper.js`)
  - Display name, href, ChevronRight indicator
- **Active link detection**: exact match first, then prefix match for nested routes
- **States handled**: loading (spinner), error (red message), empty (suggestive link), empty section ("No menus available")

### Icon Resolution — `iconMapper.js`

- Static mapping from Lucide name strings to imported React components
- `getLucideIcon(name)` — lookup with fallback to `LayoutDashboard`
- `getAvailableIcons()` — returns full list for admin form dropdown

### Admin Pages

| Page | File | Path | Purpose |
|------|------|------|---------|
| AdminMenus | `AdminMenus.jsx` | `/admin/menus` | List/filter/search/sort menus, edit/delete |
| AdminMenuForm | `AdminMenuForm.jsx` | `/admin/menus/create`, `/admin/menus/:id/edit` | Create/edit menu — all fields incl. icon dropdown, product selector, type toggle |
| AdminMenuRoles | `AdminMenuRoles.jsx` | `/admin/menus/roles` | Role-to-menu matrix — checkboxes with optimistic updates + rollback |
| UserMenuAssignModal | `UserMenuAssignModal.jsx` | (modal) | Per-user menu assignment — locked role-based + toggleable direct |
| UserMenusPanel | `UserMenusPanel.jsx` | (embedded) | Read-only user effective menus split by "Via Role" / "Direct Assigned" |

### Admin API Service — `menuService.js`

| Method | Endpoint |
|--------|----------|
| `getAllMenus(params)` | `GET /api/menus/` |
| `getUserDirectAssignments(userId)` | `GET /api/menus/user-assignments/` |
| `getUserEffectiveMenus(userId)` | `GET /api/menus/user-effective-menus/` |
| `bulkAssignMenusToUser(userId, menuIds)` | `POST /api/menus/user-assignments/` |
| `assignMenuToRole(menuId, role, orgId)` | `POST /api/menus/{id}/assign-role/` |
| `removeMenuFromRole(menuId, role, orgId)` | `POST /api/menus/{id}/remove-role/` |

### Routing (`App.jsx`)

Routes are hardcoded but linked dynamically via menu `href` fields. Key route-to-menu mapping:

| Route | Component | Menu Code |
|-------|-----------|-----------|
| `/dashboard` | Dashboard | `dashboard` |
| `/crm` | CRM | `crm` |
| `/contacts` | Contacts | `contacts` |
| `/docs` | Doc Tools | `docs` |
| `/hr/*` | HR | `hr` |
| `/accounts` | Accounts | `accounts` |
| `/media` | Media | `media` |
| `/lms` | LMS | `lms` |
| `/inventory/*` | InventoryRoutes | `inventory` |
| `/invoices/*` | Invoice pages | `invoices` |
| `/sales/*` | SalesTaskManager | `sales` |
| `/admin` | Admin overview | `admin` |
| `/settings` | Settings | `settings_pref` |

---

## Complete Data Flow

```
[PostgreSQL DB]
    ↓
Django REST API → GET /api/menus/my-menus/  (filtered by role, org, products)
    ↓
Axios → MenuContext.jsx  (cached in sessionStorage, TTL 30s)
    ↓
useMenu() hook → { sections, loading, error, refreshMenus }
    ↓
Sidebar.jsx  →  renders grouped nav links with Lucide icons
    ↓
react-router-dom  →  page components
```

## Security & Access Control

1. **Authentication**: JWT token (required for all endpoints)
2. **Role-based**: MenuRole entries per user role (global + org-scoped)
3. **Direct assignment**: MenuUser overrides for individual users
4. **Product gating**: `required_product` FK — menu hidden unless org purchased the product
5. **Org scoping**: CUSTOM menus isolated per organization; SYSTEM menus visible to all
6. **Soft-delete**: `is_active=False` hides menus without data loss

## Key Design Decisions

1. **100% dynamic menus** — no hardcoded sidebar items
2. **Role + direct assignment** — menus granted to roles or specific users
3. **Product gating** — menus can require a purchased product license
4. **Two menu types** — SYSTEM (Superadmin-managed) and CUSTOM (org-managed)
5. **Sections are data-driven** — grouping and ordering configured in DB
6. **Static icon mapping** — icons resolved client-side via `iconMapper.js`

## Files Summary

### Backend (18 files)
- `menus/models.py`, `menus/views.py`, `menus/serializers.py`, `menus/permissions.py`, `menus/urls.py`, `menus/admin.py`, `menus/apps.py`
- `menus/management/commands/seed_menus.py`
- `menus/migrations/0001_initial.py` through `0005_*.py`
- `core/settings.py`, `core/urls.py`

### Frontend (12 files)
- `src/context/MenuContext.jsx`, `src/components/Sidebar.jsx`, `src/components/Layout.jsx`
- `src/utils/iconMapper.js`
- `src/modules/admin/services/menuService.js`
- `src/modules/admin/pages/AdminMenus.jsx`, `AdminMenuForm.jsx`, `AdminMenuRoles.jsx`, `Admin.jsx`
- `src/modules/admin/components/UserManagement/UserMenuAssignModal.jsx`, `UserMenusPanel.jsx`
- `src/App.jsx`
