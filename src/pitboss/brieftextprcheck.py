"""The sentence of the Execution reviews about the repository's checklist (pitboss#438).

Like those of ``brieftext``, it is pinned by tests, so a change to it is a
reviewed code change.
"""

from collections.abc import Sequence

PRCHECK_REVIEW = (
    "Checklist: in a checkout of {repo} at the head, run `bats prcheck"
    " --checklist` and state each line of its output in the review, as"
    " `checked, ok` or as a finding."
)


def kept(lines: Sequence[str], repo: str) -> Sequence[str]:
    """The lines, without the checklist's when the repository has no ``bats prcheck``.

    Args:
        lines: the scope lines of a review brief.
        repo: the repository's ``owner/name``.

    Returns:
        The lines the brief carries; only bats-lang repositories have the command.
    """
    return [
        line
        for line in lines
        if line != PRCHECK_REVIEW or repo.startswith("bats-lang/")
    ]
