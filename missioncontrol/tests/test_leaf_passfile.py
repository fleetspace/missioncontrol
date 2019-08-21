import pytest

from home.leaf import LeafPassFile, LeafOptions


@pytest.mark.parametrize(
    "test_in, test_cmp",
    [
        ([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0]),
        ([358, 359, 0, 1, 2], [-2, -1, 0, 1, 2]),
        ([2, 1, 0, 359, 358], [2, 1, 0, -1, -2]),
        ([358, 359, 360], [358, 359, 360]),
    ],
)
def test_boundary_crossing(test_in, test_cmp):
    def _make_track_from_az_list(az_list):
        return [{"azimuth": az, "altitude": 1.0, "range": 1000.0} for az in az_list]

    track = _make_track_from_az_list(test_in)
    expected = _make_track_from_az_list(test_cmp)
    lo = LeafOptions()
    lpf = LeafPassFile(track, lo)
    assert lpf.track == expected
