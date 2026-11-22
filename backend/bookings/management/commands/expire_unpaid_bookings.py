from django.core.management.base import BaseCommand

from payments.services import expire_unpaid_bookings


class Command(BaseCommand):
    help = "Expire unpaid booking requests that passed the payment window."

    def handle(self, *args, **options):
        count = expire_unpaid_bookings()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} booking request(s)."))
