import datetime
import pytest
from workinghours.interval import parse_interval


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
