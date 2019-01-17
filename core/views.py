from dateutil.parser import parse

from django.http import HttpResponseBadRequest, JsonResponse

from forecast.models import grib_models
from forecast import extract
from core import models as m
from . import trajectory as core_trajectory


def _parse_date(date_string):
    """Return an UTC, timezone-naive date"""
    return parse(date_string).astimezone().replace(tzinfo=None)


def column(request):
    params = request.GET
    try:
        model = grib_models[params['model']]
        latitude = float(params['latitude'])
        longitude = float(params['longitude'])
        date = _parse_date(params['date'])
    except KeyError as e:
        field = e.args[0]
        return HttpResponseBadRequest(f"Parameter {field} missing or invalid")
    except ValueError as e:
        msg = e.args[0]
        return HttpResponseBadRequest(f"Invalid parameter: {msg}")

    column = extract.ColumnExtractor(model).extract(date, (longitude, latitude))

    return JsonResponse(column.to_json())


def trajectory(request):
    params = request.GET
    try:
        model = grib_models[params['model']]
        latitude = float(params['latitude'])
        longitude = float(params['longitude'])
        date = _parse_date(params['date'])
        balloon_mass_kg = float(params['balloon_mass_kg'])
        payload_mass_kg = float(params['payload_mass_kg'])
        ground_volume_m3 = float(params['ground_volume_m3'])
    except KeyError as e:
        field = e.args[0]
        return HttpResponseBadRequest(f"Parameter {field} missing or invalid")
    except ValueError as e:
        msg = e.args[0]
        return HttpResponseBadRequest(f"Invalid parameter: {msg}")

    position = model.round_position((longitude, latitude))

    extractor = extract.ColumnExtractor(
        model=model,
        extrapolated_pressures=range(1, 20))
    column = extractor.extract(date, position)
    balloon = m.Balloon(
        ground_volume_m3=ground_volume_m3,
        balloon_mass_kg=balloon_mass_kg,
        payload_mass_kg=payload_mass_kg,
        ground_pressure_hPa=column.ground_pressure)
    traj = core_trajectory.trajectory(
        balloon=balloon,
        column_extractor=extractor,
        p0=position,
        t0=date)
    geojson = core_trajectory.to_geojson(traj)
    return JsonResponse(geojson, safe=False)
