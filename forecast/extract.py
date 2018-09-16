import numpy as np
import json
from datetime import datetime
from dateutil.parser import parse

from balloon.settings import GRIB_PATH
from core.models import Column, Layer
from forecast.models import GribModel, grib_models
from forecast.preprocess import SHORT_NAMES


EPSILON = 1e-5 # EPSILON° < 1m


def extract_ground_altitude(model, position):
    if isinstance(model, GribModel):
        model_name = f"{model.name}_{model.grid_pitch}"
    else:
        model_name = model
        model = grib_models[model_name]
    (lon, lat) = model.round_position(position)
    try:
        with (GRIB_PATH / model_name / "terrain.json").open('r') as f:
            shape = json.load(f)
        with (GRIB_PATH / model_name / "terrain.np").open('rb') as f:
            array = np.load(f)
    except IOError:
        raise ValueError("No preprocessed terrain for this date")

    try:
        # TODO Round both coords to grid instead of testing up to epsilon?
        lon_idx = next(idx for (idx, lon2) in enumerate(shape['lons']) if abs(lon-lon2)<EPSILON)
        lat_idx = next(idx for (idx, lat2) in enumerate(shape['lats']) if abs(lat-lat2)<EPSILON)
    except StopIteration:
        raise ValueError("No preprocessed data for this position")

    return int(array[lon_idx][lat_idx])


def extract(model, date, position, extrapolated_pressures=()):
    if isinstance(model, GribModel):
        model_name = f"{model.name}_{model.grid_pitch}"
    else:
        model_name = model
        model = grib_models[model_name]
    (lon, lat) = model.round_position(position)
    basename = date.strftime("%Y%m%d%H%M")
    try:
        with (GRIB_PATH / model_name / (basename+".json")).open('r') as f:
            shape = json.load(f)
        with (GRIB_PATH / model_name / (basename+".np")).open('rb') as f:
            array = np.load(f)
    except IOError:
        raise ValueError("No preprocessed data for this date")

    try:
        lon_idx = next(idx for (idx, lon2) in enumerate(shape['lons']) if abs(lon-lon2) < EPSILON)
        lat_idx = next(idx for (idx, lat2) in enumerate(shape['lats']) if abs(lat-lat2) < EPSILON)
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

    column = Column(
        grib_model=model,
        position=position,
        valid_date=date,
        analysis_date=parse(shape['analysis_date']),
        ground_altitude=extract_ground_altitude(model, position),
        layers=layers,
        extrapolated_pressures=extrapolated_pressures)

    return column


def list_files(model, date_from=None):
    if isinstance(model, GribModel):
        model_name = f"{model.name}_{model.grid_pitch}"
    else:
        model_name = model
    results = {}
    for shape_file in (GRIB_PATH / model_name).glob("*.json"):
        try:
            valid_date = datetime.strptime(shape_file.stem, '%Y%m%d%H%M')
        except ValueError:
            continue  # Not a forecast file
        if date_from is not None and valid_date < date_from:
            continue
        try:
            with shape_file.open() as f:
                analysis_date = parse(json.load(f)['analysis_date'])
        except Exception:
            continue
        results[valid_date] = analysis_date
    return results
