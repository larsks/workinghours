from dataclasses import dataclass

NAMED_DAYS: dict[str, set[int]] = {
    "weekdays": {1, 2, 3, 4, 5},
    "weekend": {0, 6},
}

ALL_DAYS = set(range(7))


@dataclass
class DayFilter:
    days: set[int]
    negated: bool


def parse_days(s: str) -> DayFilter:
    """Parse a day specification string.

    Supports cron-style day numbers (0=Sunday, 7=Sunday), ranges,
    named groups (weekdays, weekend), and negation via ``!`` prefix.
    """
    negated = s.startswith("!")
    raw = s[1:] if negated else s

    days: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        if part in NAMED_DAYS:
            days |= NAMED_DAYS[part]
        elif "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2:
                raise ValueError(f"Invalid day range {part!r}. Expected N-N.")
            try:
                start = int(bounds[0])
                end = int(bounds[1])
            except ValueError:
                raise ValueError(f"Invalid day range {part!r}. Expected N-N.")
            if not (0 <= start <= 7 and 0 <= end <= 7):
                raise ValueError(
                    f"Day numbers must be 0-7 (0=Sunday, 7=Sunday), got {part!r}."
                )
            if start > end:
                raise ValueError(f"Invalid day range {part!r}. Start must be <= end.")
            for d in range(start, end + 1):
                days.add(d % 7)
        else:
            try:
                day = int(part)
            except ValueError:
                raise ValueError(
                    f"Unknown day {part!r}. Use 0-7 or: {', '.join(NAMED_DAYS)}."
                )
            if not (0 <= day <= 7):
                raise ValueError(
                    f"Day numbers must be 0-7 (0=Sunday, 7=Sunday), got {day}."
                )
            days.add(day % 7)

    if not days:
        raise ValueError("No days specified.")

    return DayFilter(days=days, negated=negated)


def combine_day_filters(filters: list[DayFilter]) -> set[int]:
    """Combine multiple day filters into a set of allowed cron-style days.

    Inclusive filters are unioned.  Exclusive filters are unioned then
    complemented.  Mixing inclusive and exclusive is an error.
    """
    if not filters:
        raise ValueError("At least one day filter must be specified.")

    types = {f.negated for f in filters}
    if len(types) > 1:
        raise ValueError(
            "Cannot mix inclusive and exclusive day filters. "
            "All --days values must use ! (exclusive) or none must."
        )

    negated = filters[0].negated
    combined: set[int] = set()
    for f in filters:
        combined |= f.days

    return ALL_DAYS - combined if negated else combined
