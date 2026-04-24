import datetime
from dataclasses import dataclass

NAMED_INTERVALS: dict[str, tuple[datetime.time, datetime.time]] = {
    "workhours": (datetime.time(9, 0), datetime.time(17, 0)),
    "sleepytime": (datetime.time(0, 0), datetime.time(6, 0)),
}


@dataclass
class Interval:
    start: datetime.time
    end: datetime.time
    negated: bool

    @property
    def target_windows(self) -> list[tuple[int, int]]:
        s = self.start.hour * 60 + self.start.minute
        e = self.end.hour * 60 + self.end.minute
        if e <= s:
            # Midnight-spanning: e.g. 20:00-02:00 → [(1200,1440),(0,120)]
            base: list[tuple[int, int]] = [(s, 1440), (0, e)]
        else:
            base = [(s, e)]
        return base if not self.negated else _complement(base)


def _complement(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    covered = bytearray(1440)
    for s, e in windows:
        covered[s:e] = b"\x01" * (e - s)
    result: list[tuple[int, int]] = []
    start = None
    for i in range(1440):
        if covered[i] == 0:
            if start is None:
                start = i
        else:
            if start is not None:
                result.append((start, i))
                start = None
    if start is not None:
        result.append((start, 1440))
    return result


def _base_windows(iv: Interval) -> list[tuple[int, int]]:
    """The raw time windows for an interval, ignoring negation."""
    s = iv.start.hour * 60 + iv.start.minute
    e = iv.end.hour * 60 + iv.end.minute
    if e <= s:
        return [(s, 1440), (0, e)]
    return [(s, e)]


def combine_intervals(intervals: list[Interval]) -> list[tuple[int, int]]:
    """Combine multiple intervals into a single list of target windows.

    All intervals must be the same type (all inclusive or all exclusive).

    Inclusive intervals are unioned: commits may fall in any of them.
    Exclusive intervals are unioned then complemented: commits must avoid
    all of them.
    """
    if not intervals:
        raise ValueError("At least one interval must be specified")

    types = {iv.negated for iv in intervals}
    if len(types) > 1:
        raise ValueError(
            "Cannot mix inclusive and exclusive intervals. "
            "All --interval values must use ! (exclusive) or none must."
        )

    negated = intervals[0].negated

    covered = bytearray(1440)
    for iv in intervals:
        for s, e in _base_windows(iv):
            covered[s:e] = b"\x01" * (e - s)

    union: list[tuple[int, int]] = []
    start = None
    for i in range(1440):
        if covered[i]:
            if start is None:
                start = i
        else:
            if start is not None:
                union.append((start, i))
                start = None
    if start is not None:
        union.append((start, 1440))

    return _complement(union) if negated else union


def parse_interval(s: str) -> Interval:
    negated = s.startswith("!")
    raw = s[1:] if negated else s

    if raw in NAMED_INTERVALS:
        start, end = NAMED_INTERVALS[raw]
        return Interval(start=start, end=end, negated=negated)

    # Check if it looks like a custom interval (has a hyphen and colons)
    if "-" in raw and ":" in raw:
        parts = raw.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid interval {s!r}. Expected HH:MM-HH:MM.")

        try:
            start = datetime.time.fromisoformat(parts[0])
            end = datetime.time.fromisoformat(parts[1])
        except ValueError:
            raise ValueError(f"Invalid interval {s!r}. Times must be in HH:MM format.")

        if (
            start.second != 0
            or start.microsecond != 0
            or end.second != 0
            or end.microsecond != 0
        ):
            raise ValueError(f"Invalid interval {s!r}. Times must be in HH:MM format.")

        return Interval(start=start, end=end, negated=negated)

    # If we reach here, it's not a valid named interval or custom format
    if "-" in raw:
        # Looks like an attempt at custom format but malformed
        raise ValueError(f"Invalid interval {s!r}. Expected HH:MM-HH:MM.")

    # Just a name without colons or hyphens
    raise ValueError(
        f"Unknown named interval {raw!r}. Known intervals: "
        f"{', '.join(NAMED_INTERVALS)}."
    )
