import datetime

import numpy as np  # noqa: F401
import pygit2

from workinghours.pdf import build_pdf, sample_times  # noqa: F401


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
