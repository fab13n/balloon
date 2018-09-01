from dateutil.parser import parse

from django.http import HttpResponseBadRequest, JsonResponse

from forecast.models import grib_models
from forecast.preprocess import extract
from core import models as m
from .trajectory import trajectory as core_trajectory, drifts_to_geojson


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

    layers = sorted(extract(model, date, (longitude, latitude)), key=lambda l: l.p_hPa, reverse=True)

    return JsonResponse([layer.to_json() for layer in layers], safe=False)


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

    balloon = m.Balloon(ground_volume_m3=ground_volume_m3, balloon_mass_kg=balloon_mass_kg, payload_mass_kg=payload_mass_kg)
    layers = extract(model, date, (longitude, latitude))
    drift = core_trajectory(balloon, layers)
    geojson = drifts_to_geojson((longitude, latitude), date, drift)
    return JsonResponse(geojson, safe=False)
