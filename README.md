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
