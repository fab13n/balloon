import math

# Physical constants
EARTH_RADIUS = 6367445      # in metres
G = 9.81                    # Gravitational acceleration, m/s²
HE_LIFT_KG_M3 = .025/.0224  # Helium lifting power at ground level, kg/m³
CX_BALLOON = 0.45           # Cx of an ascending balloon (determined empirically)
CX_PARACHUTE = 1.4          # Cx under parachute (determined empirically)
R_PARACHUTE_M = .65         # Parachute radius
R_DRY_J_kgK = 287.058       # Specific gas constant of dry air, J/(kg·K)
R_VAPOR_J_kgK = 461.495     # Specific gas constant of vapor, J/(kg·K)

BALLOON_FEATURES = {  # Envelope mass in kg => { Suggested lift force in N, burst volume in m³ }
    0.5: {'suggested_lift': 15, 'burst_volume': 97},
    1.0: {'suggested_lift': 16, 'burst_volume': 288},
    1.2: {'suggested_lift': 17, 'burst_volume': 370},
    2.0: {'suggested_lift': 18, 'burst_volume': 755}
}


class Balloon(object):
    """
    Features of a balloon with its gas filling and payload.
    """
    def __init__(self,
                 ground_volume_m3,
                 balloon_mass_kg,
                 payload_mass_kg,
                 ground_pressure_hPa=1013):

        self.balloon_mass_kg = balloon_mass_kg
        self.payload_mass_kg = payload_mass_kg
        self.ground_volume_m3 = ground_volume_m3
        self.ground_pressure_hPa = ground_pressure_hPa

        balloon_features = BALLOON_FEATURES[balloon_mass_kg]
        self.burst_volume_m3 = balloon_features['burst_volume']
        self.suggested_lift_N = balloon_features['suggested_lift']

        mass = balloon_mass_kg + payload_mass_kg

        # How much of Archimede's force is needed to lift the total mass plus provide
        # the suggested lifting force, converted into m³ of He.
        self.suggested_volume_m3 = (mass + self.suggested_lift_N / G) / HE_LIFT_KG_M3

        # Lift doesn't change with pressure/altitude: the number of moles of He
        # is constant, as well as the number of air moles displaced, therefore
        # Archimede's force is the same although the volume and pressure change.
        self.lift_N = (self.ground_volume_m3 * HE_LIFT_KG_M3 - mass) * G


