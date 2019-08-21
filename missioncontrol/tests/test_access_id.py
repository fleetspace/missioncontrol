import json
import pytest

from skyfield.api import Loader
from django.conf import settings
from v0.accesses import Access, filter_range

load = Loader(settings.EPHEM_DIR)
timescale = load.timescale()


def test_access_id_roundtrip():
    sat_id = 5
    gs_id = 6
    time = timescale.utc(2018, 5, 23, 1, 2, 3)
    accid = Access.encode_access_id(sat_id, gs_id, time)
    assert (sat_id, gs_id, time) == Access.decode_access_id(accid)


class Window(object):
    ts = load.timescale()

    def __init__(self, start_time, end_time):
        self.start_time = self.ts.utc(start_time)
        self.end_time = self.ts.utc(end_time)


windows = [
    Window(2018, 2019),
    Window(2019, 2020),
    Window(2020, 2021),
    Window(2021, 2022),
]


@pytest.mark.parametrize(
    "windows,range_inclusive,expected",
    [
        (windows, "both", windows),
        (windows, "start", windows[:-1]),
        (windows, "end", windows[1:]),
        (windows, "neither", windows[1:-1]),
    ],
)
def test_filter_range_inclusive_both(windows, range_inclusive, expected):
    ts = load.timescale()
    range_start = ts.utc(2019)
    range_end = ts.utc(2021)
    filtered = list(filter_range(windows, range_start, range_end, range_inclusive))
    assert filtered == expected
