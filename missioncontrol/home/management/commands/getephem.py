from django.core.management.base import BaseCommand, CommandError
from skyfield.api import Loader
from django.conf import settings


class Command(BaseCommand):
    help = "get ephemeris files"

    def handle(self, *args, **options):
        load = Loader(settings.EPHEM_DIR)
        load("de405.bsp")
        load.timescale()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully downloaded ephemeris files to {settings.EPHEM_DIR}!"
            )
        )
