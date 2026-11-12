"""GitHub as the act verbs see it: one port with one write (keyword: act-verbs).

``acthub`` is the port on GitHub and a test's fake is another; ``actcore`` runs the
verbs against either.
"""

import dataclasses
from typing import Callable, Mapping, Sequence

Pull = dict[str, object]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Change:
    """One write to GitHub.

    Attributes:
        kind: what is written (``merge``, ``comment``, ``issue`` ...).
        repo: the repository.
        number: the PR or issue (0 when none).
        fields: what the write carries.
    """

    kind: str
    repo: str
    number: int = 0
    fields: Mapping[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Hub:
    """GitHub, as the verbs read and write it.

    Attributes:
        pull: reads a PR of a repository, as GitHub answers.
        timeline: reads a PR's events, oldest first.
        issues: reads a repository's open issues with a label.
        open_pulls: reads a repository's open PRs.
        write: makes one write, and gives what GitHub answered (the number of what
            was made, when it was made).
    """

    pull: Callable[[str, int], Pull]
    timeline: Callable[[str, int], Sequence[object]]
    issues: Callable[[str, str], Sequence[Pull]]
    open_pulls: Callable[[str], Sequence[Pull]]
    write: Callable[[Change], str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """What a verb acts on.

    Attributes:
        repo: the repository (``owner/name``).
        number: the PR or issue (0 when none).
    """

    repo: str
    number: int = 0
