from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from balloon.settings import GRIB_PATH, PREPROCESS_BOX
from forecast.preprocess import preprocess


class Command(BaseCommand):
    help = "Download best previsions covering the specified date range for a model"

    def add_arguments(self, parser):
        parser.add_argument("grib_file", type=str, nargs='*', default=[GRIB_PATH], help="File to preprocess")
        parser.add_argument("--lat1", type=float, nargs='?', default=PREPROCESS_BOX['lat1'], help="Lowest latitude kept")
        parser.add_argument("--lat2", type=float, nargs='?', default=PREPROCESS_BOX['lat2'], help="Higest latitude kept")
        parser.add_argument("--lon1", type=float, nargs='?', default=PREPROCESS_BOX['lon1'], help="Lowest longitude kept")
        parser.add_argument("--lon2", type=float, nargs='?', default=PREPROCESS_BOX['lon2'], help="Lowest longitude kept")
        parser.add_argument("-f", "--force", action='store_true', default=False,
                            help="Force re-processing on already processed dates")

    def list_files(self, paths):
        files = []
        for p in paths:
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files += self.list_files(p.glob("**/*.grib*"))
            else:
                raise CommandError(f"Invalid input file/directory {p}")
        return files

    def handle(self, *args, **options):
        files = self.list_files(map(Path, options['grib_file']))
        print("Files to preprocess: \n\t"+"\n\t".join(str(f) for f in files))
        for f in files:
            preprocess(grib_file_path=f,
                       lat1=options['lat1'], lat2=options['lat2'], lon1=options['lon1'], lon2=options['lon2'],
                       force=options['force'])