class Cell(object):
    """
    Description of atmosphere at a given lat/lon/alt/time point, extracted from a GRIB model.
    """
    def __init__(self, u, v, t, p=None, z=None, r=None, rho=None):
        """
        :param u: east-ward speed of wind (m/s)
        :param v: north-ward speed of wind (m/s)
        :param t: temperature (°K)
        :param p: atmospheric pressure (hPa)
        :param z: altitude above MSL (m) TODO infer from std atmosphere if None
        :param r: relative humidity (percents)
        """
        # self.direction_rad = math.atan(u, v)
        # self.speed_ms = (u**2 + v**2)**0.5  # m/s
        self.u_ms = u     # m/s
        self.v_ms = v     # m/s
        self.t_K = t      # °K
        self.z_m = z      # m
        self.p_hPa = p    # hPa
        if rho:           # kg/m³
            self.rho_kg_m3 = rho
        elif p is not None and r is not None:
            self.rho_kg_m3 = self.rho(p, t, r)
        else:
            # TODO: we can probably get a better estimate from pressure without relative humidity
            self.rho_kg_m3 = self.chapman_density()
        self.height_m, self.z0_m = None, None  # Can only be filled once in a `Column`

    def chapman_density(self):
        """
        Approximate air density according to altitude, following Chapman's simplified formula.
        Only used if the model doesn't provide pressure and relative humidity.
        TODO maybe the exact formula would still be better, even without relative humidity?
        :return: Density in kg/m³ at altitude `self.z_m`
        """
        h = self.z_m / 1000  # Height in km
        if h < 17:
            a = 1.293; b = -0.1202
        elif 17 <= h < 22:
            a = 3.8923; b = -0.185
        elif 22 <= h < 25:
            a = 1.3553; b = -0.13707
        elif 25 <= h < 30:
            a = 2.11643; b = -0.15489
        elif 30 <= h < 30:
            a = 3.51386; b = -0.1718
        else:
            raise ValueError(f"{h}km is too high")
        return a * math.exp(b * h)

    def sat_vapor_pressure(self, t_K):
        """
        Return the partial water pressure at which t_K is the dew point
        (water vapor saturation = 100%).

        Allows to convert relative humidity and pressure into an accurate air density.

        Formula taken from somewhere on the Internets (https://www.omnicalculator.com/physics/air-density).
         """
        t_C = t_K - 273.15
        p_dew_hPa = 6.1078 * 10 ** ((7.5 * t_C) / (t_C + 237.3))
        return p_dew_hPa

    def rho(self, p_hPa, t_K, rh_percents):
        """
        Compute air density, in kg/m³, according to pressure, temperature and
        relative humidity (water weights around 18g/mol whereas air is around 30).
        """
        p_vapor_hPa = self.sat_vapor_pressure(t_K) * rh_percents / 100  # partial vapor pressure
        p_dry_hPa = p_hPa - p_vapor_hPa  # partial dry air pressure
        rho = p_dry_hPa * 100 / (R_DRY_J_kgK * t_K) + \
              p_vapor_hPa * 100 / (R_VAPOR_J_kgK * t_K)  # density
        return rho

    def __str__(self):
        """
        Generate a readable representation of this cell.
        """
        return f"{self.z_m/1000:.3}km_H, " + \
               f"{abs(self.u_ms):.1g}m/s_{'E' if self.u_ms>0 else 'W'}, " + \
               f"{abs(self.v_ms):.1g}m/s_{'N' if self.u_ms>0 else 'S'}, " + \
               f"{int(self.t_K - 273.15)}°C, " + \
               f"{self.p_hPa}hPa, " + \
               f"{self.rho_kg_m3:.2g}kg/m³"

    def to_json(self):
        """
        Convert into a dictionary ready to be JSON-serialized.
        """
        return dict(u=self.u_ms, v=self.v_ms, t=self.t_K, z=self.z_m, p=self.p_hPa, rho=self.rho_kg_m3)

