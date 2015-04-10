## Workinghours

Workinghours uses the `git filter-branch` command to make all of your
commits appear to happen within specific time intervals.

Maybe you made some commits at the last minute and you would like
people to think you had a more considered approach?  This will
distribute your commits between 9:00 and 17:00 for each day there are
commits:

    workinghours | workinghours-apply

Did you spend too much time working on personal projects during the
day and you would like to remove that evidence from your git history?
This will move all your commits to between the hours of 20:00 and
23:59:

    workinghours --afterhours | workinghours-apply

You can also provide custom intervals:

    workinghours --interval 12:00 17:00 | workinghours-apply

And you can operate on only subsets of your history:

    workinghours --afterhours 'master@{2015-02-28 00:00}..HEAD' 

Or:

    workinghours --afterhours HEAD~10..HEAD
