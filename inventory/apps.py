from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        import inventory.signals  # noqa

        # Auto-seed inventory features on startup (only if table exists)
        try:
            import os
            should_seed = os.environ.get('DJANGO_SEED_FEATURES', 'True') == 'True'
            if should_seed:
                from django.db import connection
                # Check if the table exists before querying to avoid RuntimeWarning
                table_name = 'inventory_inventoryfeature'
                if table_name in connection.introspection.table_names():
                    from inventory.models import InventoryFeature
                    if InventoryFeature.objects.count() == 0:
                        from inventory.seed_features import seed_inventory_features
                        seed_inventory_features()
        except Exception:
            # Silently pass on first migration (table not yet created)
            pass
