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
