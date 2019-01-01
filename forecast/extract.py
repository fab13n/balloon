import numpy as np
import json
from datetime import datetime
from dateutil.parser import parse

from balloon.settings import GRIB_PATH
from core.models import Column, Cell
from forecast.models import GribModel, grib_models
from forecast.preprocess import SHORT_NAMES


EPSILON = 1e-5  # EPSILON° < 1m


class ColumnExtractor(object):

    def __init__(self, model, extrapolated_pressures=()):
        if isinstance(model, GribModel):
            self.model = model
        else:
            model_name = model
            self.model = grib_models[model_name]
        self.model = model
        self.extrapolated_pressures = extrapolated_pressures

        # Those will be filled by `update_array_and_shape` lazily.
        self.date = None
        self.array = None
        self.shape = None

    def _update_array_and_shape(self, date):
        """
        Ensures that self.array and self.shape contain the atmosphere's description for that date.
        Won't reload if the previous extraction request was for the same date.
        """
        date = self.model.round_time(date)
        if self.array is None or self.date != date:  # TODO perform rounding here?
            basename = date.strftime("%Y%m%d%H%M")
            model_name = f"{self.model.name}_{self.model.grid_pitch}"
            try:
                with (GRIB_PATH / model_name / (basename + ".json")).open('r') as f:
                    self.shape = json.load(f)
                with (GRIB_PATH / model_name / (basename + ".np")).open('rb') as f:
                    self.array = np.load(f)
            except IOError:
                raise ValueError("No preprocessed data for this date")
            self.date = date

    def extract_ground_altitude(self, position):
        """
        Extracts ground altitude at given position
        :param position: (lon, lat)
        :return: altitude above MSL in meters
        """
        model_name = f"{self.model.name}_{self.model.grid_pitch}"
        (lon, lat) = self.model.round_position(position)
        try:
            with (GRIB_PATH / model_name / "terrain.json").open('r') as f:
                shape = json.load(f)
            with (GRIB_PATH / model_name / "terrain.np").open('rb') as f:
                array = np.load(f)
        except IOError:
            raise ValueError("No preprocessed terrain for this date")

        try:
            # TODO Round both coords to grid instead of testing up to epsilon?
            lon_idx = next(idx for (idx, lon2) in enumerate(shape['lons']) if abs(lon-lon2)<EPSILON)
            lat_idx = next(idx for (idx, lat2) in enumerate(shape['lats']) if abs(lat-lat2)<EPSILON)
        except StopIteration:
            raise ValueError("No preprocessed data for this position")

        return int(array[lon_idx][lat_idx])

    def extract(self, date, position):
        """
        Retrieve an atmospheric column for the given date and position.
        :param date: UTC valid datetime
        :param position: (lon, lat)
        :return: a `Column` object
        """
        (lon, lat) = self.model.round_position(position)
        self._update_array_and_shape(date)

        try:
            lon_idx = next(idx for (idx, lon2) in enumerate(self.shape['lons']) if abs(lon-lon2) < EPSILON)
            lat_idx = next(idx for (idx, lat2) in enumerate(self.shape['lats']) if abs(lat-lat2) < EPSILON)
        except StopIteration:
            raise ValueError("No preprocessed weather data for this position")

        np_column = self.array[lon_idx][lat_idx][:]
        column = []
        for p, cell in zip(self.shape['alts'], np_column):
            kwargs = {'p': p}
            for name, val in zip(SHORT_NAMES, cell):
                kwargs[name] = float(val)
            cell = Cell(**kwargs)
            column.append(cell)

        column = Column(
            grib_model=self.model,
            position=position,
            valid_date=date,
            analysis_date=parse(self.shape['analysis_date']),
            ground_altitude=self.extract_ground_altitude(position),
            cells=column,
            extrapolated_pressures=self.extrapolated_pressures)

        return column

    def list_files(self, date_from=None):
        """
        Returns a dict `valid_date -> analysis_date` of weather files available for
        this model, optionally filtered by date (only those more recent in `valid_date`
        than `date_from`).
        :param date_from: optional starting datetime. `valid_date`s older than that are discarded.
        :return: `valid_date -> analysis_date` dict.
        """
        model_name = f"{self.model.name}_{self.model.grid_pitch}"
        results = {}
        for shape_file in (GRIB_PATH / model_name).glob("*.json"):
            try:
                valid_date = datetime.strptime(shape_file.stem, '%Y%m%d%H%M')
            except ValueError:
                continue  # Not a forecast file
            if date_from is not None and valid_date < date_from:
                continue
            try:
                with shape_file.open() as f:
                    analysis_date = parse(json.load(f)['analysis_date'])
            except Exception:
                continue
            results[valid_date] = analysis_date
        return results
