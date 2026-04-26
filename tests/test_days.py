import pytest

from workinghours.days import combine_day_filters, parse_days


# --- parse_days ---


def test_single_day():
    df = parse_days("1")
    assert df.days == {1}
    assert df.negated is False


def test_sunday_zero():
    df = parse_days("0")
    assert df.days == {0}


def test_sunday_seven():
    df = parse_days("7")
    assert df.days == {0}


def test_comma_separated():
    df = parse_days("1,3,5")
    assert df.days == {1, 3, 5}
    assert df.negated is False


def test_range():
    df = parse_days("1-5")
    assert df.days == {1, 2, 3, 4, 5}


def test_range_including_seven():
    df = parse_days("5-7")
    assert df.days == {5, 6, 0}


def test_named_weekdays():
    df = parse_days("weekdays")
    assert df.days == {1, 2, 3, 4, 5}
    assert df.negated is False


def test_named_weekend():
    df = parse_days("weekend")
    assert df.days == {0, 6}
    assert df.negated is False


def test_mixed_named_and_numbers():
    df = parse_days("weekend,3,4")
    assert df.days == {0, 3, 4, 6}


def test_mixed_named_and_range():
    df = parse_days("weekend,1-3")
    assert df.days == {0, 1, 2, 3, 6}


def test_negated_range():
    df = parse_days("!1-3")
    assert df.days == {1, 2, 3}
    assert df.negated is True


def test_negated_named():
    df = parse_days("!weekend")
    assert df.days == {0, 6}
    assert df.negated is True


def test_negated_comma_separated():
    df = parse_days("!0,6")
    assert df.days == {0, 6}
    assert df.negated is True


def test_range_with_commas():
    df = parse_days("0-4,6")
    assert df.days == {0, 1, 2, 3, 4, 6}


def test_invalid_day_number():
    with pytest.raises(ValueError, match="0-7"):
        parse_days("8")


def test_invalid_range_start_gt_end():
    with pytest.raises(ValueError, match="Start must be <= end"):
        parse_days("5-2")


def test_invalid_range_too_many_parts():
    with pytest.raises(ValueError, match="Expected N-N"):
        parse_days("1-3-5")


def test_invalid_range_non_numeric():
    with pytest.raises(ValueError, match="Expected N-N"):
        parse_days("a-b")


def test_unknown_name():
    with pytest.raises(ValueError, match="Unknown day"):
        parse_days("holidays")


def test_empty_string():
    with pytest.raises(ValueError, match="No days specified"):
        parse_days("")


# --- combine_day_filters ---


def test_combine_single_inclusive():
    df = parse_days("weekdays")
    assert combine_day_filters([df]) == {1, 2, 3, 4, 5}


def test_combine_single_exclusive():
    df = parse_days("!weekend")
    assert combine_day_filters([df]) == {1, 2, 3, 4, 5}


def test_combine_multiple_inclusive():
    df1 = parse_days("1,2")
    df2 = parse_days("4,5")
    assert combine_day_filters([df1, df2]) == {1, 2, 4, 5}


def test_combine_multiple_exclusive():
    df1 = parse_days("!1,2")
    df2 = parse_days("!3")
    assert combine_day_filters([df1, df2]) == {0, 4, 5, 6}


def test_combine_mixed_raises():
    df1 = parse_days("weekdays")
    df2 = parse_days("!weekend")
    with pytest.raises(ValueError, match="mix"):
        combine_day_filters([df1, df2])


def test_combine_empty_raises():
    with pytest.raises(ValueError):
        combine_day_filters([])
