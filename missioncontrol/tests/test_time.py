import json
import pytest
from skyfield.api import Loader
from django.conf import settings

load = Loader(settings.EPHEM_DIR)

from v0.time import filter_range

class Window(object):
    ts = load.timescale()

    def __init__(self, start_time, end_time):
        self.start_time = self.ts.utc(start_time)
        self.end_time = self.ts.utc(end_time)

windows = [
    Window(2018, 2019),
    Window(2019, 2020),
    Window(2020, 2021),
    Window(2021, 2022)
]

@pytest.mark.parametrize("windows,range_inclusive,expected", [
    (windows, "both", windows),
    (windows, "start", windows[:-1]),
    (windows, "end", windows[1:]),
    (windows, "neither", windows[1:-1])
])
def test_filter_range_inclusive_both(windows, range_inclusive, expected):
    ts = load.timescale()
    range_start = ts.utc(2019)
    range_end = ts.utc(2021)
    filtered = list(filter_range(windows, range_start, range_end, range_inclusive))
    assert filtered == expected
