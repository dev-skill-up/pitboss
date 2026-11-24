"""What a FIX_CI pick's failed checks said (keyword: failure-text, #524)."""

from typing import Callable, Mapping, Sequence

from . import brief, config, failures, ghapi, headchecks, pullfacts, shapes

Say = Callable[[ghapi.GitHub, config.Repo, Sequence[shapes.CheckRun]], Sequence[str]]
SAYS: Mapping[brief.Kind, Say] = {brief.Kind.FIX_CI: failures.lines}


def of(
    github: ghapi.GitHub, pull: pullfacts.PullFacts | None, kind: brief.Kind
) -> Sequence[str]:
    """The lines a brief of a kind names the failed checks with.

    Args:
        github: the API.
        pull: the PR the pick is about, None for a ticket.
        kind: the kind of brief.

    Returns:
        A line for each failed check of a FIX_CI brief, none for any other.
    """
    say = SAYS.get(kind)
    return (
        say(github, pull.repo, headchecks.unanswered_of(pull)) if say and pull else []
    )
