import os
from datetime import datetime
from dateutil.parser import parse as parse_date

from django.http import JsonResponse, HttpResponseBadRequest

from forecast.preprocess import extract_ground_altitude
from . import models as m
from . import preprocess

def list_files(request, grib_model):
    """
    List all possible GRIB model files in the future for named models, as object keys.
    Corresponding object values are either the analysis date, or False if the file isn't available locally.
    """
    try:
        grib_model = m.grib_models[grib_model]
    except KeyError:
        HttpResponseBadRequest("Unknown GRIB  model name")

    longest_forecast = max(max(grib_model.validity_offsets))
    if 'from' in request.GET:
        from_date = parse_date(request.GET['from'])
    else:
        from_date = datetime.utcnow()

    dates = preprocess.list_files(grib_model, from_date)
    str_dates = {k.isoformat(): v.isoformat() for k, v in dates.items()}

    return JsonResponse(str_dates)


def altitude(request, grib_model):
    try:
        grib_model = m.grib_models[grib_model]
    except KeyError:
        HttpResponseBadRequest("Unknown GRIB  model name")
    try:
        longitude = float(request.GET['longitude'])
        latitude = float(request.GET['latitude'])
        return JsonResponse(extract_ground_altitude(grib_model, (longitude, latitude)))
    except KeyError as e:
        return HttpResponseBadRequest(f"Missing parameter {e.args[0]}")
    except ValueError as e:
        return HttpResponseBadRequest(e.args[0])
