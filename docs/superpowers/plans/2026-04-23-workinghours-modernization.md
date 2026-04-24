# workinghours Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-script `workinghours.py | workinghours-apply` pipeline with a single unified `workinghours` command managed by `uv`, rewriting commit timestamps using `git_filter_repo` as a Python library instead of the deprecated `git filter-branch`.

**Architecture:** Three logical phases — plan generation (walk commits with `pygit2`, batch by day, sample timestamps from a probability density function), application (rewrite timestamps via `git_filter_repo` commit callback), and dry-run (`--plan` flag prints plan to stdout). All logic lives in `src/workinghours/`, one module per responsibility.

**Tech Stack:** Python 3.11+, `pygit2`, `git-filter-repo`, `numpy`, `pytest`, `ruff`, managed by `uv`.

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | uv project config, dependencies, script entry point |
| `src/workinghours/__init__.py` | empty |
| `src/workinghours/interval.py` | `Interval` dataclass, `NAMED_INTERVALS`, `parse_interval()`, `target_windows` property |
| `src/workinghours/pdf.py` | `build_pdf()`, `sample_times()` |
| `src/workinghours/plan.py` | `resolve_revspec()`, `batched_commits()`, `generate_plan()` |
| `src/workinghours/apply.py` | `apply_plan()` using `git_filter_repo` |
| `src/workinghours/cli.py` | `main()`, argument parsing |
| `tests/__init__.py` | empty |
| `tests/test_interval.py` | Tests for interval parsing and `target_windows` |
| `tests/test_pdf.py` | Tests for `build_pdf` and `sample_times` |
| `tests/test_plan.py` | Tests for commit batching, plan generation, and `apply_plan` |

**Deleted:** `workinghours.py` (root), `workinghours-apply`

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/workinghours/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "workinghours"
version = "0.1.0"
description = "Rewrite git commit timestamps to fall within specified time intervals"
requires-python = ">=3.11"
dependencies = [
    "pygit2",
    "git-filter-repo",
    "numpy",
]

[project.scripts]
workinghours = "workinghours.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/workinghours"]

[dependency-groups]
dev = [
    "pytest",
    "ruff",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty package and test files**

```bash
mkdir -p src/workinghours tests
touch src/workinghours/__init__.py tests/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
uv sync
```

Expected: Dependencies resolved and installed without errors. Verify with:

```bash
uv run python -c "import pygit2, git_filter_repo, numpy; print('ok')"
```

Expected output: `ok`

- [ ] **Step 4: Verify test runner**

```bash
uv run pytest
```

Expected: `no tests ran` or `collected 0 items`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "chore: set up uv project scaffold"
```

---

### Task 2: Interval parsing

**Files:**
- Create: `src/workinghours/interval.py`
- Create: `tests/test_interval.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_interval.py`:

```python
import datetime
import pytest
from workinghours.interval import parse_interval, NAMED_INTERVALS


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
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_interval.py -v
```

Expected: `ModuleNotFoundError: No module named 'workinghours.interval'`

- [ ] **Step 3: Implement `src/workinghours/interval.py`**

```python
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

    parts = raw.split("-")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid interval {s!r}. Expected HH:MM-HH:MM or one of: "
            f"{', '.join(NAMED_INTERVALS)}."
        )

    try:
        start = datetime.time.fromisoformat(parts[0])
        end = datetime.time.fromisoformat(parts[1])
    except ValueError:
        raise ValueError(
            f"Invalid interval {s!r}. Times must be in HH:MM format."
        )

    if raw not in NAMED_INTERVALS and len(parts) == 2 and "-" not in parts[0] and "-" not in parts[1]:
        pass  # valid custom interval

    return Interval(start=start, end=end, negated=negated)
