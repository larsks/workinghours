import datetime

import pygit2
import pytest

from workinghours.heatmap import build_heatmap


@pytest.fixture
def heatmap_repo(tmp_path):
    repo = pygit2.init_repository(str(tmp_path))
    repo.config["user.name"] = "Test"
    repo.config["user.email"] = "test@example.com"
    tree_oid = repo.TreeBuilder().write()

    # Commits at known (UTC) times with known offsets so the local hour
    # and weekday are predictable:
    #
    #   2024-01-15 is a Monday.
    #   author.time + author.offset*60 → local timestamp → weekday/hour
    #
    #   Commit 0: UTC 10:30 Mon Jan 15, offset 0  → Mon 10:00 (hour slot 10)
    #   Commit 1: UTC 14:00 Mon Jan 15, offset 0  → Mon 14:00 (hour slot 14)
    #   Commit 2: UTC 09:00 Wed Jan 17, offset 0  → Wed 09:00 (hour slot 9)
    #   Commit 3: UTC 20:00 Mon Jan 15, offset +120 (UTC+2) → Mon 22:00 (hour slot 22)

    base = datetime.datetime(2024, 1, 15, 0, 0, 0, tzinfo=datetime.timezone.utc)

    entries = [
        # (UTC unix timestamp, offset in minutes)
        (
            int((base + datetime.timedelta(hours=10, minutes=30)).timestamp()),
            0,
        ),  # Mon 10:30 UTC
        (int((base + datetime.timedelta(hours=14)).timestamp()), 0),  # Mon 14:00 UTC
        (
            int((base + datetime.timedelta(days=2, hours=9)).timestamp()),
            0,
        ),  # Wed 09:00 UTC
        (
            int((base + datetime.timedelta(hours=20)).timestamp()),
            120,
        ),  # Mon 20:00 UTC + offset +120 → local 22:00
    ]

    parent: list[pygit2.Oid] = []
    for i, (ts, offset) in enumerate(entries):
        sig = pygit2.Signature("Test", "test@example.com", time=ts, offset=offset)
        oid = repo.create_commit(
            "refs/heads/master", sig, sig, f"commit {i}", tree_oid, parent
        )
        parent = [oid]
    repo.references.create("HEAD", "refs/heads/master", force=True)

    return repo


def test_build_heatmap_shape(heatmap_repo):
    matrix = build_heatmap(heatmap_repo, "HEAD")
    assert matrix.shape == (7, 24)


def test_build_heatmap_total_count(heatmap_repo):
    matrix = build_heatmap(heatmap_repo, "HEAD")
    assert matrix.sum() == 4


def test_build_heatmap_monday_slots(heatmap_repo):
    matrix = build_heatmap(heatmap_repo, "HEAD")
    monday = 0  # weekday() == 0
    # commit 0 → Mon 10:30 → slot (Mon, 10)
    assert matrix[monday, 10] == 1
    # commit 1 → Mon 14:00 → slot (Mon, 14)
    assert matrix[monday, 14] == 1
    # commit 3 → UTC+2 offset → Mon 22:00 → slot (Mon, 22)
    assert matrix[monday, 22] == 1


def test_build_heatmap_wednesday_slot(heatmap_repo):
    matrix = build_heatmap(heatmap_repo, "HEAD")
    wednesday = 2
    # commit 2 → Wed 09:00 → slot (Wed, 9)
    assert matrix[wednesday, 9] == 1


def test_build_heatmap_empty_slots_are_zero(heatmap_repo):
    matrix = build_heatmap(heatmap_repo, "HEAD")
    # No commits on Tuesday (weekday 1)
    assert matrix[1, :].sum() == 0


def test_build_heatmap_uses_author_timezone(heatmap_repo):
    # Commit 3 is at UTC 20:00 with offset +120 min (UTC+2).
    # Without the offset shift it would land in hour 20; with it, hour 22.
    matrix = build_heatmap(heatmap_repo, "HEAD")
    monday = 0
    assert matrix[monday, 20] == 0  # raw UTC hour — should NOT appear
    assert matrix[monday, 22] == 1  # offset-adjusted hour — should appear
