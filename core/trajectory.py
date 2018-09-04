import math
from datetime import timedelta

from .models import CX_PARACHUTE, CX_BALLOON, R_PARACHUTE_M, G, EARTH_RADIUS


def volume_m3(balloon, layer):
    """
    Volume of the gas in a balloon in a given layer
    :param balloon:
    :param layer:
    :return: volume in m³
    """
    return balloon.ground_volume_m3 * balloon.ground_pressure_hPa / layer.p_hPa


def speed_up_ms(balloon, layer):
    """
    Speed of the balloon going up in a given layer, in m/s.
    The drag force is `½·ρ·S·Cx·V²`, with `S` the frontal area.
    At equilibrium, drag force equals lift, which gives:

    `V = √((2F) / (ρ·S·Cx))`.

    The frontal area is deduced from the volume, by solving
    `V = 4/3·π·R³` for `R` and injecting it in `S = π·R²`.

    :param balloon:
    :param layer:
    :return: speed going up in this layer (s)
    """
    balloon_frontal_aera_m2 = math.pi * (3/4 * volume_m3(balloon, layer) / math.pi) ** (2/3)
    return math.sqrt((2 * balloon.lift_N) / (layer.rho_kg_m3 * balloon_frontal_aera_m2 * CX_BALLOON))


def speed_down_ms(balloon, layer):
    """
    Same general principle as for speed up, but witout the mass of the balloon.
    However, the force isn't the lift but the weight of the payload
    (the balloon has blown up), and the surface and Cx are those of the parachute.

    :param balloon:
    :param layer:
    :return: time spent going down in this layer (s)
    """
    f = G * balloon.payload_mass_kg
    area = math.pi * R_PARACHUTE_M**2
    return math.sqrt((2*f) / (layer.rho_kg_m3 * area * CX_PARACHUTE))


def apply_drift(position, drift):
    """
    Compute the position resulting from applying the drift `(east, north)`, in meters, to a position
    `(lon, lat)` in degrees.

    :param position:
    :param drift:
    :return: resulting (lon, lat) position in degrees.
    """
    (lon, lat) = position
    (east, north) = drift

    return \
        lon + math.degrees(math.atan(east/(EARTH_RADIUS * math.cos(lat)))), \
        lat + math.degrees((math.atan(north/EARTH_RADIUS)))


def trajectory(balloon, column, p0, t0):
    """
    Compute the cumulated drift of a balloon in a sequence of layers, sorted
    by ascending altitude.

    :param balloon:
    :param column:
    :param p0: initial position `(lon, lat)`
    :param t0: date of launch
    :return: a list of `(eastward drift, northward drift, altitude, time)` tuples,
        in meters and seconds, for each layer.
    """

    # In this first version, we simply go up then down the layers in the column.
    # In a second step, we'll want to be able to jump from a column to another:
    # keep going smoothly up or down the pressure indexing, but change the column itself
    # (the number of layers in a column may vary because of ground altitude).

    # Compute the drifts north-ward and east-ward, in each layer, of the ascending balloon.
    traj = []
    time = t0
    position = p0
    def make_traj_point(layer, position, time, speed_ms, volume=None):
        """
        Generate a new trajectory point, update latest position and time
        """
        r = round
        t = layer.height_m / abs(speed_ms)
        drift = [layer.u_ms * t, layer.v_ms * t]
        position = apply_drift(position, drift)
        time += timedelta(seconds=t)
        point = {
            'speed': {'x': r(layer.u_ms, 1), 'y': r(layer.v_ms, 1), 'z': r(speed_ms, 1)},
            'move': {'x': r(drift[0]), 'y': r(drift[1]), 'z': r(layer.height_m), 't': r(t)},
            'position': {'x': r(position[0], 4), 'y': r(position[1], 4), 'z': r(layer.z_m)},
            'pressure': layer.p_hPa,
            'rho': r(layer.rho_kg_m3, 3),
            'temp': r(layer.t_K + 273.15),
            'time': time.isoformat().split(".", 1)[0]+"Z"
        }
        if volume is not None:
            point['volume'] = r(volume)
        return (point, position, time)

    for (i, layer) in enumerate(column.layers):
        v_m3 = volume_m3(balloon, layer)
        print(f"({i:02d}) at {layer.z_m}m, {layer.p_hPa}hPa, volume = {v_m3}m³")
        if v_m3 > balloon.burst_volume_m3:
            # Burst altitude reached: stop the loop going up, start going down
            print(f"(**) {v_m3}m³ ≥ {balloon.burst_volume_m3}m³ => burst!")
            top_layer = i
            break
        (point, position, time) = make_traj_point(layer, position, time, speed_up_ms(balloon, layer), volume=v_m3)
        traj.append(point)
    else:
        # The loop didn't break, we reached the top layer without bursting
        raise ValueError("The balloon doesn't burst in the layers provided")

    # TODO: drift on a prorata of the layer within which the balloon burst?

    # Drifts on the way down, at parachute speed
    for layer in reversed(column.layers[:i]):
        print(f"(--) back to {layer.z_m}m, {layer.p_hPa}hPa")
        (point, position, time) = make_traj_point(layer, position, time, -speed_down_ms(balloon, layer))
        traj.append(point)

    return traj

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
