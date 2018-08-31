from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from forecast.preprocess import preprocess


class Command(BaseCommand):
    help = "Download best previsions covering the specified date range for a model"

    def add_arguments(self, parser):
        parser.add_argument("grib_file", type=str, help="File to preprocess")
        parser.add_argument("--lat1", type=float, nargs='?', default=42., help="Lowest latitude kept")
        parser.add_argument("--lat2", type=float, nargs='?', default=52., help="Higest latitude kept")
        parser.add_argument("--lon1", type=float, nargs='?', default=0., help="Lowest longitude kept")
        parser.add_argument("--lon2", type=float, nargs='?', default=9., help="Lowest longitude kept")
        parser.add_argument("-f", "--force", action='store_true', default=False,
                            help="Force re-processing on already processed dates")


    def handle(self, *args, **options):
        preprocess(grib_file_path=Path(options['grib_file']),
                   lat1=options['lat1'], lat2=options['lat2'], lon1=options['lon1'], lon2=options['lon2'],
                   force=options['force'])
