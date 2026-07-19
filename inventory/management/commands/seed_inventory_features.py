from django.core.management.base import BaseCommand
from inventory.seed_features import seed_inventory_features


class Command(BaseCommand):
    help = 'Seed default Inventory features for the feature management system.'

    def handle(self, *args, **options):
        created, updated = seed_inventory_features()
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded inventory features: {created} created, {updated} updated'
            )
        )