```

Wait — the validation for "unknown named interval" is not correct yet: `parse_interval("lunchtime")` would split on `-` giving `["lunchtime"]` (length 1), which hits the `len(parts) != 2` branch, but the error message would say "Invalid interval" not "Unknown named interval". Fix:

```python
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

    if ":" not in raw:
        raise ValueError(
            f"Unknown named interval {raw!r}. Known intervals: "
            f"{', '.join(NAMED_INTERVALS)}."
        )

    parts = raw.split("-")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid interval {s!r}. Expected HH:MM-HH:MM."
        )

    try:
        start = datetime.time.fromisoformat(parts[0])
        end = datetime.time.fromisoformat(parts[1])
    except ValueError:
        raise ValueError(
            f"Invalid interval {s!r}. Times must be in HH:MM format."
        )

    return Interval(start=start, end=end, negated=negated)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_interval.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 5: Format and commit**

```bash
uv run ruff format src/workinghours/interval.py tests/test_interval.py
git add src/workinghours/interval.py tests/test_interval.py
git commit -m "feat: add interval parsing"
```

---

### Task 3: Target window computation

**Files:**
- Modify: `src/workinghours/interval.py` (add `target_windows` property and `_complement()`)
- Modify: `tests/test_interval.py` (add `target_windows` tests)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_interval.py`:

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_interval.py::test_target_windows_positive -v
```

Expected: `AttributeError: 'Interval' object has no attribute 'target_windows'`

- [ ] **Step 3: Add `target_windows` and `_complement` to `src/workinghours/interval.py`**

Replace the `@dataclass class Interval` block with:

```python
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
        for i in range(s, e):
            covered[i] = 1
    result: list[tuple[int, int]] = []
    start = None
    for i in range(1441):
        if i == 1440:
            if start is not None:
                result.append((start, 1440))
        elif covered[i] == 0:
            if start is None:
                start = i
        else:
            if start is not None:
                result.append((start, i))
                start = None
    return result
```

- [ ] **Step 4: Run all interval tests**

```bash
uv run pytest tests/test_interval.py -v
```

Expected: All 14 tests pass.

- [ ] **Step 5: Format and commit**

```bash
uv run ruff format src/workinghours/interval.py tests/test_interval.py
git add src/workinghours/interval.py tests/test_interval.py
git commit -m "feat: add target_windows computation"
```

---

### Task 4: PDF generation and sampling

**Files:**
- Create: `src/workinghours/pdf.py`
- Create: `tests/test_pdf.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_pdf.py`:

```python
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
    # Values just inside the window should exceed values just outside
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
    # At 60 minutes outside the boundary, probability should be ~exp(-1) of the boundary
    pdf = build_pdf([(540, 1020)], softness=1.0, strict=False)
    # softness=1.0 hour = 60 minutes; at 60 min outside, decay = exp(-60/60) = exp(-1)
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_pdf.py -v
```

Expected: `ModuleNotFoundError: No module named 'workinghours.pdf'`

- [ ] **Step 3: Implement `src/workinghours/pdf.py`**

```python
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
    return min(abs(t - s), abs(t - e))


def sample_times(pdf: np.ndarray, n: int, rng: np.random.Generator) -> list[int]:
    if n == 0:
        return []
    cdf = np.cumsum(pdf)
    samples = rng.random(n)
    return [min(int(np.searchsorted(cdf, u, side="right")), 1439) for u in samples]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_pdf.py -v
```

Expected: All 12 tests pass.

- [ ] **Step 5: Format and commit**

```bash
uv run ruff format src/workinghours/pdf.py tests/test_pdf.py
git add src/workinghours/pdf.py tests/test_pdf.py
git commit -m "feat: add PDF generation and CDF sampling"
```

---

### Task 5: Commit batching

**Files:**
- Create: `src/workinghours/plan.py`
- Create: `tests/test_plan.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_plan.py`:

