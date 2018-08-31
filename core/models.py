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


class Layer(object):
    """
    Description of atmosphere at a given point, extracted from a GRIB model.
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
        p_vapor_hPa = self.sat_vapor_pressure(t_K) * rh_percents / 100  # partial vaport pressure
        p_dry_hPa = p_hPa - p_vapor_hPa  # partial dry air pressure
        rho = p_dry_hPa * 100 / (R_DRY_J_kgK * t_K) + \
              p_vapor_hPa * 100 / (R_VAPOR_J_kgK * t_K)  # density
        return rho

    def __str__(self):
        """
        Generate a readable representation of this layer.
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
