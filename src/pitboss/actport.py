"""GitHub as the act verbs see it: one port with one write (keyword: act-verbs).

``acthub`` is the port on GitHub and a test's fake is another; ``actcore`` runs the
verbs against either.
"""

import dataclasses
from typing import AbstractSet, Callable, Mapping, MutableMapping, Sequence

Pull = dict[str, object]
Options = Mapping[str, str]
HELD: Mapping[str, AbstractSet[str]] = {
    "pushes": frozenset({"push", "update-branch"}),
    "merges": frozenset({"merge", "arm"}),
    "undrafts": frozenset({"undraft"}),
    "ci": frozenset(
        {
            "push",
            "update-branch",
            "merge",
            "arm",
            "undraft",
            "rerun",
            "dispatch-workflow",
            "label",
            "pr-create",
        }
    ),
    "dispatch": frozenset({"dispatch-next"}),
}
ENDS_A_HOLD = frozenset(
    {
        "hold",
        "unhold",
        "ack",
        "disarm",
        "comment",
        "override",
        "block",
        "ticket",
        "review",
        "close",
    }
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Owner:
    """The owner's messages and their dispositions.

    Attributes:
        messages: the ids of the owner's messages, in order.
        dispositions: each answered message's disposition (``ack`` adds one).
        caps: the caps ``ack --kind cap`` set, by message, oldest first (``ack``
            adds one).
    """

    messages: Sequence[str] = ()
    dispositions: MutableMapping[str, str] = dataclasses.field(default_factory=dict)
    caps: MutableMapping[str, int] = dataclasses.field(default_factory=dict)


def cap_of(owner: Owner) -> int:
    """The cap the owner set last.

    Args:
        owner: the owner's messages.

    Returns:
        It, or 0 for the configuration's.
    """
    return list(owner.caps.values())[-1] if owner.caps else 0


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

    @property
    def name(self) -> str:
        """The PR or issue as ``owner/name#number``.

        Returns:
            The text.
        """
        return "#".join((self.repo, str(self.number)))


class Refused(Exception):
    """The verb does not write: a gate, the verdict or the form refused it."""


def option(options: Options, name: str) -> str:
    """A verb's option that must be given.

    Args:
        options: the options.
        name: the option.

    Returns:
        Its value.

    Raises:
        Refused: it is not given.
    """
    if not options.get(name):
        raise Refused(f"{name}=... is required")
    return options[name]


def options_of(options: Options, *names: str) -> Sequence[str]:
    """A verb's options that must be given.

    Args:
        options: the options.
        *names: the options, in order.

    Returns:
        Their values, in the order named.
    """
    return [option(options, name) for name in names]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Asked:
    """The verb a command line asks for, on what, with what.

    Attributes:
        verb: the verb.
        target: what it acts on.
        options: its ``name=value`` options.
    """

    verb: str
    target: Target
    options: Mapping[str, str]