```python
import datetime

import pygit2
import pytest

from workinghours.plan import batched_commits, resolve_revspec


@pytest.fixture
def test_repo(tmp_path):
    repo = pygit2.init_repository(str(tmp_path))
    repo.config["user.name"] = "Test"
    repo.config["user.email"] = "test@example.com"
    tree_oid = repo.TreeBuilder().write()

    # Two commits on day 1, one on day 2
    day1 = datetime.datetime(2024, 1, 15)
    day2 = datetime.datetime(2024, 1, 16)
    timestamps = [
        int((day1 + datetime.timedelta(hours=10)).timestamp()),
        int((day1 + datetime.timedelta(hours=11)).timestamp()),
        int((day2 + datetime.timedelta(hours=14)).timestamp()),
    ]

    parent: list[pygit2.Oid] = []
    for i, ts in enumerate(timestamps):
        sig = pygit2.Signature("Test", "test@example.com", time=ts, offset=0)
        oid = repo.create_commit(
            "refs/heads/master", sig, sig, f"commit {i}", tree_oid, parent
        )
        parent = [oid]

    return repo


def test_batched_commits_groups_by_day(test_repo):
    end_oid = test_repo.revparse_single("HEAD").id
    batches = batched_commits(test_repo, None, end_oid)
    assert len(batches) == 2
    assert len(batches[0]) == 1   # day 2 (newest, walked first)
    assert len(batches[1]) == 2   # day 1


def test_batched_commits_ordering_within_day(test_repo):
    end_oid = test_repo.revparse_single("HEAD").id
    batches = batched_commits(test_repo, None, end_oid)
    day1_batch = batches[1]
    # Walk is topological newest-first, so batch[0] is the later commit
    assert day1_batch[0].commit_time > day1_batch[1].commit_time


def test_resolve_revspec_single(test_repo):
    start_oid, end_oid = resolve_revspec(test_repo, "HEAD")
    assert start_oid is None
    assert end_oid == test_repo.revparse_single("HEAD").id


def test_resolve_revspec_range(test_repo):
    start_oid, end_oid = resolve_revspec(test_repo, "HEAD~1..HEAD")
    assert start_oid == test_repo.revparse_single("HEAD~1").id
    assert end_oid == test_repo.revparse_single("HEAD").id
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_plan.py -v
```

Expected: `ModuleNotFoundError: No module named 'workinghours.plan'`

- [ ] **Step 3: Implement `src/workinghours/plan.py` (batching only)**

```python
import datetime

import numpy as np
import pygit2

from workinghours.pdf import build_pdf, sample_times


def resolve_revspec(
    repo: pygit2.Repository, revspec: str
) -> tuple[pygit2.Oid | None, pygit2.Oid]:
    if ".." in revspec:
        start_str, end_str = revspec.split("..", 1)
        return repo.revparse_single(start_str).id, repo.revparse_single(end_str).id
    return None, repo.revparse_single(revspec).id


def batched_commits(
    repo: pygit2.Repository,
    start_oid: pygit2.Oid | None,
    end_oid: pygit2.Oid,
) -> list[list[pygit2.Commit]]:
    batches: list[list[pygit2.Commit]] = []
    current_batch: list[pygit2.Commit] = []
    current_day: datetime.date | None = None

    for commit in repo.walk(end_oid, pygit2.GIT_SORT_TOPOLOGICAL):
        day = datetime.datetime.fromtimestamp(commit.commit_time).date()

        if current_day is None:
            current_day = day

        if day != current_day:
            if current_batch:
                batches.append(current_batch)
            current_batch = []
            current_day = day

        current_batch.append(commit)

        if start_oid is not None and commit.id == start_oid:
            break

    if current_batch:
        batches.append(current_batch)

    return batches
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_plan.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 5: Format and commit**

```bash
uv run ruff format src/workinghours/plan.py tests/test_plan.py
git add src/workinghours/plan.py tests/test_plan.py
git commit -m "feat: add commit batching and revspec resolution"
```

---

### Task 6: Plan generation

**Files:**
- Modify: `src/workinghours/plan.py` (add `generate_plan`)
- Modify: `tests/test_plan.py` (add `generate_plan` tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plan.py`:

