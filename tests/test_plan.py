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
