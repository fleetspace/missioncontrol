import json
import base64
import copy
import zlib
import math
import logging
import hashlib
import datetime

from astropy.time import Time
from numpy import ediff1d, arange, vectorize
from scipy import optimize
from Crypto.Cipher import AES
from concurrent.futures import ProcessPoolExecutor
from collections import namedtuple
from itertools import product
from skyfield.api import Loader, Topos, EarthSatellite
from textwrap import wrap
from flask import request, Response
from urllib.parse import urljoin
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from home.models import GroundStation, Satellite, CachedAccess
from v0.track import get_track_file, DEF_STEP_S

AES_KEY = "bananasinpajamas"
AES_IV = "banana1orbanana2"  # must be 16 bytes

TWO_DAYS_S = 2 * 24 * 60 * 60
JD_MIN = 1.0 / 24.0 / 60.0
JD_SEC = JD_MIN / 60.0
TAU = 2.0 * math.pi

AltAz = namedtuple("AltAz", ["time", "altitude", "azimuth"])

load = Loader(settings.EPHEM_DIR)

##
## Note, Accesses uses Skyfield Time, which is stored as 64 bit floats of
##   Julian time.
##
##   This is a trade between performance and precision (required here), and
##   python native datetimes used by django, and common elsewhere.
##
##   Note that Skyfield Time objects have a precision of around 20us.
##   https://rhodesmill.org/skyfield/time.html#time-precision-is-around-20-1-s
##


def timescale_functions():
    """skyfield requires a "timescale" object that is used for things like
    leap seconds. we want to initialize it once, but avoid making it
    a global variable.
    This closure exposes two functions that rely on a global timescale,
    """
    timescale = load.timescale(builtin=True)

    def now():
        return timescale.now()

    def add_seconds(t, s):
        """
        There's no easier way to add seconds to a Time object :(
        """
        return timescale.utc(*map(sum, zip(t.utc, (0, 0, 0, 0, 0, s))))

    def tt(t):
        """do whatever it takes to make time into skyfield"""
        if t == "now":
            return now()
        if isinstance(t, str):
            t = timescale.from_astropy(Time(t, format="isot"))
        if isinstance(t, tuple):
            t = timescale.utc(*t)
        if isinstance(t, datetime.datetime):
            t = timescale.utc(t)
        return t

    def tt_iso(t):
        t = tt(t)
        return t.utc_iso(places=6)

    def tt_midpoint(start_time, end_time):
        start_time = tt(start_time)
        end_time = tt(end_time)
        mid_time = timescale.tai_jd(((start_time.tai + end_time.tai) / 2))
        return mid_time

    def tai_jd(t):
        return timescale.tai_jd(t)

    return add_seconds, now, tt, tt_iso, tt_midpoint, tai_jd


add_seconds, now, tt, tt_iso, tt_midpoint, tai_jd = timescale_functions()


def make_timeseries(start, end, step):
    """return a list of times from start to end.
    each step is 'step' seconds after the previous time.
    """
    if end.tt < start.tt:
        raise RuntimeError("end cannot be before start")

    t = start
    ts = [t]
    while t.tt <= end.tt:
        t = add_seconds(t, step)
        ts += [t]
    return ts


def get_default_range(range_start=None, range_end=None):
    """cast to internal time, set default range_start and range_end times"""
    if range_start is None:
        range_start = now()
    else:
        range_start = tt(range_start)
    if range_end is None:
        range_end = add_seconds(range_start, TWO_DAYS_S)
    else:
        range_end = tt(range_end)

    return range_start, range_end


def filter_range(windows, range_start, range_end, range_inclusive):
    """given a list of time windows (object that have start and end times),
    filters out items base on the range_inclusive criteria:
      start - the start of the range is inclusive
      end - the end of the range is inclusive
      neither - all windows must fit completely within range
      both (default) - windows that overlap with range are returned

    this is useful for pagination, when you may want to set either end to
    inclusive depending on the direction of the page so as to not get
    duplicate items.
    """
    # filter the start of the range
    if range_inclusive in ["end", "neither"]:
        windows = filter(lambda w: tt(w.start_time).tt >= range_start.tt, windows)
    else:
        windows = filter(lambda w: tt(w.end_time).tt >= range_start.tt, windows)

    # filter the end of the range
    if range_inclusive in ["start", "neither"]:
        windows = filter(lambda w: tt(w.end_time).tt <= range_end.tt, windows)
    else:
        windows = filter(lambda w: tt(w.start_time).tt <= range_end.tt, windows)

    return windows


