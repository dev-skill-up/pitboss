"""The sentence of a worker brief for a project with no drafts (pitboss#216).

Like those of ``brieftext``, it is pinned by tests, so a change to it is a
reviewed code change.
"""

from .brieftext import CI_DRAFT, HOLD_BUG, PUSH_FREE, PUSH_HELD

PUSH_HELD_READY = (
    "Push: push with `uvx pitboss push {config} --no-dry-run` (without `--draft`:"
    " this project's PRs are not drafts, and push refuses `--draft` here), after"
    " every commit. Under a hold it exits 1 and pushes nothing: hand back at once,"
    " naming where you stopped and the SHA of what is unpushed; never loop or"
    " sleep for the hold to clear. " + HOLD_BUG
)
# keyed by (holds, drafts) of the project's briefs
PUSHES = {
    (True, True): PUSH_HELD,
    (True, False): PUSH_HELD_READY,
    (False, True): PUSH_FREE,
    (False, False): PUSH_FREE,
}
CI_DRAFT_CHECK = (
    "Draft: this PR is a draft, and this repository's lint refuses an approving"
    " review of a head with no completed green `{check}` check run, draft or not,"
    " and a draft runs that job (keyword: plan-review-check, pitboss#275). Read"
    " the `{check}` check run of the head SHA above first; if it has not"
    " completed, hand back `NOT STARTED: {check} is <state>` (queued, in"
    " progress, or none) and review nothing. Read the diff and the PR body, and"
    " dry-run the Plan's commands; the other checks of a draft are not yours to"
    " wait for."
)


def draft_ci(check: str) -> str:
    """The CI sentence of the Plan review of a draft.

    Args:
        check: the check the project's lint requires before an approval, empty
            when it requires none.

    Returns:
        The sentence that says a draft runs no CI job, or, with a check, the
        one that makes the reviewer read that check run first.
    """
    return CI_DRAFT_CHECK.format(check=check) if check else CI_DRAFT
