import numpy as np


def build_pdf(
    windows: list[tuple[int, int]], softness: float, strict: bool
) -> np.ndarray:
    if not windows:
        raise ValueError("No target windows specified")

    pdf = np.zeros(1440, dtype=float)
    for s, e in windows:
        pdf[s:e] = 1.0

    if not strict:
        softness_minutes = softness * 60.0
        if softness_minutes > 0:
            for t in range(1440):
                if pdf[t] == 0.0:
                    d = _min_dist(t, windows)
                    pdf[t] = np.exp(-d / softness_minutes)

    total = pdf.sum()
    if total == 0.0:
        raise ValueError("PDF sums to zero — check interval configuration")
    return pdf / total


def _min_dist(t: int, windows: list[tuple[int, int]]) -> int:
    return min(_dist_to_window(t, s, e) for s, e in windows)


def _dist_to_window(t: int, s: int, e: int) -> int:
    if s <= t < e:
        return 0
    # Window is half-open [s, e): nearest boundary indices are s and e-1
    return min(abs(t - s), abs(t - (e - 1)))


def sample_times(pdf: np.ndarray, n: int, rng: np.random.Generator) -> list[int]:
    if n == 0:
        return []
    cdf = np.cumsum(pdf)
    samples = rng.random(n)
    return [min(int(np.searchsorted(cdf, u, side="right")), 1439) for u in samples]
