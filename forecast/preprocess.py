"""
Preprocess a GRIB file into a series of numpy arrays, one per valid date,
indexed in lon / lat / pressure, and containing tuples t / u / v / z / r.

Storage format:

One file with '.np' suffix contains the numpy array:

* t as an unsigned 16-bits int
* u & v as signed bytes in m/s
* z unsigned short (2 bytes) in meters
* r a two-bytes half-float

The other with suffix '.json' contains its indexing description:
* list of latitudes in degrees
* list of longitudes in degrees
* list of levels in hPa
"""
import json
import pygrib
from datetime import datetime
from dateutil.parser import parse

import numpy as np

from balloon.settings import GRIB_PATH
from core.models import Layer
from forecast.models import GribModel

SHORT_NAMES = tuple("tuvzr")
DATA_TYPES = [(name, "f2") for name in SHORT_NAMES]


def preprocess(grib_file_path, lat1, lat2, lon1, lon2, force=False):
    # TODO ARPEGE INDEXED 0...360 rather than -180...180, boxes across 0 not supported
    with pygrib.open(grib_file_path.__fspath__()) as f:
        box = dict(lat1=lat1, lat2=lat2, lon1=lon1, lon2=lon2)
        print(f"preprocessing {grib_file_path} within {box}")
        messages = f.select(shortName=SHORT_NAMES, typeOfLevel='isobaricInhPa')
        dates = set(m.validDate for m in messages)
        altitudes = sorted(set(m.level for m in messages))
        alt_idx_dict = {l: i for (i, l) in enumerate(altitudes)}
        lats, lons = messages[0].data(**box)[1:]
        analysis_date = messages[0].analDate.isoformat()
        lats = [x[0] for x in lats]
        lons = list(lons[0])
        shape = [len(lons), len(lats), len(altitudes)]

        for date in dates:
            basename = date.strftime("%Y%m%d%H%M")
            np_file_path = grib_file_path.parent / (basename+".np")
            shape_file_path = grib_file_path.parent / (basename+".json")
            if not force and shape_file_path.is_file():
                # Check if their is a preprocessed file at least as recent as this one.
                with shape_file_path.open() as f:
                    previous_analysis = json.load(f).get('analysis_date', "")
                if previous_analysis >= analysis_date:
                    print(f"\tpreprocessed data for {date.isoformat()} is more recent ({previous_analysis} vs. {analysis_date})")
                    continue
                else:
                    print(f"\tupdating preprocessed data for {date.isoformat()} ({previous_analysis} => {analysis_date})")
            else:
                print(f"\tfor {date.isoformat()}:")
            array = np.recarray(shape=shape, dtype=DATA_TYPES)
            for m in messages:
                if m.validDate != date:
                    continue
                print(f"\t\tindexing {m.shortName}@{m.level}hPa")
                alt_idx = alt_idx_dict[m.level]
                (data, _, _) = m.data(**box)
                for lon_idx in range(len(lons)):
                    for lat_idx in range(len(lats)):
                        datum = data[lat_idx][lon_idx]
                        if m.shortName == 'z':
                            datum = int(datum/9.81)  # Convert geopotential in m²/s² into meters above MSL
                        array[lon_idx][lat_idx][alt_idx][m.shortName] = datum
            with np_file_path.open('wb') as f:
                np.save(f, array)
            with shape_file_path.open('w') as f:
                json.dump({'lats': lats, 'lons': lons, 'alts': altitudes, 'analysis_date': analysis_date}, f)


def extract(model, date, position):
    if isinstance(model, GribModel):
        model_name = f"{model.name}_{model.grid_pitch}"
    else:
        model_name = model
    (lon, lat) = position
    basename = date.strftime("%Y%m%d%H%M")
    try:
        with (GRIB_PATH / model_name / (basename+".json")).open('r') as f:
            shape = json.load(f)
        with (GRIB_PATH / model_name / (basename+".np")).open('rb') as f:
            array = np.load(f)
    except IOError:
        raise ValueError("No preprocessed data for this date")

    try:
        # TODO round positions to grid
        lon_idx = next(idx for (idx, lon2) in enumerate(shape['lons']) if lon==lon2)
        lat_idx = next(idx for (idx, lat2) in enumerate(shape['lats']) if lat==lat2)
    except StopIteration:
        raise ValueError("No preprocessed data for this position")

    np_layers = array[lon_idx][lat_idx][:]
    layers = []
    for p, layer in zip(shape['alts'], np_layers):
        kwargs = {'p': p}
        for name, val in zip(SHORT_NAMES, layer):
            kwargs[name] = float(val)
        layer = Layer(**kwargs)
        layers.append(layer)
    return layers

def list_files(model, date_from=None):
    if isinstance(model, GribModel):
        model_name = f"{model.name}_{model.grid_pitch}"
    else:
        model_name = model
    results = {}
    for shape_file in (GRIB_PATH / model_name).glob("*.json"):
        valid_date = datetime.strptime(shape_file.stem, '%Y%m%d%H%M')
        if date_from is not None and valid_date < date_from:
            continue
        try:
            with shape_file.open() as f:
                analysis_date = parse(json.load(f)['analysis_date'])
        except Exception:
            continue
        results[valid_date] = analysis_date
    return results