```python
import numpy as np

from workinghours.plan import generate_plan


def test_generate_plan_covers_all_commits(test_repo):
    rng = np.random.default_rng(42)
    plan = generate_plan(
        repo=test_repo,
        revspec="HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        rng=rng,
    )
    all_ids = {
        str(c.id)
        for c in test_repo.walk(
            test_repo.revparse_single("HEAD").id, pygit2.GIT_SORT_TOPOLOGICAL
        )
    }
    assert set(plan.keys()) == all_ids


def test_generate_plan_strict_times_within_window(test_repo):
    rng = np.random.default_rng(42)
    plan = generate_plan(
        repo=test_repo,
        revspec="HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        rng=rng,
    )
    for dt in plan.values():
        minutes = dt.hour * 60 + dt.minute
        assert 540 <= minutes < 1020, f"Time {dt.time()} outside window"


def test_generate_plan_preserves_date(test_repo):
    rng = np.random.default_rng(42)
    plan = generate_plan(
        repo=test_repo,
        revspec="HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        rng=rng,
    )
    original_dates = {
        str(c.id): datetime.datetime.fromtimestamp(c.commit_time).date()
        for c in test_repo.walk(
            test_repo.revparse_single("HEAD").id, pygit2.GIT_SORT_TOPOLOGICAL
        )
    }
    for cid, new_dt in plan.items():
        assert new_dt.date() == original_dates[cid]


def test_generate_plan_partial_revspec(test_repo):
    rng = np.random.default_rng(42)
    plan = generate_plan(
        repo=test_repo,
        revspec="HEAD~1..HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        rng=rng,
    )
    # Only the tip commit (HEAD) is in the range
    assert len(plan) == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_plan.py::test_generate_plan_covers_all_commits -v
```

Expected: `ImportError: cannot import name 'generate_plan' from 'workinghours.plan'`

- [ ] **Step 3: Add `generate_plan` to `src/workinghours/plan.py`**

Append to `src/workinghours/plan.py`:

```python
def generate_plan(
    repo: pygit2.Repository,
    revspec: str,
    windows: list[tuple[int, int]],
    softness: float,
    strict: bool,
    rng: np.random.Generator | None = None,
) -> dict[str, datetime.datetime]:
    if rng is None:
        rng = np.random.default_rng()

    start_oid, end_oid = resolve_revspec(repo, revspec)
    batches = batched_commits(repo, start_oid, end_oid)
    pdf = build_pdf(windows, softness=softness, strict=strict)

    plan: dict[str, datetime.datetime] = {}
    for batch in batches:
        date = datetime.datetime.fromtimestamp(batch[0].commit_time).date()
        times_minutes = sample_times(pdf, len(batch), rng)
        times_minutes.sort(reverse=True)
        for commit, minutes in zip(batch, times_minutes):
            new_dt = datetime.datetime.combine(
                date, datetime.time()
            ) + datetime.timedelta(minutes=minutes)
            plan[str(commit.id)] = new_dt

    return plan
```

- [ ] **Step 4: Run all plan tests**

```bash
uv run pytest tests/test_plan.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 5: Format and commit**

```bash
uv run ruff format src/workinghours/plan.py tests/test_plan.py
git add src/workinghours/plan.py tests/test_plan.py
git commit -m "feat: add plan generation"
```

---

### Task 7: Apply plan

**Files:**
- Create: `src/workinghours/apply.py`
- Modify: `tests/test_plan.py` (add integration test)

- [ ] **Step 1: Write failing test**

Append to `tests/test_plan.py`:

```python
from workinghours.apply import apply_plan


def test_apply_plan_rewrites_timestamps(test_repo):
    target_dt = datetime.datetime(2024, 1, 15, 10, 30)
    plan = {
        str(c.id): target_dt
        for c in test_repo.walk(
            test_repo.revparse_single("HEAD").id, pygit2.GIT_SORT_TOPOLOGICAL
        )
    }

    repo_path = test_repo.workdir.rstrip("/")
    apply_plan(repo_path, plan)

    new_repo = pygit2.Repository(repo_path)
    expected_ts = int(target_dt.timestamp())
    for commit in new_repo.walk(
        new_repo.revparse_single("HEAD").id, pygit2.GIT_SORT_TOPOLOGICAL
    ):
        assert commit.commit_time == expected_ts
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_plan.py::test_apply_plan_rewrites_timestamps -v
```

Expected: `ModuleNotFoundError: No module named 'workinghours.apply'`

- [ ] **Step 3: Implement `src/workinghours/apply.py`**

```python
import datetime
import os