class Column(object):
    """
    Stack of cells at a given (lon, lat) grid position.
    In addition to storing cells in a pressure-indexed dictionary `self.cell`,
    this class offers a couple of interpolation / extrapolation features for missing points,
    most notably the exact launch altitude and the stratospheric levels.

    Public fields include:
    * `grib_model`
    * `position`: `(longitude, latitude)`
    * `valid_date`, `analysis_date` always in UTC
    * `ground_altitude` in meters
    * `cells` a sorted list by  increasing altitude
    """
    def __init__(self, grib_model, position, valid_date, analysis_date,
                 ground_altitude, cells, extrapolated_pressures=()):
        """
        :param grib_model:
        :param position:
        :param valid_date:
        :param analysis_date:
        :param ground_altitude:
        :param cells:
        :param extrapolated_pressures:
        """
        self.grib_model = grib_model
        self.position = grib_model.round_position(position)
        self.valid_date = valid_date
        self.analysis_date = analysis_date
        self.ground_altitude = ground_altitude

        # Sort cells and remove cells below ground surface
        sorted_cells = sorted(cells, key=lambda l: l.p_hPa, reverse=True)
        i = next(i for (i, l) in enumerate(sorted_cells) if l.z_m > ground_altitude)
        sorted_cells = sorted_cells[i:]

        # Interpolated ground pressure (needed to compute balloon dilatation according to pressure)
        (la, lb) = sorted_cells[:2]
        self.ground_pressure = self._interpolate_altitude_pressure(Pa=la.p_hPa, Pb=lb.p_hPa, Za=la.z_m, Zb=lb.z_m,
                                                                   Zc=ground_altitude)

        # Extrapolated stratospheric cells (sometimes the balloon bursts above the top model cell)
        (ly, lz) = sorted_cells[-2:]
        sorted_extrapolated_pressures = sorted((p for p in extrapolated_pressures if p < lz.p_hPa), reverse=True)
        extrapolated_cells = [self._extrapolate_stratospheric_cell(ly, lz, p) for p in sorted_extrapolated_pressures]

        # Add heights to cells
        all_overground_cells = sorted_cells + extrapolated_cells
        for (l0, l1, l2) in zip(all_overground_cells[0:], all_overground_cells[1:], all_overground_cells[2:]):
            # Boundaries for l1 are at (Z2+Z1)/2 and (Z1+Z0)/2, height is therefore (Z2-Z0)/2
            l1.height_m = (l2.z_m - l0.z_m) / 2

        # First cell goes from ground_altitude to La/Lb boundary
        la.height_m = (la.z_m + lb.z_m)/2 - ground_altitude

        # For  last cell, we consider that z_m is in the middle of the cell.
        # The height is therefor twice the distance from last boundary (Zy+Zz)/2 to Zz.
        lz.height_m = lz.z_m - ly.z_m

        # Add z limits z0 & z1
        z = self.ground_altitude
        for c in all_overground_cells:
            c.z0_m = z
            z = z + c.height_m if c.height_m else None

        underground_cells = i * [None]
        self.cells = underground_cells + all_overground_cells

    def does_contain_point(self, position):
        """
        indicate whether the point at `position=(longitude, latitude)` is in this column
        :param position:
        :return: True/False
        """
        hp = self.grib_model.grid_pitch / 2.  # half-pitch
        return all(self.position[i]-hp <= position[i] <= self.position[i] + hp for i in range(2))

    def is_closest_to_date(self, date):
        """
        Whether this column is the best one, in terms of valid_date, to describe this exact date.
        """
        return self.grib_model.round_time(date) == self.valid_date

    def _interpolate_altitude_pressure(self, Pa, Za, Pb, Zb, Pc=None, Zc=None):
        """
        interpolate pressure from altitude or conversely.

        Pressure is supposed to follow a power law `Pi = P · exp(-K · Zi)`,
        with constants `P` and `K` to be determined.
        With two points `(Pa, Za)` and `(Pb, Zb)` we can determine `P` and `K`,
        then use them to interpolate nearby `Pc` from `Zc` or conversely.

        Exactly one of parameters `Pc` and `Zc` must be None, and will be interpolated
        and returned as a result.

        :param Pa: pressure at first point
        :param Za: altitude of first point
        :param Pb: pressure at second point
        :param Zb: altitude of second point
        :param Zc: altitude at which the pressure must be interpolated if not None
        :param Pc: pressure at which the altitude must be interpolated if not None
        :return: either interpolated Zc or interpolated Pc, depending on which parameter was None.
        """
        K = math.log(Pb / Pa) / (Za - Zb)
        P = Pa * math.exp(K * Za)

        if Zc is None and Pc is None:
            raise ValueError("Only one of Pc/Zc must be None")
        elif Zc is None:
            return math.log(P / Pc) / K
        elif Pc is None:
            return P * math.exp(-K * Zc)
        else:
            raise ValueError("One of Pc/Zc must be None")

    def _extrapolate_stratospheric_cell(self, cell0, cell1, p):
        """
        Create an extrapolated cell in the stratosphere, in case the balloon goes beyond
        the forecast model's ceiling.
        :param cell0: second highest cell from the model
        :param cell1: highest cell from the model
        :param p: pressure cell to extrapolate
        :return: a cell object
        """
        return Cell(
            u=cell1.u_ms,
            v=cell1.v_ms,
            t=cell1.t_K,  # Temperatures have a limited gradient in the stratosphere
            p=p,
            z=self._interpolate_altitude_pressure(Pa=cell1.p_hPa, Pb=cell0.p_hPa, Za=cell1.z_m,
                                                  Zb=cell0.z_m, Pc=p),
            rho=cell1.rho_kg_m3 * p / cell1.p_hPa)

    def to_json(self):
        return {
            'model': self.grib_model.name,
            'grid_pitch': self.grib_model.grid_pitch,
            'position': {'x': self.position[0], 'y': self.position[1]},
            'analysis_date': self.analysis_date.isoformat(),
            'valid_date': self.valid_date.isoformat(),
            'ground': {'pressure': self.ground_pressure, 'z': self.ground_altitude},
            'cells': [cell.to_json() for cell in self.cells]
        }
