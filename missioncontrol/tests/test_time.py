import json
import pytest
import datetime
import pytz
from skyfield.api import Loader
from django.conf import settings

from v0.time import utc


def test_bad_datetime():
    est = pytz.timezone('US/Eastern')
    dt = datetime.datetime.utcnow()
    dt = est.localize(dt)
    with pytest.raises(ValueError):
        utc(dt)


def test_bad_isostring():
    with pytest.raises(ValueError):
        d = utc("2018-05-23T00:00:00+13:00")
