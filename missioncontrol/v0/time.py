from copy import copy
from datetime import datetime
from pytz import UTC
from dateutil.parser import parse
from dateutil.tz import tzutc
from skyfield.api import Time


def utc(t):
    """ do whatever it takes to make time into datetime
    """
    # get datetime
    if isinstance(t, datetime):
        pass
    elif t == "now":
        t = datetime.utcnow()
    elif isinstance(t, str):
        t = parse(t)
    elif isinstance(t, tuple):
        t = datetime(*t)
    elif isinstance(t, Time):
        t = t.utc_datetime()

    # ensure UTC
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    if t.tzname() != "UTC":
        raise ValueError(f"Non-UTC timezones ({t}, {t.tzname()}) are not supported.")

    return t
