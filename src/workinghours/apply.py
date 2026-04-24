import datetime
import os
import tempfile

import git_filter_repo


def apply_plan(repo_path: str, plan: dict[str, datetime.datetime]) -> None:
    repo_path = os.path.realpath(repo_path)
    old_cwd = os.getcwd()
    old_env = {}
    env_overrides = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "",
    }
    empty_config = None
    try:
        # Temporarily override git config env vars so git_filter_repo's
        # `git config --list` doesn't choke on multiline alias values in the
        # user's global config (git_filter_repo assumes every output line
        # contains exactly one '=').
        with tempfile.NamedTemporaryFile(suffix=".gitconfig", delete=False) as f:
            empty_config = f.name
        env_overrides["GIT_CONFIG_GLOBAL"] = empty_config
        for key, val in env_overrides.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = val

        os.chdir(repo_path)
        args = git_filter_repo.FilteringOptions.parse_args(["--force", "--partial"])
        repo_filter = git_filter_repo.RepoFilter(
            args, commit_callback=_make_callback(plan)
        )
        repo_filter.run()
    finally:
        os.chdir(old_cwd)
        for key, old_val in old_env.items():
            if old_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_val
        if empty_config:
            try:
                os.unlink(empty_config)
            except Exception:
                pass


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
