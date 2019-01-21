import os
from datetime import datetime
from dateutil.parser import parse as parse_date

from django.http import JsonResponse, HttpResponseBadRequest

from forecast.extract import ColumnExtractor
from . import models as m
from . import extract


def list_files(request, grib_model):
    """
    List all possible GRIB model files in the future for named models, as object keys.
    Corresponding object values are either the analysis date, or False if the file isn't available locally.
    """
    try:
        grib_model = m.grib_models[grib_model]
    except KeyError:
        HttpResponseBadRequest("Unknown GRIB  model name")

    if 'from' in request.GET:
        date_from = parse_date(request.GET['from'])
    else:
        date_from = datetime.utcnow()

    dates = ColumnExtractor(grib_model).list_files(date_from=date_from)
    if len(dates) == 0:
        dates = ColumnExtractor(grib_model).list_files(n=6)

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
        return JsonResponse(ColumnExtractor(grib_model).extract_ground_altitude((longitude, latitude)))
    except KeyError as e:
        return HttpResponseBadRequest(f"Missing parameter {e.args[0]}")
    except ValueError as e:
        return HttpResponseBadRequest(e.args[0])
