import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, HTTPError
from pathlib import Path

from balloon.settings import GRIB_PATH


class FileRef(object):
    """
    Reference to a forecast file.
    Constists of a Grib model, an analysis date and a frozenset of forecast offsets.
    """
    def __init__(self, model, analysis_date, forecast_offsets):
        self.model = model
        self.analysis_date = analysis_date
        self.forecast_offsets = frozenset(forecast_offsets)

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        sorted_offsets = sorted("%02d" % int(delta/timedelta(hours=1)) for delta in self.forecast_offsets)
        return f"{self.model.name}_{self.model.grid_pitch}/" + \
            "_".join([self.analysis_date.strftime('%Y%m%d%H%M')] + sorted_offsets)

    def __fspath__(self):
        return GRIB_PATH / f"{self}.grib2"

    def valid_dates(self):
        return sorted(self.analysis_date + offset for offset in self.forecast_offsets)

    def status(self):
        """
        Get the current status of this forecast among:
         * "future" (the file hasn't been produced by its source yet)
         * "missing" (may exist on the source, but hasn't been successfully downloaded)
         * "pending" (download actively in progress)
         * "stalled" (traces of a partial download, but nithing has been written in the last 15 minutes => probably dead)
         * "downloaded" (present and usable)
        :return:
        """
        if self.analysis_date > datetime.utcnow():
            return "future"
        p = self.__fspath__()
        if p.is_file():
            return "downloaded"
        p = p.parent / (p.name+'.part')
        if not p.is_file():
            return "missing"
        age = datetime.utcnow() - datetime.utcfromtimestamp(p.stat().st_mtime)
        if age > timedelta(minutes=15):
            return "stalled"
        else:
            return "pending"

    def download(self):
        """
        Ask the model to download the referenced file and return a filesystem path.
        :return: a Path upon success, None otherwise.
        """
        return self.model.download_file(self)