import git_filter_repo


def apply_plan(repo_path: str, plan: dict[str, datetime.datetime]) -> None:
    repo_path = os.path.realpath(repo_path)
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_path)
        args = git_filter_repo.FilteringOptions.parse_args(["--force"])
        repo_filter = git_filter_repo.RepoFilter(
            args, commit_callback=_make_callback(plan)
        )
        repo_filter.run()
    finally:
        os.chdir(old_cwd)


def _make_callback(plan: dict[str, datetime.datetime]):
    def callback(commit, metadata):
        cid = commit.original_id.decode()
        if cid not in plan:
            return
        new_dt = plan[cid]
        timestamp = int(new_dt.timestamp())
        orig_tz = commit.author_date.decode().split()[-1]
        date_bytes = f"{timestamp} {orig_tz}".encode()
        commit.author_date = date_bytes
        commit.committer_date = date_bytes

    return callback
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/test_plan.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Format and commit**

```bash
uv run ruff format src/workinghours/apply.py tests/test_plan.py
git add src/workinghours/apply.py tests/test_plan.py
git commit -m "feat: add git_filter_repo-based plan application"
```

---

### Task 8: CLI

**Files:**
- Create: `src/workinghours/cli.py`

No automated tests — verified by running the tool directly.

- [ ] **Step 1: Implement `src/workinghours/cli.py`**

```python
import argparse
import sys

import pygit2

from workinghours.apply import apply_plan
from workinghours.interval import Interval, parse_interval
from workinghours.plan import generate_plan


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workinghours",
        description="Rewrite git commit timestamps to fall within specified time intervals.",
    )
    parser.add_argument(
        "--interval",
        default=None,
        metavar="INTERVAL",
        help=(
            "Target interval. Named: workhours (default), !workhours. "
            "Custom: HH:MM-HH:MM or !HH:MM-HH:MM. "
            "Prefix ! means commits fall OUTSIDE the interval."
        ),
    )
    parser.add_argument(
        "--repo",
        default=".",
        metavar="PATH",
        help="Path to git repository (default: current directory).",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print the timestamp plan to stdout without rewriting history.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Hard boundaries — no commits will fall outside the target window.",
    )
    parser.add_argument(
        "--softness",
        type=float,
        default=1.0,
        metavar="HOURS",
        help=(
            "Exponential decay rate for soft boundaries, in hours (default: 1.0). "
            "Ignored when --strict is set."
        ),
    )
    parser.add_argument(
        "revspec",
        nargs="?",
        default="HEAD",
        help="Commit range to rewrite, e.g. HEAD~10..HEAD (default: HEAD).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.softness < 0:
        parser.error("--softness must be non-negative")

    try:
        interval: Interval = (
            parse_interval(args.interval) if args.interval else parse_interval("workhours")
        )
    except ValueError as e:
        parser.error(str(e))

    try:
        repo = pygit2.Repository(args.repo)
    except pygit2.GitError as e:
        sys.exit(f"error: cannot open repository at {args.repo!r}: {e}")

    try:
        plan = generate_plan(
            repo=repo,
            revspec=args.revspec,
            windows=interval.target_windows,
            softness=args.softness,
            strict=args.strict,
        )
    except pygit2.GitError as e:
        sys.exit(f"error: cannot resolve revspec {args.revspec!r}: {e}")
    except ValueError as e:
        sys.exit(f"error: {e}")

    if args.plan:
        for cid, new_dt in plan.items():
            print(f"{cid} {new_dt.isoformat()}")
        return

    try:
        repo_path = repo.workdir.rstrip("/")
        apply_plan(repo_path, plan)
    except Exception as e:
        sys.exit(f"error: failed to apply plan: {e}")
```

- [ ] **Step 2: Verify entry point**

```bash
uv run workinghours --help
```

Expected: Help text listing all flags (`--interval`, `--repo`, `--plan`, `--strict`, `--softness`, `revspec`).

