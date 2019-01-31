from astropy.time import Time
from datetime import datetime
from django.conf import settings
from skyfield.api import Loader

load = Loader(settings.EPHEM_DIR)

TWO_DAYS_S = 2 * 24 * 60 * 60


def timescale_functions():
    """ skyfield requires a "timescale" object that is used for things like
        leap seconds. we want to initialize it once, but avoid making it
        a global variable.
        This closure exposes two functions that rely on a global timescale,
        now : returns a Time() of the current time
        add_seconds : returns a Time() with s seconds added
    """
    timescale = load.timescale()

    def now():
        return timescale.now()

    def add_seconds(t, s):
        """
        There's no easier way to add seconds to a Time object :(
        """
        return timescale.utc(*map(sum, zip(t.utc, (0, 0, 0, 0, 0, s))))

    def utc(t):
        """ do whatever it takes to make time into skyfield
        """
        if t == "now":
            return now()
        if isinstance(t, str):
            t = timescale.from_astropy(Time(t, format='isot'))
        if isinstance(t, tuple):
            t = timescale.utc(*t)
        if isinstance(t, datetime):
            t = timescale.utc(t)
        return t
    
    def iso(t):
        t = utc(t)
        return t.utc_iso(places=6)
    
    def midpoint(start_time, end_time):
        start_time = utc(start_time)
        end_time = utc(end_time)
        mid_time = timescale.tai_jd(
            ((start_time.tai + end_time.tai) / 2)
        )
        return mid_time

    return add_seconds, now, utc, iso, midpoint


add_seconds, now, utc, iso, midpoint = timescale_functions()


def make_timeseries(start, end, step):
    """ return a list of times from start to end.
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
    """ cast to internal time, set default range_start and range_end times
    """
    if range_start is None:
        range_start = now()
    else:
        range_start = utc(range_start)
    if range_end is None:
        range_end = add_seconds(range_start, TWO_DAYS_S)
    else:
        range_end = utc(range_end)

    return range_start, range_end


def filter_range(windows, range_start, range_end, range_inclusive):
    """ given a list of time windows (object that have start and end times),
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
    if range_inclusive in ['end', 'neither']:
        windows = filter(lambda w: utc(w.start_time).tt >= range_start.tt, windows)
    else:
        windows = filter(lambda w: utc(w.end_time).tt >= range_start.tt, windows)

    # filter the end of the range
    if range_inclusive in ['start', 'neither']:
        windows = filter(lambda w: utc(w.end_time).tt <= range_end.tt, windows)
    else:
        windows = filter(lambda w: utc(w.start_time).tt <= range_end.tt, windows)

    return windows
