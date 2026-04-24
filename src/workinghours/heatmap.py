import argparse
import datetime
import sys

import numpy as np
import pygit2


_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_HOURS = [f"{h:02d}:00" for h in range(24)]


def build_heatmap(
    repo: pygit2.Repository,
    revspec: str,
) -> np.ndarray:
    """Return a (7, 24) matrix of commit counts indexed by [weekday, hour].

    Weekday 0 = Monday, 6 = Sunday. Times are taken from each commit's
    author date with its stored timezone offset applied, so the heatmap
    reflects when authors actually worked rather than the machine's locale.
    """
    if ".." in revspec:
        start_str, end_str = revspec.split("..", 1)
        start_oid: pygit2.Oid | None = repo.revparse_single(start_str).id
        end_oid = repo.revparse_single(end_str).id
    else:
        start_oid = None
        end_oid = repo.revparse_single(revspec).id

    matrix = np.zeros((7, 24), dtype=int)

    for commit in repo.walk(end_oid, pygit2.GIT_SORT_TOPOLOGICAL):
        if start_oid is not None and commit.id == start_oid:
            break
        # Convert UTC timestamp to the author's local time using the stored offset
        utc_dt = datetime.datetime.fromtimestamp(
            commit.author.time, tz=datetime.timezone.utc
        )
        local_dt = utc_dt + datetime.timedelta(minutes=commit.author.offset)
        matrix[local_dt.weekday(), local_dt.hour] += 1

    return matrix


def plot_heatmap(matrix: np.ndarray, output: str | None, title: str) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    # GitHub-style: light grey for zero, green gradient for activity
    colors = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
    cmap = LinearSegmentedColormap.from_list("gh_green", colors)

    fig, ax = plt.subplots(figsize=(16, 4))

    im = ax.imshow(matrix, aspect="auto", cmap=cmap, interpolation="nearest")

    ax.set_xticks(range(24))
    ax.set_xticklabels(_HOURS, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(7))
    ax.set_yticklabels(_DAYS, fontsize=9)

    # Annotate non-zero cells with their count
    max_val = matrix.max()
    for day in range(7):
        for hour in range(24):
            count = matrix[day, hour]
            if count > 0:
                # Use white text on dark cells, dark on light cells
                brightness = count / max_val if max_val > 0 else 0
                color = "white" if brightness > 0.6 else "#333333"
                ax.text(
                    hour,
                    day,
                    str(count),
                    ha="center",
                    va="center",
                    fontsize=6,
                    color=color,
                )

    fig.colorbar(im, ax=ax, label="Commits", shrink=0.8)
    ax.set_title(title, pad=10)
    ax.set_xlabel("Hour of day (author's local time)")
    ax.set_ylabel("Day of week")

    plt.tight_layout()

    if output:
        plt.savefig(output, dpi=150, bbox_inches="tight")
        print(f"Saved to {output}")
    else:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="workinghours-heatmap",
        description=(
            "Show a 7-day × 24-hour heatmap of commit activity. "
            "Each cell represents one (day-of-week, hour) slot; "
            "intensity is the number of commits in that slot."
        ),
    )
    parser.add_argument(
        "--repo",
        default=".",
        metavar="PATH",
        help="Path to git repository (default: current directory).",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Save to FILE (PNG, SVG, PDF…) instead of opening a window.",
    )
    parser.add_argument(
        "--title",
        metavar="TEXT",
        help="Override the chart title.",
    )
    parser.add_argument(
        "revspec",
        nargs="?",
        default="HEAD",
        help="Commit range to analyse (default: HEAD = all commits).",
    )
    args = parser.parse_args()

    try:
        repo = pygit2.Repository(args.repo)
    except pygit2.GitError as e:
        sys.exit(f"error: cannot open repository at {args.repo!r}: {e}")

    try:
        matrix = build_heatmap(repo, args.revspec)
    except pygit2.GitError as e:
        sys.exit(f"error: cannot resolve revspec {args.revspec!r}: {e}")

    total = int(matrix.sum())
    title = args.title or f"Commit activity — {total} commits ({args.revspec})"

    plot_heatmap(matrix, args.output, title)
