import datetime
from dataclasses import dataclass

NAMED_INTERVALS: dict[str, tuple[datetime.time, datetime.time]] = {
    "workhours": (datetime.time(9, 0), datetime.time(17, 0)),
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
