from datetime import datetime

from dateutil.parser import parse as parse_date

from django.core.management.base import BaseCommand, CommandError

from forecast.models import grib_models
from balloon.settings import ACTIVE_MODELS

class Command(BaseCommand):
    help = "Download best previsions covering the specified date range for a model"

    def add_arguments(self, parser):
        parser.add_argument("-m", "--model", default=None, type=str, help="Name of the weather model. All active models if unspecified")
        parser.add_argument("date_from", default="", type=str, nargs='?', help="First forecast date to download, default=now")
        parser.add_argument("date_to", default="", type=str, nargs='?', help="Last forecast date to download, default=max forecast")

    def handle(self, *args, **options):
        try:
            m = options.get('model')
            if m is None:
                models = [grib_models[m] for m in ACTIVE_MODELS]
            else:
                # TODO support multiple model names
                models = [grib_models[m]]
        except KeyError:
            raise CommandError(f"Unknown GRIB model name {options['model']}, valid names are " +
                               ", ".join(grib_models.keys()))
        try:
            if options['date_from'] != "":
                valid_date_from = parse_date(options['date_from']).replace(tzinfo=None)
            else:
                valid_date_from = datetime.utcnow()
            if options['date_to'] != "":
                valid_date_to = parse_date(options['date_to']).replace(tzinfo=None)
            else:
                valid_date_to = datetime.utcnow() + max(max(max(m.validity_offsets)) for m in models)
        except ValueError:
            raise CommandError("Cannot decode date")
        # TODO handle timezone-aware dates

        print(f"Downloading models {', '.join(f'{m.name} {m.grid_pitch}' for m in models)} from {valid_date_from.isoformat()} to {valid_date_to.isoformat()}")
        
        for m in models:
            m.download_forecasts(valid_date_from, valid_date_to)
