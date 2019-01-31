from django.core.management.base import BaseCommand, CommandError
from skyfield.api import Loader
from django.conf import settings
from home.models import CachedAccess
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'clean out old CachedAccesses'

    def handle(self, *args, **options):
        now = timezone.now()
        two_days_ago = now - timedelta(days=2)
        CachedAccess.objects.filter(modified__lt=two_days_ago).delete()
        self.stdout.write(self.style.SUCCESS('Successfully deleted old CachedAccesses'))
