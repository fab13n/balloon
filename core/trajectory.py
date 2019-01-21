import math
from datetime import timedelta
import logging

from .models import CX_PARACHUTE, CX_BALLOON, R_PARACHUTE_M, G, EARTH_RADIUS


logger = logging.getLogger('balloon')


def volume_m3(balloon, cell):
    """
    Volume of the gas in a balloon in a given cell
    :param balloon:
    :param cell:
    :return: volume in m³
    """
    return balloon.ground_volume_m3 * balloon.ground_pressure_hPa / cell.p_hPa


def speed_up_ms(balloon, cell):
    """
    Speed of the balloon going up in a given cell, in m/s.
    The drag force is `½·ρ·S·Cx·V²`, with `S` the frontal area.
    At equilibrium, drag force equals lift, which gives:

    `V = √((2F) / (ρ·S·Cx))`.

    The frontal area is deduced from the volume, by solving
    `V = 4/3·π·R³` for `R` and injecting it in `S = π·R²`.

    :param balloon:
    :param cell:
    :return: speed going up in this cell (s)
    """
    balloon_frontal_aera_m2 = math.pi * (3 / 4 * volume_m3(balloon, cell) / math.pi) ** (2 / 3)
    return math.sqrt((2 * balloon.lift_N) / (cell.rho_kg_m3 * balloon_frontal_aera_m2 * CX_BALLOON))


def speed_down_ms(balloon, cell):
    """
    Same general principle as for speed up, but witout the mass of the balloon.
    However, the force isn't the lift but the weight of the payload
    (the balloon has blown up), and the surface and Cx are those of the parachute.

    :param balloon:
    :param cell:
    :return: time spent going down in this cell (s)
    """
    f = G * balloon.payload_mass_kg
    area = math.pi * R_PARACHUTE_M**2
    return math.sqrt((2*f) / (cell.rho_kg_m3 * area * CX_PARACHUTE))


def apply_drift(position, drift):
    """
    Compute the position resulting from applying the drift `(east, north)`, in meters, to a position
    `(lon, lat)` in degrees.

    Meters `m` are converted in angle degrees `d` with `m / 2πR = d / 360 ⇒ d = 180m / πR`,
    with `R` the Earth radius for latitudes, and the meridian's radius `R·cos(latitude)` for longitudes

    :param position: position in degrees
    :param drift: drift to apply in meters
    :return: resulting (lon, lat) position in degrees.
    """
    (lon, lat) = position
    (east_m, north_m) = drift

    north_d = (180 * north_m) / (math.pi * EARTH_RADIUS)
    east_d = (180 * east_m) / (math.pi * EARTH_RADIUS * math.cos(math.radians(lat)))

    return lon + east_d, lat + north_d


def pos_string(p, z):
    ns = "N" if p[1] >= 0 else "S"
    ew = 'E' if p[0] >= 0 else "W"
    return f"{p[1]:05.2f}{ns};{p[0]:04.2f}{ew}^{int(z):05d}m"


def make_trajectory_point(column, cell, position, time, speed_ms, volume=None):
    """
    Generate a new trajectory point, update latest position and time
    """
    direction = +1 if speed_ms > 0 else -1
    r = round
    t = cell.height_m / abs(speed_ms)
    drift = [cell.u_ms * t, cell.v_ms * t]
    position = apply_drift(position, drift)
    time += timedelta(seconds=t)
    point = {
        'speed': {'x': r(cell.u_ms, 1), 'y': r(cell.v_ms, 1), 'z': r(speed_ms, 1)},
        'move': {'x': r(drift[0]), 'y': r(drift[1]), 'z': direction * r(cell.height_m), 't': r(t)},
        'position': {'x': r(position[0], 4), 'y': r(position[1], 4), 'z': r(cell.z_m)},
        'cell': {'x': column.position[0], 'y': column.position[1], 'z': [cell.z0_m, cell.z0_m+cell.height_m],
                 't': column.valid_date.isoformat()},
        'pressure': cell.p_hPa,
        'rho': r(cell.rho_kg_m3, 3),
        'temp': r(cell.t_K + 273.15),
        'time': time.isoformat().split(".", 1)[0]+"Z"
    }
    if volume is not None:
        point['volume'] = r(volume, 1)
    return (point, position, time)


def trajectory(balloon, column_extractor, p0, t0):
    """
    Compute the cumulated drift of a balloon in a sequence of cells, sorted
    by ascending altitude.

    :param balloon:
    :param column_extractor:
    :param p0: initial position `(lon, lat)`
    :param t0: date of launch
    :return: a list of `(eastward drift, northward drift, altitude, time)` tuples,
        in meters and seconds, for each cell.
    """

    # In this first version, we simply go up then down the cells in the column.
    # In a second step, we'll want to be able to jump from a column to another:
    # keep going smoothly up or down the pressure indexing, but change the column itself
    # (the number of cells in a column may vary because of ground altitude).

    # Compute the drifts north-ward and east-ward, in each cell, of the ascending balloon.

    points = []
    time = t0
    position = p0
    burst = False
    column = column_extractor.extract(time, position)
    i = 0

    # Skip underground cells
    while column.cells[i] is None:
        i += 1

    # Way up; we keep index `i` rather than iterating directly on the column,
    # because there might be column changes due to drift and/or time passing.
    while i < len(column.cells) and not burst:
        cell = column.cells[i]
        v_m3 = volume_m3(balloon, cell)
        logger.info(f"({i:02d}) {pos_string(position, cell.z_m)}, {cell.p_hPa:>4d}hPa, volume = {int(v_m3)}m³")
        if v_m3 > balloon.burst_volume_m3:
            logger.info(f"(**) {int(v_m3)}m³ ≥ {balloon.burst_volume_m3}m³ => burst!")
            burst = True
            break
        (point, position, time) = make_trajectory_point(column, cell, position, time, speed_up_ms(balloon, cell), volume=v_m3)
        points.append(point)
        i += 1
        if not column.does_contain_point(position) or not column.is_closest_to_date(time):
            column = column_extractor.extract(time, position)
            logger.info(f"(**) Switching to column {column.position[0]}, {column.position[1]}")

    if not burst:  # the for loop can exit because of overflow(exception raised), balloon burst, or exit of column
        raise ValueError("The balloon doesn't burst in the cells provided")

    # Way down, at parachute speed. Index `i` is still at the cell index where the balloon burst.
    while i >= 0:
        cell = column.cells[i]
        if cell is None:  # On ground
            break
        logger.info(f"({i:02d}) back to {pos_string(position, cell.z_m)}, {cell.p_hPa: 4d}hPa")
        (point, position, time) = make_trajectory_point(column, cell, position, time, -speed_down_ms(balloon, cell))
        points.append(point)
        if not column.does_contain_point(position) or not column.is_closest_to_date(time):
            column = column_extractor.extract(time, position)
            logger.info(f"(**) Switching to column {column.position[0]}, {column.position[1]}")
        i -= 1

    return points


def to_geojson(trajectory):
    """
    convert an initial position `(lon, lat)` and a sequence of drifts `(east, north)`
    into a geojson feature.

    :param position:
    :param drift:
    :return: dictionary ready to seraialize into geojson.
    """
    # TODO start from ground not MSL
    features = []
    for p in trajectory:
        ftr = {"type": "Feature",
               "geometry": {"type": "Point",
                            "coordinates": [round(p['position']['x'], 4), round(p['position']['y'], 4)]},
               "properties": p}
        features.append(ftr)

    return {"type": "FeatureCollection", "properties": {}, "features": features}
