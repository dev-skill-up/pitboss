"""The sentences of the briefs about the ticket's Done-when (pitboss#396).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change. A brief offers no hand-back route for a Done-when: the
only text about handing back a ticket is the dependency on another open ticket
(``brieftextwork.DEPENDENCY``).
"""

RULE = "meet the Done-when as written, or prove it impossible"
ONE_PR = f"One PR: do the whole ticket in one PR and split nothing yourself: {RULE}."
DONE_WHEN = (
    "Done-when: read the Done-when in the body of the ticket {read}; only the body"
    " has it, and a comment adds nothing to it. Copy each of its bullets word for"
    " word into a numbered Plan row of its own, with the exact evidence command"
    " (a measurement it names is the one the row runs, never a substitute); never"
    f" narrow it or offer an alternative: {RULE}."
)
DONE_WHEN_DIGEST = (
    "Done-when digest: the PR body has the line `Done-when digest:"
    " {done_when_digest}`, the digest of the ticket's Done-when as it is now;"
    " `pitboss plan-check` refuses a body whose line is not the ticket's digest,"
    " which is how a Done-when edited after a worker started is found."
)


def plan_digest_line(digest: str) -> str:
    """The words that name the Plan digest line of a brief.

    Args:
        digest: the digest of the body's Plan section, empty when it has none.

    Returns:
        The line to add, or the statement that the body has no Plan section.
    """
    if digest:
        return f"the line `Plan digest: {digest}`"
    return "no `Plan digest:` line (the body has no `## Plan` section)"