class Access(object):
    """An Access is when a Groundstation has visibility to a Satellite"""

    _timescale = load.timescale(builtin=True)

    def __init__(self, start_time, end_time, sat, gs, max_alt, base_url=""):
        self._start_time = tt(start_time)
        self._end_time = tt(end_time)
        self._satellite = sat
        self._groundstation = gs
        self._max_alt = max_alt
        self._base_url = base_url

    @property
    def start_time(self):
        return self._start_time

    @property
    def end_time(self):
        return self._end_time

    def clone(self):
        return copy.copy(self)

    def clip(self, start, end):
        """returns a new access, with clipped start and end times"""
        access = self.clone()
        access._start_time = tai_jd(max(tt(start).tai, access.start_time.tai))
        access._end_time = tai_jd(min(tt(end).tai, access.end_time.tai))
        return access

    @property
    def json(self):
        return json.dumps(self.to_dict(), indent=4)

    def __lt__(self, other):
        return self.start_time.tt < other.start_time.tt

    def __gt__(self, other):
        return self.start_time.tt > other.start_time.tt

    @classmethod
    def from_time(cls, t, sat, gs, base_url=""):
        t = tt(t)

        if not Access.is_above_horizon(sat, gs, t):
            raise ObjectDoesNotExist(
                f"Access could not be found between {sat}, {gs} at {tt_iso(t)}"
            )

        start_time = Access.find_start(sat, gs, t)
        end_time = Access.find_end(sat, gs, t)
        max_alt = Access.find_max_alt(sat, gs, t)

        return cls(start_time, end_time, sat, gs, max_alt, base_url=base_url)

    @classmethod
    def from_overlap(cls, start_time, end_time, sat, gs):
        mid_time = tt_midpoint(start_time, end_time)
        return cls.from_time(mid_time, sat, gs)

    @staticmethod
    def encode_access_id(sat_id, gs_id, time):
        """
        Why are we doing this?
        Accesses are value objects and are computed on the fly, still they are
        useful to pass around. They can be described by a sat/gs pair and
        midtime of the pass.

        Encodes an access into an ID that can be used to recompute
        the same (or similar) access.

        Uses b64url encoding to avoid the need for urlencoding
        We encrypt so the keys look visually different for operators
          TODO there is probably a lighter-weight way that is less secure
        """

        time_strs = [str(int(t)) for t in time.tai_calendar()]
        time_str = time.utc_strftime("%y%m%d%H%M%S")
        string = "|".join((str(sat_id), str(gs_id), time_str))

        def encode(message):
            _crypt = AES.new(AES_KEY, AES.MODE_CFB, AES_IV)
            return _crypt.encrypt(message)

        encrypted = encode(string)
        access_id = base64.urlsafe_b64encode(encrypted)
        return access_id.decode()

    @classmethod
    def decode_access_id(cls, access_id):
        """
        complement to the above encoding algorithm
        """

        def decrypt(ciphertext):
            _crypt = AES.new(AES_KEY, AES.MODE_CFB, AES_IV)
            return _crypt.decrypt(ciphertext)

        crypted = base64.urlsafe_b64decode(access_id)
        decoded = decrypt(crypted).decode()
        sat_id, gs_id, time_tuple = decoded.split("|")
        times = [int(c) for c in wrap(time_tuple, 2)]
        # we only use the 2 digit year, so add 2000 back
        times[0] += 2000
        time = tt(tuple(times))
        return int(sat_id), int(gs_id), time

    @classmethod
    def from_id(cls, access_id, base_url=""):
        sat_id, gs_id, t = cls.decode_access_id(access_id)
        sat = Satellite.objects.get(id=int(sat_id))
        gs = GroundStation.objects.get(id=int(gs_id))
        return cls.from_time(t, sat, gs, base_url="")

    @property
    def access_id(self):
        mid_time = tt_midpoint(self.start_time, self.end_time)
        return self.encode_access_id(
            self._satellite.id, self._groundstation.id, mid_time
        )

    def iter_track(self, step=DEF_STEP_S):
        times = make_timeseries(self._start_time, self._end_time, step)
        pair = self._satellite - self._groundstation
        for t in times:
            altitude, azimuth, _range = pair.at(t).altaz()
            yield {
                "time": tt_iso(t),
                "azimuth": azimuth.degrees,
                "altitude": altitude.degrees,
                "range": _range.km,
            }

    @staticmethod
    def _find_boundary(sat, gs, t, step, turn_around_when, stop_when):
        """
        adds step to t unit `turn_around_when` returns true, then flips and
          halves step until .
        Finds the boundary where alt crosses cutoff within sigma
        The initial step dictates the direction of the cutoff
          for example, if it is positive then we are looking for pass-end
          if it is negative, then we are looking for pass-start

        Takes:
          sat - a Satellite
          gs - a GroundStation
          t - a Time() that exists within an access
          step - seconds to add to t (sign of step dictates the direction)
        """
        # XXX This can probably be optimized significantly
        horizon_mask = gs.horizon_mask
        pair = sat._vec - gs._vec

        def _recurse(t, step, alt, azi):
            stop = stop_when(sat, gs, alt, azi, step)
            if stop:
                return AltAz(t, alt, azi)

            measure = add_seconds(t, step)
            alt_next, azi_next, _ = pair.at(measure).altaz()

            turnaround = turn_around_when(sat, gs, alt, alt_next, azi, azi_next)
            if turnaround:
                return _recurse(measure, -step / 2, alt_next, azi_next)
            return _recurse(measure, step, alt_next, azi_next)

        alt, azi, _ = pair.at(t).altaz()
        cutoff = horizon_mask[int(azi.degrees)]
        if alt.degrees <= cutoff:
            return RuntimeError("Initial time must be during a pass")
        return _recurse(t, step, alt, azi)

    @property
    def satellite(self):
        return self._satellite

    @property
    def groundstation(self):
        return self._groundstation

    @property
    def max_alt(self):
        return round(self._max_alt, 3)

    @staticmethod
    def _find_cutoff(sat, gs, t, step, sigma=0.01):
        def crosses_zero(sat, gs, alt, alt_next, azi, azi_next):
            cutoff = gs.horizon_mask[int(azi.degrees)]
            return ((alt_next.degrees - cutoff) * (alt.degrees - cutoff)) < 0

        def alt_is_close_to_cutoff(sat, gs, alt, azi, step):
            cutoff = gs.horizon_mask[int(azi.degrees)]
            return abs(alt.degrees - cutoff) < sigma

        return Access._find_boundary(
            sat, gs, t, step, crosses_zero, alt_is_close_to_cutoff
        ).time

    @staticmethod
    def is_above_horizon(sat, gs, t):
        pair = sat._vec - gs._vec
        alt, azi, _ = pair.at(t).altaz()
        cutoff = gs.horizon_mask[int(azi.degrees)]
        return alt.degrees > cutoff

    @staticmethod
    def find_start(sat, gs, t, sigma=0.01):
        return Access._find_cutoff(sat, gs, t, -60, sigma)

    @staticmethod
    def find_end(sat, gs, t, sigma=0.01):
        return Access._find_cutoff(sat, gs, t, 60, sigma)

    @staticmethod
    def find_max_alt(sat, gs, t, sigma=0.1):
        def alt_is_lower(sat, gs, alt, alt_next, azi, azi_next):
            return alt_next.degrees < alt.degrees

        def step_is_small(sat, gs, alt, azi, step):
            return abs(step) < sigma

        return Access._find_boundary(
            sat, gs, t, 60, alt_is_lower, step_is_small
        ).altitude.degrees

    def to_dict(self):
        return {
            "id": self.access_id,
            "satellite": self.satellite.hwid,
            "groundstation": self.groundstation.hwid,
            "start_time": tt_iso(self.start_time),
            "end_time": tt_iso(self.end_time),
            "max_alt": self.max_alt,
            "_href": urljoin(
                self._base_url,
                "v0/accesses/{access_id}/".format(access_id=self.access_id),
            ),
            "_track": urljoin(
                self._base_url,
                "v0/accesses/{access_id}/track/".format(access_id=self.access_id),
            ),
        }

    def __repr__(self):
        return (
            "<Access: ({satellite}, {groundstation})"
            " ({start_time}, {end_time})"
            " ({max_alt} deg)>"
        ).format(**self.to_dict())


