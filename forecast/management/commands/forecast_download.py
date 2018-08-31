from datetime import datetime

from dateutil.parser import parse as parse_date

from django.core.management.base import BaseCommand, CommandError

from forecast.models import grib_models


class Command(BaseCommand):
    help = "Download best previsions covering the specified date range for a model"

    def add_arguments(self, parser):
        parser.add_argument("model_name", type=str, help="Name of the weather model")
        parser.add_argument("date_from", default="", type=str, nargs='?', help="First forecast date to download, default=now")
        parser.add_argument("date_to", default="", type=str, nargs='?', help="Last forecast date to download, default=max forecast")

    def handle(self, *args, **options):
        try:
            grib_model = grib_models[options['model_name']]
        except KeyError:
            raise CommandError(f"Unknown GRIB model name {options['model_name']}, valid names are " +
                               ", ".join(grib_models.keys()))
        try:
            if options['date_from'] != "":
                valid_date_from = parse_date(options['date_from']).replace(tzinfo=None)
            else:
                valid_date_from = datetime.utcnow()
            if options['date_to'] != "":
                valid_date_to = parse_date(options['date_to']).replace(tzinfo=None)
            else:
                valid_date_to = datetime.utcnow() + max(max(grib_model.validity_offsets))
        except ValueError:
            raise CommandError("Cannot decode date")
        # TODO handle timezone-aware dates

        grib_model.download_forecasts(valid_date_from, valid_date_to)
