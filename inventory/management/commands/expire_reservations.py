"""
Management command to auto-expire reservations that have passed their expiry date.

Usage:
    python manage.py expire_reservations
    python manage.py expire_reservations --dry-run

Schedule this as a cron job to run daily:
    0 2 * * * cd /path/to/project && python manage.py expire_reservations
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import InventoryReservation
from inventory.services.reservation_service import expire_reservation


class Command(BaseCommand):
    help = 'Auto-expire reservations past their expiry date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which reservations would be expired without actually expiring them',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        today = timezone.now().date()

        expired = InventoryReservation.objects.filter(
            status__in=['ACTIVE'],
            expiry_date__lt=today,
        )

        count = expired.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No reservations to expire.'))
            return

        self.stdout.write(f"Found {count} expired reservation(s):")
        for r in expired:
            self.stdout.write(
                f"  {r.reservation_number} (expired: {r.expiry_date}, "
                f"status: {r.get_status_display()})"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no reservations were expired.'))
            return

        expired_count = 0
        error_count = 0
        for reservation in expired:
            try:
                expire_reservation(reservation, user=None)
                expired_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {reservation.reservation_number} expired successfully."
                ))
            except ValueError as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {reservation.reservation_number}: {e}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Expired: {expired_count}, Errors: {error_count}"
        ))