def _find_accesses_wrapper(args):
    """Wrapper to unpack args tuple
    Needed because multiprocessing passes args as a tuple
    """
    return _find_accesses(*args)


def _find_accesses(sat, gs, start, end, ts):
    """finds a single timestamp from each access in the provided time
    window.
    """
    pair = gs.observe(sat)

    def f(t, use_horizonmask=True):
        """function to maximize"""

        def _get_horizon(az_deg):
            return gs.horizon_mask[int(az_deg)]

        get_horizon = vectorize(_get_horizon)

        t = ts.tai(jd=t)
        alt, az, distance = pair.at(t).altaz()
        if use_horizonmask:
            horizon = get_horizon(az.degrees)
            return alt.degrees - horizon
        return alt.degrees

    def minusf(t):
        """function to minimize"""
        return -f(t)

    t0 = start.tai
    orbit_period_per_minute = TAU / sat._vec.model.no
    orbit_period = orbit_period_per_minute / 24.0 / 60.0
    step = orbit_period / 6.0

    t = arange(start.tai - step, end.tai + (2 * step), step)
    deg_above_cutoff = f(t)
    left_diff = ediff1d(deg_above_cutoff, to_begin=0.0)
    right_diff = ediff1d(deg_above_cutoff, to_end=0.0)
    maxima = (left_diff > 0.0) & (right_diff < 0.0)

    def find_highest(t):
        result = optimize.minimize_scalar(
            minusf, bracket=[t + step, t, t - step], tol=JD_SEC / t
        )
        return result.x

    t_highest = [find_highest(ti) for ti in t[maxima]]
    dt_highest = ts.tai(jd=t_highest)

    def find_rising(t):
        """Provide a moment of maximum altitude as `t`."""
        rising = optimize.brentq(f, t - 2 * step, t)
        return rising

    def find_setting(t):
        """Provide a moment of maximum altitude as `t`."""
        setting = optimize.brentq(f, t + 2 * step, t)
        return setting

    passes = [ti for ti in t_highest if f(ti) > 0.0]

    dt_passes = ts.tai(jd=passes)
    max_alts = [f(ti, use_horizonmask=False) for ti in passes]

    t_rising = [find_rising(ti) for ti in passes]
    dt_rising = ts.tai(jd=t_rising)

    t_setting = [find_setting(ti) for ti in passes]
    dt_setting = ts.tai(jd=t_setting)

    zipped = zip(dt_rising, dt_setting, max_alts)
    return sat, gs, zipped


