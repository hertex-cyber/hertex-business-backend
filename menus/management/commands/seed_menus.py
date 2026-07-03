"""
seed_menus.py — Management command to seed default system menus.

Usage:
    python manage.py seed_menus            # Create/update menus + role assignments
    python manage.py seed_menus --reset    # Delete all SYSTEM menus first, then re-seed
    python manage.py seed_menus --dry-run  # Preview what would be created without writing

Run this after every fresh DB migration to restore default navigation.
"""
from django.core.management.base import BaseCommand
from menus.models import Menu, MenuRole


# ─────────────────────────────────────────────────────────────────────────────
# Default system menu definitions
# Each dict: code, name, href, icon (Lucide name), section, order
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_MENUS = [
    # ── Operations ──────────────────────────────────────────────────────────
    {
        "code": "dashboard",
        "name": "Dashboard",
        "href": "/dashboard",
        "icon": "LayoutDashboard",
        "section": "Operations",
        "order": 1,
        "description": "Main overview dashboard",
    },
    {
        "code": "contacts",
        "name": "Contacts",
        "href": "/contacts",
        "icon": "Contact",
        "section": "Operations",
        "order": 2,
        "description": "Manage business contacts",
    },
    {
        "code": "crm",
        "name": "CRM",
        "href": "/crm",
        "icon": "Briefcase",
        "section": "Operations",
        "order": 3,
        "description": "Customer relationship management",
    },
    {
        "code": "docs",
        "name": "Doc Tools",
        "href": "/docs",
        "icon": "FileText",
        "section": "Operations",
        "order": 4,
        "description": "Document creation and management tools",
    },
    {
        "code": "inventory",
        "name": "Inventory",
        "href": "/inventory/items",
        "icon": "Box",
        "section": "Operations",
        "order": 5,
        "description": "Item master and inventory management",
    },
    {
        "code": "hr",
        "name": "HR",
        "href": "/hr",
        "icon": "Users",
        "section": "Operations",
        "order": 6,
        "description": "Human resources management",
    },
    {
        "code": "accounts",
        "name": "Accounts",
        "href": "/accounts",
        "icon": "CreditCard",
        "section": "Operations",
        "order": 7,
        "description": "Accounting and financial management",
    },
    {
        "code": "media",
        "name": "Media",
        "href": "/media",
        "icon": "ImageIcon",
        "section": "Operations",
        "order": 8,
        "description": "Media library and asset management",
    },
    {
        "code": "lms",
        "name": "LMS",
        "href": "/lms",
        "icon": "GraduationCap",
        "section": "Operations",
        "order": 9,
        "description": "Learning management system",
    },
    {
        "code": "sales-tasks",
        "name": "Sales Tasks",
        "href": "/sales/tasks",
        "icon": "Target",
        "section": "Sales",
        "order": 1,
        "description": "Task board and execution management",
    },
    {
        "code": "sales-targets",
        "name": "Targets",
        "href": "/sales/targets",
        "icon": "Crosshair",
        "section": "Sales",
        "order": 2,
        "description": "Sales targets and cycles management",
    },
    {
        "code": "sales-dashboard-team",
        "name": "Team Dashboard",
        "href": "/sales/dashboard/team",
        "icon": "Users",
        "section": "Sales",
        "order": 3,
        "description": "Manager's team performance overview",
    },
    {
        "code": "sales-dashboard-executive",
        "name": "Executive Dashboard",
        "href": "/sales/dashboard/executive",
        "icon": "BarChart3",
        "section": "Sales",
        "order": 4,
        "description": "VP/CRO enterprise-wide sales performance",
    },
    {
        "code": "invoices",
        "name": "Invoices",
        "href": "/invoices",
        "icon": "FileText",
        "section": "Operations",
        "order": 10,
        "description": "Invoice creation and management",
    },
    {
        "code": "settings_pref",
        "name": "Preferences",
        "href": "/settings",
        "icon": "Settings",
        "section": "Settings",
        "order": 1,
        "description": "User preferences and settings",
    },
    # ── Admin ────────────────────────────────────────────────────────────────
    {
        "code": "admin",
        "name": "Admin",
        "href": "/admin",
        "icon": "ShieldCheck",
        "section": "Admin",
        "order": 1,
        "description": "System administration panel",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Role configuration
# ─────────────────────────────────────────────────────────────────────────────
ALL_ROLES = ["Superadmin", "Admin", "Manager", "Staff", "Vendor", "User"]
MANAGER_PLUS_ROLES = ["Superadmin", "Admin", "Manager"]
ADMIN_ONLY_ROLES = ["Superadmin", "Admin"]

# Per-menu role override: codes listed here get custom role lists
# All other menus default to MANAGER_PLUS_ROLES
MENU_ROLE_OVERRIDES = {
    "dashboard": ALL_ROLES,       # Everyone needs the dashboard
    "settings_pref": ALL_ROLES,   # Everyone needs settings
    "admin": ADMIN_ONLY_ROLES,    # Only admins
}


class Command(BaseCommand):
    help = (
        "Seed default SYSTEM menus and role assignments. "
        "Safe to re-run — uses update_or_create so existing data is not duplicated."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete ALL existing SYSTEM menus before seeding (destructive).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        prefix = "[DRY RUN] " if dry_run else ""

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{prefix}ByteHive ERP — Seeding Default System Menus\n" + "─" * 50
        ))

        # ── Optional reset ────────────────────────────────────────────────────
        if options["reset"]:
            if dry_run:
                count = Menu.objects.filter(type="SYSTEM").count()
                self.stdout.write(self.style.WARNING(
                    f"{prefix}Would delete {count} SYSTEM menus."
                ))
            else:
                from django.db import transaction
                from menus.models import MenuUser
                with transaction.atomic():
                    system_ids = list(Menu.objects.filter(type="SYSTEM").values_list("id", flat=True))
                    if system_ids:
                        MenuRole.objects.filter(menu_id__in=system_ids).delete()
                        MenuUser.objects.filter(menu_id__in=system_ids).delete()
                        deleted_count = Menu.objects.filter(id__in=system_ids).delete()[0]
                        self.stdout.write(self.style.WARNING(
                            f"  ⚠  Deleted {deleted_count} existing SYSTEM menus."
                        ))

        # ── Seed menus ────────────────────────────────────────────────────────
        created_menus = 0
        updated_menus = 0
        created_roles = 0
        skipped_roles = 0

        for menu_data in DEFAULT_MENUS:
            menu_code = menu_data["code"]
            roles = MENU_ROLE_OVERRIDES.get(menu_code, MANAGER_PLUS_ROLES)

            defaults = {
                "name": menu_data["name"],
                "href": menu_data["href"],
                "icon": menu_data["icon"],
                "section": menu_data["section"],
                "order": menu_data["order"],
                "description": menu_data.get("description", ""),
                "type": "SYSTEM",
                "is_active": True,
                "organization": None,
                "required_product": None,
            }

            if dry_run:
                exists = Menu.objects.filter(code=menu_code, organization__isnull=True).exists()
                action = "Update" if exists else "Create"
                self.stdout.write(f"  {prefix}{action}: [{menu_data['section']}] {menu_data['name']} ({menu_code})")
                self.stdout.write(f"         Roles: {', '.join(roles)}")
            else:
                menu, created = Menu.objects.update_or_create(
                    code=menu_code,
                    organization=None,
                    defaults=defaults,
                )

                if created:
                    created_menus += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Created : [{menu.section}] {menu.name} ({menu.code})"))
                else:
                    updated_menus += 1
                    self.stdout.write(f"  ↻  Updated: [{menu.section}] {menu.name} ({menu.code})")

                # ── Assign roles (create missing ones) ────────────────────────────
                assigned_roles = set()
                for role in roles:
                    _, role_created = MenuRole.objects.get_or_create(
                        menu=menu,
                        role=role,
                        organization=None,
                    )
                    assigned_roles.add(role)
                    if role_created:
                        created_roles += 1
                    else:
                        skipped_roles += 1

                # ── Remove stale role assignments ──────────────────────────────────
                stale_roles = MenuRole.objects.filter(
                    menu=menu,
                    organization__isnull=True,
                ).exclude(role__in=roles)
                stale_count = stale_roles.count()
                if stale_count:
                    stale_roles.delete()
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠  Removed {stale_count} stale role(s) from '{menu.code}'"
                    ))

        # ── Summary ────────────────────────────────────────────────────────────
        if not dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("─" * 50))
            self.stdout.write(self.style.SUCCESS(
                f"  Menus   → {created_menus} created, {updated_menus} updated"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"  Roles   → {created_roles} added, {skipped_roles} already existed"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"\n  ✅ Done! {len(DEFAULT_MENUS)} system menus are now active.\n"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\n{prefix}Dry run complete. No changes written.\n"
            ))
