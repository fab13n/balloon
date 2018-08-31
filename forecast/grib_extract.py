import pygrib
from numbers import Number

from core.models import Layer


def round_to_grid(pos, pitch):
    """
    Get the grid coordinate closest to `pos`, if grid coordinates are multiples of `pitch`
    :param pos: a number of array of numbers
    :param pitch: grid pitch
    :return: a rounded position on the grid of pitch `pitch`.
    """
    if isinstance(pos, Number):
        return round(pos/pitch) * pitch
    else:
        return [round_to_grid(p, pitch) for p in pos]


def grib_extract(model, date, position, log=lambda x: print(x)):
    (lon, lat) = round_to_grid(position, 0.5)
    shortNames = ('u', 'v', 't', 'p', 'z', 'r')
    layer_values = {}  # level -> shortName -> value
    file = model.best_fileref(date)
    filename = str(file.__fspath__())  # pygrib doesn't seem to be __fspath__ aware
    log(f"From file {filename}")
    for m in pygrib.open(str(file.__fspath__())).select(shortName=shortNames, typeOfLevel='isobaricInhPa', validDate=date):
        name=m.shortName
        log(f"\treading {name}@{m.level}hPa")
        data = m.data(lon1=lon, lon2=lon, lat1=lat, lat2=lat)
        val = data[0][0][0]
        if name == 'z':
            val = int(val/9.81)
        if m.level in layer_values:
            layer_values[m.level][name] = val
        else:
            layer_values[m.level] = {name: val}

    layers = [Layer(p=level, **values) for (level, values) in layer_values.items()]
    # print("\n".join(str(layer) for layer in layers))
    return layers
