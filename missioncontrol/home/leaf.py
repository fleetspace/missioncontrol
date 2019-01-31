import json
import sys

from collections import namedtuple, Mapping
from textwrap import dedent


class LeafOptions(object):
    __slots__ = [
        "SAT", "SGS",
        "RX_FREQ", "RX_BW", "RX_MOD", "RX_POL", "RX_PROTO", "RX_FEC",
        "TX_FREQ", "TX_BW", "TX_MOD", "TX_POL", "TX_PROTO", "TX_FEC",
        "DATE", "AOS", "DT", "LOS"
    ]
    defaults = {"DT": 0.05}

    def __init__(self, **kwargs):
        self.update(dict.fromkeys(self.__slots__, ''))
        self.update(self.defaults)
        self.update(dict(**kwargs))

    def update(self, other):
        for k, v in other.items():
            setattr(self, k, v)

    def __getitem__(self, k):
        return getattr(self, k)


class LeafPassFile(object):
    header_template = dedent("""
    SAT={SAT}, SGS={SGS};
    RX_FREQ={RX_FREQ}, RX_BW={RX_BW}, RX_MOD={RX_MOD}, RX_POL={RX_POL}, RX_PROTO={RX_PROTO}, RX_FEC={RX_FEC};
    TX_FREQ={TX_FREQ}, TX_BW={TX_BW}, TX_MOD={TX_MOD}, TX_POL={TX_POL}, TX_PROTO={TX_PROTO}, TX_FEC={TX_FEC};
    DATE={DATE}, AOS={AOS}, DT={DT}, LOS={LOS};
    AZ(deg), EL(deg), SLANT(km), Doppler(Hz);
    """).strip()
    line_template = "{azimuth:.2f}, {altitude:.2f}, {range:.2f}, 0.0;"

    def __init__(self, track, leafoptions):
        self.options = leafoptions
        self.lines = []
        track = list(track)
        azs = [step["azimuth"] for step in track]
        alts = [step["altitude"] for step in track]

        # ensure track always crosses 0, and not 360
        sorted_azs = sorted(azs)
        is_contiguous = sorted_azs == azs or reversed(sorted_azs) == azs
        if not is_contiguous and max(azs) > 180.0:
            for step in track:
                if step["azimuth"] > 180.0:
                    step["azimuth"] -= 360

        self.track = track

        # normal altitude bounds set by horizon_mask
        if min(alts) < 0.0:
            msg = "Altitude ({altitude}) is out of bounds"
            raise ValueError(msg.format(azimuth=min(alts)))

        # format body lines
        self._body = [self.line_template.format(**step) for step in track]

    @property
    def header(self):
        return self.header_template.format_map(self.options)

    @classmethod
    def from_access(cls, access, leafoptions=None):
        if leafoptions is None:
            leafoptions = LeafOptions()

        dt = leafoptions.DT
        track = access.iter_track(dt)

        def _fmt_time(t):
            time_str = t.utc_iso(' ', 6)
            date, time = time_str.split(' ')
            return time[:-1]  # leave off Z

        leafoptions.update({
            "SGS": access.satellite.hwid,
            "SAT": access.satellite.catid,
            "DATE": access.start_time.utc_strftime("%y/%m/%d"),
            "AOS": _fmt_time(access.start_time),
            "LOS": _fmt_time(access.end_time)
        })
        return cls(track, leafoptions)

    def __repr__(self):
        # Yep... they need \r\n ... what even is this?
        return '\r\n'.join(self.header.splitlines() + self._body)

    @property
    def json(self):
        return json.dumps(repr(self))
