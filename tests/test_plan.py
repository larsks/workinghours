import datetime

import numpy as np
import pygit2
import pytest

from workinghours.apply import apply_plan
from workinghours.plan import batched_commits, generate_plan, resolve_revspec


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

    # Set HEAD to point to master
    repo.references.create("HEAD", "refs/heads/master", force=True)

    return repo


def test_batched_commits_groups_by_day(test_repo):
    end_oid = test_repo.revparse_single("HEAD").id
    batches = batched_commits(test_repo, None, end_oid)
    assert len(batches) == 2
    assert len(batches[0]) == 1  # day 2 (newest, walked first)
    assert len(batches[1]) == 2  # day 1


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


def test_resolve_revspec_bare_ancestor(test_repo):
    start_oid, end_oid = resolve_revspec(test_repo, "HEAD~1")
    assert start_oid == test_repo.revparse_single("HEAD~1").id
    assert end_oid == test_repo.revparse_single("HEAD").id


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
        str(c.id): datetime.datetime.fromtimestamp(c.author.time).date()
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


def test_generate_plan_bare_ancestor_same_as_range(test_repo):
    rng1 = np.random.default_rng(42)
    plan_bare = generate_plan(
        repo=test_repo,
        revspec="HEAD~1",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        rng=rng1,
    )
    rng2 = np.random.default_rng(42)
    plan_range = generate_plan(
        repo=test_repo,
        revspec="HEAD~1..HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        rng=rng2,
    )
    assert plan_bare == plan_range


def test_generate_plan_uses_author_date_not_committer_date(tmp_path):
    # Regression: when committer dates are all "today" but author dates span
    # multiple days, batching must use author.time or all commits collapse to
    # the same day.
    repo = pygit2.init_repository(str(tmp_path))
    repo.config["user.name"] = "Test"
    repo.config["user.email"] = "test@example.com"
    tree_oid = repo.TreeBuilder().write()

    committer_ts = int(datetime.datetime(2024, 3, 20, 12, 0).timestamp())
    author_timestamps = [
        int(datetime.datetime(2024, 1, 10, 10, 0).timestamp()),
        int(datetime.datetime(2024, 2, 5, 14, 0).timestamp()),
        int(datetime.datetime(2024, 3, 20, 9, 0).timestamp()),
    ]

    parent: list[pygit2.Oid] = []
    for i, author_ts in enumerate(author_timestamps):
        author = pygit2.Signature("Test", "test@example.com", time=author_ts, offset=0)
        committer = pygit2.Signature(
            "Test", "test@example.com", time=committer_ts, offset=0
        )
        oid = repo.create_commit(
            "refs/heads/master", author, committer, f"commit {i}", tree_oid, parent
        )
        parent = [oid]
    repo.references.create("HEAD", "refs/heads/master", force=True)

    rng = np.random.default_rng(42)
    plan = generate_plan(
        repo=repo,
        revspec="HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        rng=rng,
    )

    expected_dates = [
        datetime.date(2024, 1, 10),
        datetime.date(2024, 2, 5),
        datetime.date(2024, 3, 20),
    ]
    plan_dates = sorted({dt.date() for dt in plan.values()})
    assert plan_dates == sorted(expected_dates), (
        f"Expected dates {sorted(expected_dates)}, got {plan_dates}. "
        "Plan is using committer date instead of author date."
    )


def test_generate_plan_allowed_days_filters_batches(tmp_path):
    # Create commits on known days:
    # 2024-01-15 = Monday (cron day 1)
    # 2024-01-16 = Tuesday (cron day 2)
    # 2024-01-17 = Wednesday (cron day 3)
    repo = pygit2.init_repository(str(tmp_path))
    repo.config["user.name"] = "Test"
    repo.config["user.email"] = "test@example.com"
    tree_oid = repo.TreeBuilder().write()

    timestamps = [
        int(datetime.datetime(2024, 1, 15, 10, 0).timestamp()),
        int(datetime.datetime(2024, 1, 16, 10, 0).timestamp()),
        int(datetime.datetime(2024, 1, 17, 10, 0).timestamp()),
    ]

    parent: list[pygit2.Oid] = []
    for i, ts in enumerate(timestamps):
        sig = pygit2.Signature("Test", "test@example.com", time=ts, offset=0)
        oid = repo.create_commit(
            "refs/heads/master", sig, sig, f"commit {i}", tree_oid, parent
        )
        parent = [oid]
    repo.references.create("HEAD", "refs/heads/master", force=True)

    rng = np.random.default_rng(42)
    plan = generate_plan(
        repo=repo,
        revspec="HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        allowed_days={1},  # Monday only
        rng=rng,
    )

    plan_dates = {dt.date() for dt in plan.values()}
    assert plan_dates == {datetime.date(2024, 1, 15)}
    assert len(plan) == 1


def test_generate_plan_allowed_days_none_includes_all(test_repo):
    rng = np.random.default_rng(42)
    plan = generate_plan(
        repo=test_repo,
        revspec="HEAD",
        windows=[(540, 1020)],
        softness=0.0,
        strict=True,
        allowed_days=None,
        rng=rng,
    )
    assert len(plan) == 3


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


def test_apply_plan_works_after_previous_run(test_repo):
    repo_path = test_repo.workdir.rstrip("/")

    first_dt = datetime.datetime(2024, 1, 15, 10, 30)
    plan1 = {
        str(c.id): first_dt
        for c in test_repo.walk(
            test_repo.revparse_single("HEAD").id, pygit2.GIT_SORT_TOPOLOGICAL
        )
    }
    apply_plan(repo_path, plan1)

    second_dt = datetime.datetime(2024, 1, 15, 14, 0)
    repo2 = pygit2.Repository(repo_path)
    plan2 = {
        str(c.id): second_dt
        for c in repo2.walk(
            repo2.revparse_single("HEAD").id, pygit2.GIT_SORT_TOPOLOGICAL
        )
    }
    apply_plan(repo_path, plan2)

    repo3 = pygit2.Repository(repo_path)
    expected_ts = int(second_dt.timestamp())
    for commit in repo3.walk(
        repo3.revparse_single("HEAD").id, pygit2.GIT_SORT_TOPOLOGICAL
    ):
        assert commit.commit_time == expected_ts
