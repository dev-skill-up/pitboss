"""The sentence of a worker brief for a project with no drafts (pitboss#216).

Like those of ``brieftext``, it is pinned by tests, so a change to it is a
reviewed code change.
"""

from .brieftext import HOLD_BUG

PUSH_HELD_READY = (
    "Push: push with `uvx pitboss push {config} --no-dry-run` (without `--draft`:"
    " this project's PRs are not drafts, and push refuses `--draft` here), after"
    " every commit. Under a hold it exits 1 and pushes nothing: hand back at once,"
    " naming where you stopped and the SHA of what is unpushed; never loop or"
    " sleep for the hold to clear. " + HOLD_BUG
)