- [ ] **Step 3: Smoke test with `--plan`**

```bash
uv run workinghours --plan --strict
```

Expected: Lines of `<sha> <ISO-timestamp>` printed to stdout, all times between `09:00` and `17:00`.

- [ ] **Step 4: Smoke test with `--interval '!workhours'`**

```bash
uv run workinghours --plan --strict --interval '!workhours'
```

Expected: Lines where all times are before `09:00` or after `17:00`.

- [ ] **Step 5: Format and commit**

```bash
uv run ruff format src/workinghours/cli.py
git add src/workinghours/cli.py
git commit -m "feat: add CLI entry point"
```

---

### Task 9: Cleanup and README

**Files:**
- Delete: `workinghours.py`
- Delete: `workinghours-apply`
- Modify: `README.md`

- [ ] **Step 1: Remove old files**

```bash
git rm workinghours.py workinghours-apply
```

- [ ] **Step 2: Rewrite `README.md`**

```markdown
## Workinghours

Workinghours rewrites the timestamps of commits in a git repository so they appear to have been made within specific time intervals.

### Installation

```bash
uv tool install .
```

Or run directly without installing:

```bash
uv run workinghours
```

### Usage

Move all commits into working hours (9:00–17:00):

```bash
workinghours
```

Move all commits outside working hours:

```bash
workinghours --interval '!workhours'
```

Use a custom time interval:

```bash
workinghours --interval '12:00-16:00'
```

Use a custom interval, negated (commits fall outside noon–4pm):

```bash
workinghours --interval '!12:00-16:00'
```

Operate on a subset of history:

```bash
workinghours HEAD~10..HEAD
```

Preview the plan without rewriting:

```bash
workinghours --plan
```

Use hard boundaries (no drift outside the target window):

```bash
workinghours --strict
```

Control how far commits can drift outside the window (in hours, default 1.0):

```bash
workinghours --softness 0.5
```

### Options

| Option | Default | Description |
|---|---|---|
| `--interval INTERVAL` | `workhours` | Target interval (named or `HH:MM-HH:MM`, prefix `!` to negate) |
| `--repo PATH` | `.` | Path to git repository |
| `--plan` | off | Print plan to stdout without rewriting |
| `--strict` | off | Hard boundaries, no drift |
| `--softness HOURS` | `1.0` | Soft-boundary exponential decay rate |
| `revspec` | `HEAD` | Commit range to rewrite |
```

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass, none skipped.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "chore: remove old scripts, update README"
```

---

## Self-review

**Spec coverage:**
- ✓ Project structure with uv — Task 1
- ✓ Interval parsing (all four forms, negation, named, custom) — Tasks 2–3
- ✓ Midnight-spanning intervals and complements — Task 3
- ✓ PDF generation with exponential decay — Task 4
- ✓ CDF sampling (`sample_times`) — Task 4
- ✓ `--strict` hard cutoff — Task 4 (tested), Task 8 (CLI flag)
- ✓ `--softness` parameter — Task 4 (tested), Task 8 (CLI flag)
- ✓ Commit batching by calendar day — Task 5
- ✓ `resolve_revspec` for both single and range forms — Task 5
- ✓ `generate_plan` combining batching + sampling — Task 6
- ✓ Partial revspec (subset of history) — Task 6
- ✓ `apply_plan` via `git_filter_repo` — Task 7
- ✓ CLI with all flags — Task 8
- ✓ `--plan` dry-run output — Task 8
- ✓ Error handling (bad interval, bad repo, bad revspec) — Task 8
- ✓ Delete old files, update README — Task 9

**Type consistency:**
- `windows: list[tuple[int, int]]` — consistent across `interval.target_windows`, `build_pdf`, `generate_plan`
- `plan: dict[str, datetime.datetime]` — consistent across `generate_plan`, `apply_plan`, `cli.main`
- `rng: np.random.Generator` — consistent across `sample_times`, `generate_plan`
- `batched_commits` returns `list[list[pygit2.Commit]]` — consistent across Task 5 and Task 6 usage
