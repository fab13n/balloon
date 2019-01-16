"""
Preprocess a GRIB file into a series of numpy arrays, one per valid date,
indexed in lon / lat / pressure, and containing tuples t / u / v / z / r.

Storage format:

One file with '.np' suffix contains the numpy array:

* t as an unsigned 16-bits int
* u & v as signed bytes in m/s
* z unsigned short (2 bytes) in meters
* r a two-bytes half-float

The other with suffix '.json' contains its indexing description:
* list of latitudes in degrees
* list of longitudes in degrees
* list of levels in hPa
"""
import json
import pygrib
import sys

import numpy as np


SHORT_NAMES = tuple("tuvzr")
DATA_TYPES = [(name, "f2") for name in SHORT_NAMES]
EPSILON = 1e-5


def preprocess(grib_file_path, lat1, lat2, lon1, lon2, force=False):
    # TODO ARPEGE INDEXED 0...360 rather than -180...180, boxes across 0 not supported
    with pygrib.open(grib_file_path.__fspath__()) as f:
        messages = f.select(shortName=SHORT_NAMES, typeOfLevel='isobaricInhPa')
        dates = set(m.validDate for m in messages)
        altitudes = sorted(set(m.level for m in messages))
        alt_idx_dict = {l: i for (i, l) in enumerate(altitudes)}
        if lon2 < lon1:  # Across the 0 meridian
            left = messages[0].data(lat1=lat1, lat2=lat2, lon1=lon1, lon2=360 - EPSILON)[1:]
            right = messages[0].data(lat1=lat1, lat2=lat2, lon1=0, lon2=lon2)[1:]
            lats, lons = (np.concatenate((l, r), axis=1) for l, r in zip(left, right))
        else:
            box = dict(lat1=lat1, lat2=lat2, lon1=lon1, lon2=lon2)
            lats, lons = messages[0].data(**box)[1:]
            print(f"preprocessing {grib_file_path} within {box}")
        analysis_date = messages[0].analDate.isoformat()
        lats = [x[0] for x in lats]
        lons = list(lons[0])
        shape = [len(lons), len(lats), len(altitudes)]

        for date in dates:
            basename = date.strftime("%Y%m%d%H%M")
            np_file_path = grib_file_path.parent / (basename+".np")
            shape_file_path = grib_file_path.parent / (basename+".json")
            if not force and shape_file_path.is_file():
                # Check if their is a preprocessed file at least as recent as this one.
                with shape_file_path.open() as f:
                    previous_analysis = json.load(f).get('analysis_date', "")
                if previous_analysis >= analysis_date:
                    print(f"\t- preprocessed data for {date.isoformat()} is more recent ({previous_analysis} vs. {analysis_date})")
                    continue
                else:
                    print(f"\t+ Update files for {date.isoformat()} ({previous_analysis} => {analysis_date})")
            else:
                print(f"\t+ Create files for {date.isoformat()}:")
            array = np.recarray(shape=shape, dtype=DATA_TYPES)
            for m in messages:
                if m.validDate != date:
                    continue
                sys.stdout.write(f"\r\t\tindexing {m.shortName}@{m.level}hPa")
                sys.stdout.flush()
                alt_idx = alt_idx_dict[m.level]
                if lon1 < lon2:
                    data = m.data(**box)[0]
                else:
                    left = messages[0].data(lat1=lat1, lat2=lat2, lon1=lon1, lon2=360 - EPSILON)[0]
                    right = messages[0].data(lat1=lat1, lat2=lat2, lon1=0, lon2=lon2)[0]
                    data = np.concatenate((left, right), axis=1)
                for lon_idx in range(len(lons)):
                    for lat_idx in range(len(lats)):
                        datum = data[lat_idx][lon_idx]
                        if m.shortName == 'z':
                            datum = int(datum/9.81)  # Convert geopotential in m²/s² into meters above MSL
                        array[lon_idx][lat_idx][alt_idx][m.shortName] = datum
            with np_file_path.open('wb') as f:
                np.save(f, array)
            with shape_file_path.open('w') as f:
                json.dump({'lats': lats, 'lons': lons, 'alts': altitudes, 'analysis_date': analysis_date}, f)
            print("")