class GribModel(object):
    """
    Description of a family of GRIB model files, including

     * when forecasts are produced,
     * which valid dates are described in each forecast file
     * what's the grid pitch
     * how files are downloaded

    Each file, downloaded or not, already produced or not, is described by a tuple
    (analysis_date, frozenset of validity offsets). Such a key is called a "combo".
    """
    name = 'ABSTRACT'
    time_pitch = timedelta(hours=1)  # Interval between two validity dates
    grid_pitch = 0.5       # Interval between grid points in degrees
    analysis_offsets = ()  # Tuple of offsets from midnight UTC
    validity_offsets = ()  # Tuple of frozensets of offsets from analysis dates

    def list_forecasts(self, validity_date_from, validity_date_to=None):
        """
        List every combo containing valid dates in the date range given as parameters
        Those files aren't necessarily downloaded yet, and don't even necessarily exist (their analysis
        date might be in the future or in a very recent past).

        :param validity_date_from: first valid date looked for;
        :param validity_date_to: optional last valid date looked for;
            if missing, only one validity date `validity_date_from` is looked for.
        :return: dict valid_date => list of filerefs containing that valid date, sorted by decreasing analysis date
        """
        if validity_date_to is None:
            validity_date_to = validity_date_from
        results = {}  # valid date => fileref set
        midnight = validity_date_to.replace(hour=0, minute=0, second=0, microsecond=0)
        while midnight + max(max(self.validity_offsets)) >= validity_date_from:
            for analysis_offset in reversed(sorted(self.analysis_offsets)):
                for validity_offsets_for_file in self.validity_offsets:
                    fileref = FileRef(self, midnight + analysis_offset, validity_offsets_for_file)
                    for validity_date in fileref.valid_dates():
                        if validity_date_from <= validity_date <= validity_date_to:
                            if validity_date in results:
                                results[validity_date].append(fileref)
                            else:
                                results[validity_date] = [fileref]
            midnight -= timedelta(days=1)
        return results

    def best_fileref(self, date):
        """
        Return the most recently generated forecast valid for `date` which has been locally downloaded,
        or `None` is no such file is available.
        :param date:
        """
        candidates = list(self.list_forecasts(date).values())[0]
        for fileref in candidates:
            if fileref.status() == 'downloaded':
                return fileref
        return None  # Not found

    def download_file(self, combo):
        """
        Try to download the most recent prevision file for the dates combination
        :param combo: `(analysis_date, frozenset_of_validity_offsets)`
        :return: path to downloaded file, or None upon failure.
        """
        print(f"Downloading file for f{combo}")
        raise NotImplementedError("downloading method not implemented")

    def download_forecasts(self, validity_date_from, validity_date_to=None):
        """
        Try to download the best forecast for every valid date within the date range.
        Return a dictionary, valid_date => path of describing downloaded file.
        :param validity_date_from:
        :param validity_date_to:
        :return:
        """

        # valid_date => list of filerefs containing that valid date, sorted by decreasing analysis date
        forecasts = self.list_forecasts(validity_date_from, validity_date_to)

        # Create a fileref => path index, to avoid multiple downloads.
        downloaded = set()  # downloaded fileref set

        # Order the forecasts to download nearest validity dates first
        for validity_date, fileref_list in sorted(forecasts.items(), key=lambda item: item[0]):
            print(f"? Looking for {validity_date.isoformat()}:")
            for fileref in fileref_list:
                if fileref.analysis_date > datetime.utcnow():
                    continue  # File produced in the future
                elif fileref.analysis_date + max(fileref.forecast_offsets) < datetime.utcnow():
                    continue  # File only forecasts the past
                elif fileref.status() in ("downloaded", "pending"):
                    fspath = fileref.__fspath__()
                    downloaded.add(fileref)
                else:
                    # Perform download
                    fspath = fileref.download()
                if fspath: # Either found already downloaded/pending, or just downloaded
                    print(f"\t. Found in {fileref}")
                    break  # No need to look for older forecast of the same validity_date

        # Recreate the valid date => path result from the combo => path one.
        # Items are handled by increasing analysis date, so that the latest forecast will erase older ones.
        result = {}
        for fileref in downloaded:
            for validity_date in fileref.valid_dates():
                if validity_date_from <= validity_date <= validity_date_to:
                    result[validity_date] = fileref
                    # TODO Preprocess immediately
        return result

    def round_position(self, position):
        """
        :param position: `(lon, lat)`
        :return: `(lon, lat)` rounded to the model's grid pitch
        """
        return [round(x/self.grid_pitch) * self.grid_pitch for x in position]

    def round_time(self, date):
        """
        Return the date closest to `date` for which a forecast exists
        TODO only return downloaded and preprocessed dates? Maybe we'd rather fail upon missing files
        :param date:
        :return:
        """
        one_hour = timedelta(hours=1)
        if self.time_pitch % one_hour != timedelta(0):
            raise NotImplementedError("Time pitches not multiple of an hour not implemented")
        pitch = int(self.time_pitch.total_seconds()) // 3600
        if date.minute >= 30:
            date = date + one_hour
        h = int((date.hour + pitch // 2) // pitch) * pitch
        midnight = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnigth + timedelta(hours=h)  # Also works if h ≥ 24


def _make_analysis_offsets(text):
    """
    Transform a string "o0 o1 o2 o3" into a tuple of offsets, in hours, for model `analysis_offsets` class fields.
    """
    return tuple(timedelta(hours=int(i)) for i in text.split(" "))


def _make_validity_offsets(text, interval):
    """
    Transform a string "o0-o1 o2-o3 o4-o5" into nested tuples of offsets, in hours, for model `validity_offsets`
    class fields.
    """
    str_pairs = (str_pair.split('-') for str_pair in text.split(' '))
    def sp_to_tdt(a, b):
        return tuple(timedelta(hours=n) for n in range(int(a), int(b)+1, interval))
    return tuple(sp_to_tdt(*str_pair) for str_pair in str_pairs)


class ArpegeCommon(GribModel):
    name = 'ARPEGE'
    analysis_offsets = _make_analysis_offsets("0 6 12 18")
    url_pattern = \
        "http://dcpc-nwp.meteo.fr/services/PS_GetCache_DCPCPreviNum?" + \
        "token=__5yLVTdr-sGeHoPitnFc7TZ6MhBcJxuSsoZp6y0leVHU__&" + \
        "model=%(name)s&" + \
        "grid=%(grid_pitch)s&" + \
        "package=IP1&" + \
        "time=%(first_offset)sH%(last_offset)sH&" + \
        "referencetime=%(analysis_date)s&" + \
        "format=grib2"

    def download_file(self, fileref):
        MEGABYTE = 1024 * 1024
        offsets = sorted("%02d" % int(d / timedelta(hours=1)) for d in fileref.forecast_offsets)
        url = self.url_pattern % {
            'name':          self.name,
            'grid_pitch':    str(self.grid_pitch),
            'first_offset':  offsets[0],
            'last_offset':   offsets[-1],
            'analysis_date': fileref.analysis_date.strftime("%Y-%m-%dT%H:%M:%SZ")}
        output = Path(str(fileref.__fspath__())+".part")
        try:
            print(f"\t? Trying to download {output}\n\tfrom {url}")
            with urlopen(url) as input:
                if input.status > 299:
                    print(f"\t- Error {input.status}: {input.msg}")
                    return None
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('wb') as output_buffer:
                    for i in range(sys.maxsize):
                        sys.stdout.write(f"\r\t+ {i}MB")
                        sys.stdout.flush()
                        chunk = input.read(MEGABYTE)
                        if not chunk:
                            break
                        output_buffer.write(chunk)
                        output_buffer.flush()

            output.rename(fileref.__fspath__())
            print(f" Saved to {fileref.__fspath__()}")
            return output
        except HTTPError as e:
            print(f"\t- HTTP error {e.code}: {e.msg}")
            return None


class ArpegeGlobal(ArpegeCommon):
    time_pitch = timedelta(hours=3)
    grid_pitch = 0.5
    validity_offsets = _make_validity_offsets("0-24 27-48 51-72 75-102 105-114", 3)
    grib_constants_url = "https://donneespubliques.meteofrance.fr/donnees_libres/Static/gribsConstants/ARPEGE_0.5_CONSTANT.grib"


class ArpegeEurope(ArpegeCommon):
    time_pitch = timedelta(hours=1)
    grid_pitch = 0.1
    validity_offsets = _make_validity_offsets("0-12 13-24 25-36 37-48 49-60 61-72 73-84 85-96 97-102 103-114", 1)
    grib_constants_url = "https://donneespubliques.meteofrance.fr/donnees_libres/Static/gribsConstants/ARPEGE_0.1_CONSTANT.grib"


grib_models = {
    'ARPEGE_0.5': ArpegeGlobal(),
    'ARPEGE_0.1': ArpegeEurope()
}
