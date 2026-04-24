# workinghours modernization design

**Date:** 2026-04-23

## Overview

Replace the two-script pipeline (`workinghours.py | workinghours-apply`) with a single unified Python 3 tool managed by `uv`. The core behavioral change is replacing `git filter-branch` (deprecated) with `git_filter_repo` as a library. The CLI is redesigned for clarity, and the drift model is replaced with a mathematically principled soft-boundary approach.

## Project structure

```
workinghours/
├── pyproject.toml          # uv project config, dependencies, script entry point
├── src/
│   └── workinghours.py     # unified implementation
└── tests/
    └── test_workinghours.py
```

Files removed: `workinghours.py` (root), `workinghours-apply`.

Install locally with `uv tool install .` or run directly with `uv run workinghours`.

## CLI

```
workinghours [--interval INTERVAL] [--repo PATH] [--plan] [--strict] [--softness HOURS] [revspec]
```

| Flag | Default | Description |
|---|---|---|
| `--interval INTERVAL` | `workhours` | Target interval (see below) |
| `--repo PATH` | `.` | Path to git repository |
| `--plan` | off | Print plan to stdout; do not rewrite history |
| `--strict` | off | Hard boundaries — no drift outside the target window |
| `--softness HOURS` | `1.0` | Decay rate for soft boundaries (ignored with `--strict`) |
| `revspec` | `HEAD` | Commit range to rewrite (e.g. `HEAD~10..HEAD`) |

### Interval syntax

`--interval` accepts a single string in one of four forms:

| Value | Meaning |
|---|---|
| `workhours` | 9:00–17:00 local time (the default) |
| `!workhours` | Outside 9:00–17:00 |
| `HH:MM-HH:MM` | Custom range |
| `!HH:MM-HH:MM` | Outside a custom range |

The `!` prefix negates: commits should fall *outside* the specified window. Midnight-spanning ranges are supported (e.g. `20:00-02:00`).

## Architecture: three phases

### Phase 1 — Plan generation

1. Resolve `revspec` to a commit range using `pygit2`.
2. Walk commits from newest to oldest, batching by calendar day.
3. For each day's batch, assign timestamps by sampling from the day's PDF (see Drift model below), then sort to preserve intra-day commit ordering.
4. Produce a `dict[str, datetime]` mapping commit ID → new timestamp.

### Phase 2 — Application

Pass the plan to `git_filter_repo` via a commit callback. For each commit:
- If the commit's original ID is in the plan, set `author_date` and `committer_date` to the planned timestamp.
- Otherwise, leave the commit unchanged (handles partial revspec rewrites).

### Phase 3 — Dry-run (`--plan`)

Print the plan to stdout as `<commit-id> <ISO-8601-timestamp>` lines instead of applying it. Format is compatible with the old `workinghours-apply` if needed.

## Interval logic

A **positive** interval (e.g. `workhours`, `12:00-16:00`) defines a single contiguous window. The target PDF is high within this window.

A **negated** interval (e.g. `!workhours`) defines the complement: the portions of the day *outside* the specified range. For a normal range like `09:00-17:00`, the complement is two windows: `[00:00, 09:00)` and `[17:00, 24:00)`. For a midnight-spanning range like `20:00-02:00`, the complement is a single contiguous window: `[02:00, 20:00)`.

## Drift model

Commits are sampled from a probability density function (PDF) over 24 hours, discretized into minute-resolution buckets.

**PDF shape:**
- Within the target window(s): `pdf(t) = 1`
- Outside the target window(s): `pdf(t) = exp(-d(t) / softness)`, where `d(t)` is the distance in hours from `t` to the nearest window boundary.

**Sampling:**
1. Normalize the PDF to sum to 1.
2. Compute the cumulative distribution function (CDF).
3. Sample uniformly from [0, 1] and apply the inverse CDF to get a time-of-day offset in minutes.
4. Add the sampled offset to midnight of the commit's original date.
5. Sort samples within each day batch (descending) to preserve relative commit ordering.

**Parameters:**
- `--softness HOURS` (default `1.0`): controls the exponential decay rate. Higher values → wider soft zone. A commit 1 h inside the excluded zone has ~37% the probability of one at the boundary; 2 h in has ~14%.
- `--strict`: equivalent to setting PDF to 0 outside the target window (hard cutoff). Overrides `--softness`.

## Dependencies

- `pygit2` — commit walking, revspec resolution
- `git-filter-repo` — history rewriting (used as a Python library: `import git_filter_repo`)

Dev/test:
- `pytest`

## Error handling

| Condition | Behavior |
|---|---|
| Invalid `--interval` format | Clear error with expected formats |
| Unrecognized named interval | Error listing valid names |
| Negative `--softness` | Rejected with error |
| Revspec does not resolve | `pygit2` exception caught, re-raised with clean message |
| `git_filter_repo` not importable | Tell user to install `git-filter-repo` |
| Repository has uncommitted changes | `git_filter_repo` enforces this; error surfaced cleanly |

## Testing

All tests use `pytest`.

| Test area | What is verified |
|---|---|
| Interval parsing | All four forms; midnight-spanning ranges; invalid inputs rejected |
| Negation logic | Complement windows are correct for both normal and midnight-spanning intervals |
| PDF generation | Values within the window ≥ values outside; `--strict` gives 0 outside; softness parameter changes shape |
| Commit batching | Commits are grouped by calendar day; intra-day ordering is preserved |
| Timestamp assignment (`--strict`) | All assigned times fall within the target window |
| Timestamp assignment (soft) | Distribution of samples matches expected exponential falloff statistically |
