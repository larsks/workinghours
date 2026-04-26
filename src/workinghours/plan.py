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
        if start_oid is not None and commit.id == start_oid:
            break

        day = datetime.datetime.fromtimestamp(commit.author.time).date()

        if current_day is None:
            current_day = day

        if day != current_day:
            if current_batch:
                batches.append(current_batch)
            current_batch = []
            current_day = day

        current_batch.append(commit)

    if current_batch:
        batches.append(current_batch)

    return batches


def _python_weekday_to_cron(weekday: int) -> int:
    return (weekday + 1) % 7


def generate_plan(
    repo: pygit2.Repository,
    revspec: str,
    windows: list[tuple[int, int]],
    softness: float,
    strict: bool,
    allowed_days: set[int] | None = None,
    rng: np.random.Generator | None = None,
) -> dict[str, datetime.datetime]:
    if rng is None:
        rng = np.random.default_rng()

    start_oid, end_oid = resolve_revspec(repo, revspec)
    batches = batched_commits(repo, start_oid, end_oid)
    pdf = build_pdf(windows, softness=softness, strict=strict)

    plan: dict[str, datetime.datetime] = {}
    for batch in batches:
        date = datetime.datetime.fromtimestamp(batch[0].author.time).date()

        if allowed_days is not None:
            cron_day = _python_weekday_to_cron(date.weekday())
            if cron_day not in allowed_days:
                continue

        times_minutes = sample_times(pdf, len(batch), rng)
        times_minutes.sort(reverse=True)
        for commit, minutes in zip(batch, times_minutes):
            new_dt = datetime.datetime.combine(
                date, datetime.time()
            ) + datetime.timedelta(minutes=minutes)
            plan[str(commit.id)] = new_dt

    return plan