class AccessCalculator(object):
    timescale = load.timescale(builtin=True)

    def __init__(self, base_url=""):
        self._base_url = base_url

    @classmethod
    def calculate_accesses(
        cls,
        satellites,
        groundstations,
        start_time=None,
        end_time=None,
        filter_func=None,
    ):
        """calculates all of the access between a given list of satellites
        and groundstations over the range between start_time and end_time.

        If no times are given, then the default propagation window is from
        "now" until two days from now

        filter_func allows you to pass in a function to filter out bad
        accesses.
        """
        try:
            base_url = request.url_root
        except RuntimeError:
            base_url = ""

        start_time, end_time = get_default_range(start_time, end_time)

        accesses = []
        pairs = []
        for sat, gs in product(satellites, groundstations):
            pairs += [(sat, gs, start_time, end_time, cls.timescale)]

        with ProcessPoolExecutor() as executor:
            for sat, gs, access_times in executor.map(_find_accesses_wrapper, pairs):
                accesses += [
                    Access(t_start, t_end, sat, gs, max_alt, base_url=base_url)
                    for t_start, t_end, max_alt in access_times
                ]

        if filter_func is not None and accesses:
            accesses = filter(filter_func, accesses)

        return sorted(accesses, key=lambda a: a.start_time.tt)


def search(
    limit=100,
    range_start=None,
    range_end=None,
    range_inclusive="both",
    satellites=None,
    groundstations=None,
):

    # TODO pagination
    # This could be done with a next header, where range_start is the end_time
    # of the last access returned previously, and range_inclusive is set to
    # 'end' so that we don't return any accesses twice

    if satellites is None:
        sats = list(Satellite.objects.all())
    else:
        sats = list(Satellite.objects.filter(hwid__in=satellites))

    if groundstations is None:
        gss = list(GroundStation.objects.all())
    else:
        gss = list(GroundStation.objects.filter(hwid__in=groundstations))

    base_url = request.url_root
    ac = CachedAccessCalculator(base_url=base_url)
    timescale = ac.timescale

    range_start, range_end = get_default_range(range_start, range_end)
    accesses = ac.calculate_accesses(
        sats, gss, start_time=range_start, end_time=range_end, limit=limit
    )
    accesses = filter_range(accesses, range_start, range_end, range_inclusive)

    return [
        access.to_dict() for access in sorted(accesses, key=lambda a: a.start_time.tt)
    ][:limit]


