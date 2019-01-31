import json
import pytest

from skyfield.api import Loader
from django.conf import settings
from v0.accesses import Access

load = Loader(settings.EPHEM_DIR)
timescale = load.timescale()


def test_access_id_roundtrip():
    sat_id = 5
    gs_id = 6
    time = timescale.utc(2018, 5, 23, 1, 2, 3)
    accid = Access.encode_access_id(sat_id, gs_id, time)
    assert (sat_id, gs_id, time) == Access.decode_access_id(accid)

