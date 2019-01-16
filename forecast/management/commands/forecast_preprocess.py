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

    def get_processed_files(self, path):
        try:
            with (path / "processed.json").open('rb') as f:
                return set(json.load(f))
        except Exception:
            return []

    def set_processed_files(self, path, files):
        # Convert to list of strings, remove references to missing files
        filtered_filenames = [f.absolute().__fspath__() for f in files if f.is_file()]
        try:
            with (path / "processed.json").open('wb') as f:
                return json.dump(filtered_filenames, f)
        except Exception:
            pass

    def handle(self, *args, **options):
        roots = map(Path, options['grib_file'])
        for r in roots:
            processed_files = self.get_processed_files(r)
            files = [f for f in self.list_files([r]) if f not in processed_files]
            print("Files to preprocess: \n\t"+"\n\t".join(str(f) for f in files))
            for f in files:
                preprocess(grib_file_path=f,
                           lat1=options['lat1'], lat2=options['lat2'],
                           lon1=options['lon1'], lon2=options['lon2'],
                           force=options['force'])
            self.set_processed_files(r, processed_files | files)