def get_access(access_id):
    base_url = request.url_root
    access = Access.from_id(access_id, base_url=base_url)
    return access.to_dict()


def get_track(access_id, step=DEF_STEP_S):
    base_url = request.url_root
    accepts = request.headers.get("accept", "")
    access = Access.from_id(access_id, base_url=base_url)

    return get_track_file(access, step=step)


class CachedAccessCalculator(AccessCalculator):
    @staticmethod
    def _sat_gs_vector_hash(tle1, tle2, lat, lon, el, horizon_mask):
        """returns a hash that matches on TLE and GS location and horizon mask"""
        to_hash = [tle1, tle2, round(lat, 6), round(lon, 6), round(el, 6)]
        to_hash += horizon_mask
        to_hash = str(to_hash)
        return hashlib.md5(to_hash.encode()).hexdigest()

    @classmethod
    def _cached_pair_compute(cls, sat, gs, tbucket):
        """computes accesses for a given (sat,gs) pair on a given tbucket
        (julian day), and caches the results.
        returns cached results if they are available.
        """
        start = cls.timescale.tai(jd=int(tbucket))
        end = cls.timescale.tai(jd=int(tbucket) + 1)

        tle1, tle2 = sat.tle
        bucket_hash = (
            cls._sat_gs_vector_hash(
                tle1, tle2, gs.latitude, gs.longitude, gs.elevation, gs.horizon_mask
            )
            + "@"
            + str(start)
            + "-"
            + str(end)
        )

        cached = CachedAccess.objects.filter(bucket_hash=bucket_hash).exists()
        if not cached:
            # compute accesses
            sat, gs, found = _find_accesses(sat, gs, start, end, cls.timescale)
            accesses_to_cache = [
                Access(rising, setting, sat, gs, max_alt)
                for rising, setting, max_alt in found
                if start.tai <= rising.tai < end.tai
            ]
            if not accesses_to_cache:
                # create placeholder object to store empty range
                CachedAccess.objects.update_or_create(
                    bucket_hash=bucket_hash,
                    defaults={
                        "satellite": sat,
                        "groundstation": gs,
                        "placeholder": True,
                    },
                )
            for bucket_index, access in enumerate(accesses_to_cache):
                CachedAccess.objects.update_or_create(
                    bucket_hash=bucket_hash,
                    bucket_index=bucket_index,
                    defaults={
                        "satellite": sat,
                        "groundstation": gs,
                        "start_time": tt_iso(access.start_time),
                        "end_time": tt_iso(access.end_time),
                        "max_alt": access.max_alt,
                        "placeholder": False,
                    },
                )

        cached = CachedAccess.objects.filter(bucket_hash=bucket_hash).all()

        # dont' return placeholder windows
        return [ca.to_access() for ca in cached if not ca.placeholder]

    @classmethod
    def _chunked_compute(cls, sats, gss, range_start, range_end, limit=100):
        """breaks up time range into chunks, and computes one chunk at a time"""
        bucket_start = int(math.floor(range_start.tai))
        bucket_end = int(math.ceil(range_end.tai))

        accesses = []
        for bucket in range(bucket_start, bucket_end):
            for sat, gs in product(sats, gss):
                new = cls._cached_pair_compute(sat, gs, bucket)
                new = filter(lambda a: a.end_time.tai >= range_start.tai, new)
                new = filter(lambda a: a.start_time.tai <= range_end.tai, new)
                accesses += new
            if len(accesses) > limit:
                break
        return accesses

    @classmethod
    def calculate_accesses(
        cls,
        satellites,
        groundstations,
        start_time=None,
        end_time=None,
        filter_func=None,
        limit=100,
    ):
        """calculates all of the access between a given list of satellites
        and groundstations over the range between start_time and end_time.

        If no times are given, then the default propagation window is from
        "now" until two days from now

        filter_func allows you to pass in a function to filter out bad
        accesses.
        """
        try:
            base_url = request.url_root
        except RuntimeError:
            base_url = ""

        start_time, end_time = get_default_range(start_time, end_time)

        accesses = cls._chunked_compute(
            satellites, groundstations, start_time, end_time, limit=limit
        )

        if filter_func is not None and accesses:
            accesses = filter(filter_func, accesses)

        return sorted(accesses, key=lambda a: a.start_time.tt)
