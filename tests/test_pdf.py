import numpy as np
import pytest
from workinghours.pdf import build_pdf, sample_times


def test_build_pdf_length():
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=False)
    assert len(pdf) == 1440


def test_build_pdf_sums_to_one():
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=False)
    assert abs(pdf.sum() - 1.0) < 1e-9


def test_build_pdf_window_higher_than_boundary():
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=False)
    assert pdf[540] > pdf[539]
    assert pdf[1019] > pdf[1020]


def test_build_pdf_strict_zero_outside():
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=True)
    assert pdf[:540].sum() == 0.0
    assert pdf[1020:].sum() == 0.0
    assert pdf[540:1020].sum() > 0.0


def test_build_pdf_strict_uniform_inside():
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=True)
    inside = pdf[540:1020]
    assert np.allclose(inside, inside[0])


def test_build_pdf_higher_softness_more_mass_outside():
    pdf_soft = build_pdf([(540, 1020)], softness=2.0, strict=False)
    pdf_tight = build_pdf([(540, 1020)], softness=0.5, strict=False)
    assert pdf_soft[:540].sum() > pdf_tight[:540].sum()


def test_build_pdf_exponential_decay():
    # softness=1.0 hour = 60 minutes; at 60 min outside, decay = exp(-60/60) = exp(-1)
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=False)
    ratio = pdf[479] / pdf[539]  # 479 = 60 min before boundary at 540
    assert abs(ratio - np.exp(-1)) < 0.01


def test_build_pdf_two_windows():
    pdf = build_pdf([(0, 540), (1020, 1440)], softness=1.0, strict=True)
    assert pdf[540:1020].sum() == 0.0


def test_build_pdf_empty_windows_raises():
    with pytest.raises(ValueError):
        build_pdf([], softness=1.0, strict=True)


def test_sample_times_count():
    rng = np.random.default_rng(42)
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=True)
    times = sample_times(pdf, 10, rng)
    assert len(times) == 10


def test_sample_times_strict_within_window():
    rng = np.random.default_rng(42)
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=True)
    times = sample_times(pdf, 200, rng)
    for t in times:
        assert 540 <= t < 1020, f"Time {t} outside window [540, 1020)"


def test_sample_times_empty():
    rng = np.random.default_rng(42)
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=True)
    assert sample_times(pdf, 0, rng) == []


def test_build_pdf_softness_zero_equivalent_to_strict():
    pdf_zero_softness = build_pdf([(540, 1020)], softness=0.0, strict=False)
    pdf_strict = build_pdf([(540, 1020)], softness=0.0, strict=True)
    assert np.allclose(pdf_zero_softness, pdf_strict)
