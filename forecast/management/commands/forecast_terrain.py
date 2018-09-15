import json
import pygrib
import sys
from urllib.request import urlopen
from requests import HTTPError

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from balloon.settings import GRIB_PATH, PREPROCESS_BOX
from forecast.models import grib_models


class Command(BaseCommand):
    help = "Download and preprocess ground altitudes for a model"

    def add_arguments(self, parser):
        parser.add_argument("model_name", type=str, help="GRIB model")
        parser.add_argument("--lat1", type=float, nargs='?', default=PREPROCESS_BOX['lat1'], help="Lowest latitude kept")
        parser.add_argument("--lat2", type=float, nargs='?', default=PREPROCESS_BOX['lat2'], help="Higest latitude kept")
        parser.add_argument("--lon1", type=float, nargs='?', default=PREPROCESS_BOX['lon1'], help="Lowest longitude kept")
        parser.add_argument("--lon2", type=float, nargs='?', default=PREPROCESS_BOX['lon2'], help="Lowest longitude kept")
        parser.add_argument("-f", "--force", action='store_true', default=False, help="Force re-processing")

    def download(self, model, force=False):
        model_path = GRIB_PATH / f"{model.name}_{model.grid_pitch}"
        output = GRIB_PATH / model_path / 'terrain.grib2.part'
        result = GRIB_PATH / model_path / 'terrain.grib2'
        print(f"? Trying to download {output}\n  from {model.grib_constants_url}")
        if not force and result.is_file():
            print("- Already downloaded")
            return result
        MEGABYTE = 1024*1024
        try:
            with urlopen(model.grib_constants_url) as input:
                if input.status > 299:
                    print(f"- Error {input.status}: {input.msg}")
                    return None
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('wb') as output_buffer:
                    for i in range(sys.maxsize):
                        sys.stdout.write(f"\r+ {i}MB")
                        sys.stdout.flush()
                        chunk = input.read(MEGABYTE)
                        if not chunk:
                            break
                        output_buffer.write(chunk)
                        output_buffer.flush()
            output.rename(result)
            print(f" Saved in {result}")
            return result
        except HTTPError as e:
            print(f"- HTTP error {e.code}: {e.msg}")
            return None

    def preprocess(self, grib_file, lat1, lat2, lon1, lon2, force=False):
        print("? Preprocessing terrain data...")
        np_file = grib_file.parent / "terrain.np"
        shape_file = grib_file.parent / "terrain.json"
        if not force and shape_file.is_file() and np_file.is_file():
            print("- Already processed")
            return
        box = dict(lat1=lat1, lat2=lat2, lon1=lon1, lon2=lon2)
        (msg,) = pygrib.open(str(grib_file)).select(shortName='h')
        h, lats, lons = msg.data(**box)
        lats = [x[0] for x in lats]
        lons = list(lons[0])
        shape = [len(lons), len(lats)]
        array = np.zeros(shape=shape, dtype=np.int16)
        for lon_idx in range(len(lons)):
            for lat_idx in range(len(lats)):
                datum = h[lat_idx][lon_idx]
                array[lon_idx][lat_idx] = datum
        with np_file.open('wb') as f:
            np.save(f, array)
        with shape_file.open('w') as f:
            json.dump({'lats': lats, 'lons': lons}, f)
        print(f"+ Saved in {np_file} and {shape_file}")

    def handle(self, *args, **options):
        try:
            grib_model = grib_models[options['model_name']]
        except KeyError:
            raise CommandError(f"Unknown GRIB model name {options['model_name']}, valid names are " +
                               ", ".join(grib_models.keys()))
        grib_file = self.download(grib_model, options['force'])
        if grib_file is None:
            raise CommandError("Cannot download GRIB file from provider")
        self.preprocess(grib_file, lat1=options['lat1'], lat2=options['lat2'], lon1=options['lon1'], lon2=options['lon2'],
                        force=options['force'])
