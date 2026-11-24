from django.core.management.base import BaseCommand

from payments.services import expire_unpaid_bookings, release_completed_bookings


class Command(BaseCommand):
    help = "Refresh booking-based listing availability (expiry and completed leases)."

    def handle(self, *args, **options):
        expired = expire_unpaid_bookings()
        released = release_completed_bookings()
        self.stdout.write(
            self.style.SUCCESS(
                f"Expired {expired} unpaid booking(s); reopened {released} completed listing(s)."
            )
        )
