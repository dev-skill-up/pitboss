"""The help text that a command's docstring does not hold (keyword: command-help).

A rule the skills used to restate is stated here once, next to the code, and
``pitboss COMMAND --help`` prints it (pitboss#301).
"""

NOX = """\
The order is skills, lint and mypy (about 23 s together, and most red runs
are red there), then the tests of one Python version, which run with
virtue's -x so that the first failing test stops the run; every session
runs with -r and the first failing session stops the rest. A targeted
test module, nox -s ... or virtue is never run by hand: the whole
suite (every Python version, docs, dry_release) is CI's Run Nox step."""

NEXT = """\
The pull requests and tickets are read oldest first, and the read stops once
it holds max(5, the slots configured) decisions: an item nobody acts on now is
read past and never printed. A read that fails is tried again (at most four
tries, a wait drawn from 0 to 0.5 x 2^k seconds before try k); after the last
the command exits 1 with a READ FAILED line on standard error."""

SWEEP = """\
A PR line reads: owner/name#12 [clean] auto-merge=off pending=0
failed=[test (job 345)] queue=- review=none Title (branch). [state]
is GitHub's mergeable_state. auto-merge is whether it is armed (a
push clears it), pending the checks of the head not finished, and
failed the checks whose latest run on the head failed and that no newer
passing commit status of the head answers. queue is the state of the
PR's newest merge-queue run, - for none. review is the standing of
the newest review: approved-this-head; approved-before-merges (an
older head was approved and only merges of the base came since; never in a
gated repository); changes-needed; plan-changes-needed (the review
graded the Plan changes needed, so the only round is a revision of the
Plan); plan-approved (the Plan alone was approved, which is no approval
to merge); older-head (a fix came since: it needs a review);
older-body (the review recorded a Body: digest and the body was
fixed after it, the head not having moved); none."""

CLEAN_CONTAINER = """\
A regular file directly in --root (default /) written over --hours
(default 1) after --marker (default /container_info.json, skipped
when absent) is dead too. A path marked live is never listed: a file named
.pitboss-live in it at any depth or in a directory above it (not honored
in a merged checkout when older than 6 hours), a path of [clean] live,
the main clone, the directory the command runs in, or a tree that changed
in the idle hours. A symbolic link is never followed and a mount point never
entered; a standalone clone counts every ref (other local branches and the
stash), a worktree of another repository its HEAD. It fetches each
repository first and does not judge the checkouts of one that cannot be
fetched."""
