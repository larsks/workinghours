#!/usr/bin/python

import argparse
import pygit2
import time
import random
import datetime
import six

intervals = {
    'workday': (datetime.time(hour=9),
                datetime.time(hour=17)),
    'afterhours': (datetime.time(hour=19, minute=30),
                   datetime.time(hour=23, minute=59)),
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--afterhours',
                   action='store_const',
                   const='afterhours',
                   dest='interval')
    p.add_argument('--workday',
                   action='store_const',
                   const='workday',
                   dest='interval')
    p.add_argument('--interval', '-i',
                   nargs=2)
    p.add_argument('--repo', '-r',
                   default='.')
    p.add_argument('revspec')
    p.set_defaults(interval='workday')
    return p.parse_args()


def batched_commits(repo, start_cid, end_cid):
    current_day = None
    commits = []
    for commit in repo.walk(end_cid, pygit2.GIT_SORT_TOPOLOGICAL):
        when = time.localtime(commit.commit_time)

        if current_day is None:
            current_day = when

        if when.tm_yday != current_day.tm_yday:
            yield commits
            commits = []
            current_day = when

        commits.append(commit)

    yield commits
    return


def main():
    args = parse_args()

    if isinstance(args.interval, six.string_types):
        interval = intervals[args.interval]
    else:
        i_start = datetime.datetime.strptime(args.interval[0],
                                             '%H:%M').time()
        i_end = datetime.datetime.strptime(args.interval[1],
                                             '%H:%M').time()
        interval = (i_start, i_end)

    repo = pygit2.Repository(args.repo)

    if '..' in args.revspec:
        start_cid, end_cid = args.revspec.split('..')
        start_cid = repo.revparse_single(start_cid).id
        end_cid = repo.revparse_single(end_cid).id
    else:
        end_cid = repo.revparse_single(args.revspec).id
        start_cid = None

    for batch in batched_commits(repo, start_cid, end_cid):
        first_commit = datetime.datetime.fromtimestamp(
            batch[0].commit_time)

        time_start = datetime.datetime.combine(
            first_commit.date(),
            interval[0])
        time_end = datetime.datetime.combine(
            first_commit.date(),
            interval[1])

        delta = time_end-time_start

        offsets = sorted([random.uniform(0, delta.total_seconds())
                          for x in range(len(batch))],
                         reverse=True)

        for i, commit in enumerate(batch):
            when = time_start + datetime.timedelta(seconds=offsets[i])
            print commit.id, when.isoformat()


if __name__ == '__main__':
    main()