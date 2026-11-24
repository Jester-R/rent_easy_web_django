from django.core.management.base import BaseCommand

from accounts.session_tracking import prune_login_session_history


class Command(BaseCommand):
    help = "Delete expired or signed-out login sessions past the retention window."

    def handle(self, *args, **options):
        count = prune_login_session_history()
        self.stdout.write(
            self.style.SUCCESS(f"Removed {count} old login session(s).")
        )
