import datetime
import pytest
from workinghours.interval import combine_intervals, parse_interval


def test_named_workhours():
    iv = parse_interval("workhours")
    assert iv.start == datetime.time(9, 0)
    assert iv.end == datetime.time(17, 0)
    assert iv.negated is False


def test_named_workhours_negated():
    iv = parse_interval("!workhours")
    assert iv.start == datetime.time(9, 0)
    assert iv.end == datetime.time(17, 0)
    assert iv.negated is True


def test_custom_interval():
    iv = parse_interval("12:00-16:00")
    assert iv.start == datetime.time(12, 0)
    assert iv.end == datetime.time(16, 0)
    assert iv.negated is False


def test_custom_interval_negated():
    iv = parse_interval("!12:00-16:00")
    assert iv.start == datetime.time(12, 0)
    assert iv.end == datetime.time(16, 0)
    assert iv.negated is True


def test_midnight_spanning_interval():
    iv = parse_interval("20:00-02:00")
    assert iv.start == datetime.time(20, 0)
    assert iv.end == datetime.time(2, 0)
    assert iv.negated is False


def test_invalid_named_interval():
    with pytest.raises(ValueError, match="Unknown named interval"):
        parse_interval("lunchtime")


def test_invalid_custom_format():
    with pytest.raises(ValueError, match="Invalid interval"):
        parse_interval("9am-5pm")


def test_invalid_too_many_parts():
    with pytest.raises(ValueError, match="Invalid interval"):
        parse_interval("09:00-12:00-17:00")


def test_target_windows_positive():
    iv = parse_interval("09:00-17:00")
    assert iv.target_windows == [(540, 1020)]


def test_target_windows_negated():
    iv = parse_interval("!09:00-17:00")
    assert iv.target_windows == [(0, 540), (1020, 1440)]


def test_target_windows_midnight_spanning():
    # 20:00-02:00 covers [1200,1440) and [0,120)
    iv = parse_interval("20:00-02:00")
    assert iv.target_windows == [(1200, 1440), (0, 120)]


def test_target_windows_midnight_spanning_negated():
    # !20:00-02:00: complement of [1200,1440)∪[0,120) = [120,1200)
    iv = parse_interval("!20:00-02:00")
    assert iv.target_windows == [(120, 1200)]


def test_workhours_target_windows():
    iv = parse_interval("workhours")
    assert iv.target_windows == [(540, 1020)]


def test_not_workhours_target_windows():
    iv = parse_interval("!workhours")
    assert iv.target_windows == [(0, 540), (1020, 1440)]


def test_target_windows_midnight_as_end():
    # 22:00-00:00: the (0, 0) inner window is zero-width, covers only [1320, 1440)
    iv = parse_interval("22:00-00:00")
    assert iv.target_windows == [(1320, 1440), (0, 0)]


# --- combine_intervals ---


def test_combine_single_inclusive():
    # Single inclusive interval behaves identically to target_windows
    iv = parse_interval("workhours")
    assert combine_intervals([iv]) == iv.target_windows


def test_combine_single_exclusive():
    iv = parse_interval("!workhours")
    assert combine_intervals([iv]) == iv.target_windows


def test_combine_inclusive_union():
    # Two non-overlapping inclusive intervals → their union
    iv1 = parse_interval("06:00-10:00")
    iv2 = parse_interval("17:00-20:00")
    result = combine_intervals([iv1, iv2])
    assert result == [(360, 600), (1020, 1200)]


def test_combine_inclusive_overlapping():
    # Overlapping inclusive intervals are merged
    iv1 = parse_interval("06:00-12:00")
    iv2 = parse_interval("10:00-17:00")
    result = combine_intervals([iv1, iv2])
    assert result == [(360, 1020)]


def test_combine_exclusive_workhours_and_sleepytime():
    # !workhours (09:00-17:00) ∪ !sleepytime (00:00-06:00)
    # base union covers [0,360) and [540,1020)
    # complement = [360,540) and [1020,1440) → 06:00-09:00 and 17:00-24:00
    iv1 = parse_interval("!workhours")
    iv2 = parse_interval("!sleepytime")
    result = combine_intervals([iv1, iv2])
    assert result == [(360, 540), (1020, 1440)]


def test_combine_exclusive_custom():
    # !09:00-12:00 and !14:00-17:00 — avoid both lunch and afternoon
    iv1 = parse_interval("!09:00-12:00")
    iv2 = parse_interval("!14:00-17:00")
    result = combine_intervals([iv1, iv2])
    # base union: [540,720) and [840,1020)
    # complement: [0,540), [720,840), [1020,1440)
    assert result == [(0, 540), (720, 840), (1020, 1440)]


def test_combine_mixed_types_raises():
    iv1 = parse_interval("workhours")
    iv2 = parse_interval("!sleepytime")
    with pytest.raises(ValueError, match="mix"):
        combine_intervals([iv1, iv2])


def test_combine_empty_raises():
    with pytest.raises(ValueError):
        combine_intervals([])
