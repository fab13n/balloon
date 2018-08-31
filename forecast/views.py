import os
from datetime import datetime
from dateutil.parser import parse as parse_date

from django.http import JsonResponse, HttpResponseBadRequest

from . import models as m


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
    forecasts = grib_model.list_forecasts(from_date, from_date + longest_forecast)
    result = {}  # valid date -> analysis_date or False
    for valid_date, fileref_list in forecasts.items():
        available = False
        for fileref in fileref_list:
            status = fileref.status()
            if status == 'downloaded':
                available = fileref.analysis_date
                break
            # TODO report pending files
        result[valid_date.isoformat()] = available
    return JsonResponse(result)


def _close_files_with_procfs(fd_min=3, fd_max=-1):
    """
    Need to close sockets and files on forked process
    """
    for nm in os.listdir("/proc/self/fd"):
        if nm.startswith('.'):
            continue
        fd = int(nm)
        if fd >= fd_min and (fd_max == -1 or fd < fd_max):
            try:
                print(f"Close fd{fd} in forked process")
                os.close(fd)
            except OSError:
                pass


def update_file(request, grib_model, valid_date_from, valid_date_to=None):
    """
    Try to update every grib file describing a date within the proposed range.

    :param request:
    :param grib_model:
    :param valid_date_from:
    :param valid_date_to:
    :return:
    """
    try:
        grib_model = m.grib_models[grib_model]
    except KeyError:
        return HttpResponseBadRequest("Unknown GRIB  model name, valid names are " + ", ".join(m.grib_models.keys()))

    try:
        valid_date_from = parse_date(valid_date_from).replace(tzinfo=None)
        if valid_date_to is not None:
            valid_date_to = parse_date(valid_date_to).replace(tzinfo=None)
    except ValueError:
        return HttpResponseBadRequest("Cannot decode date")
    # TODO handle timezone-aware dates

    parent_pid = os.getpid()
    if os.fork() == 0:
        try:
            print("Start running download in a forked process")
            _close_files_with_procfs()
            grib_model.download_forecasts(valid_date_from, valid_date_to)
            print("Download process done")
        finally:
            os.exit(0)

    return list_files(request, grib_model)
