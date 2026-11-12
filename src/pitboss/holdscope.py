"""The runner-pressure hold covers the organisations whose runners are busy.

The owner's rules (B20: "a runner-pressure hold covers pushes, merges and
dispatches in the bats-lang org"; T141, 2026-11-03T02:07Z: "holds only apply to
same-org repos") make the hold a property of the organisations that share the
runners. Another organisation's repository has its own runner budget and is
never held, whatever the pressure (keyword: hold-scope, pitboss#141). The
module reads no file and runs nothing.
"""

from typing import AbstractSet, Protocol, Sequence


class Owned(Protocol):
    """A repository, as far as the hold reads it (``config.Repo``)."""

    @property
    def owner(self) -> str:
        """Its owner.

        Returns:
            The value.
        """


class Runners(Protocol):
    """The repositories that share the runners (``config.Runners``)."""

    @property
    def repositories(self) -> Sequence[Owned]:
        """The repositories whose runs count.

        Returns:
            The value.
        """

    @property
    def held(self) -> bool:
        """Whether a ``[runners]`` table exists.

        Returns:
            The value.
        """

    @property
    def exempt(self) -> AbstractSet[str]:
        """The repositories never held.

        Returns:
            The value.
        """


OTHER_ORGANISATION = (
    "the hold covers only repositories of {orgs} (the organisations whose"
    " runners are busy): a repository of another organisation gets no hold, no"
    " draft advice and no wait line"
)
SCOPE = "the hold covers only repositories of {orgs}"
OUTSIDE = (
    "not held: {slug} is not a repository of {orgs}, whose runners are the ones"
    " under pressure"
)


def organisations(runners: Runners) -> Sequence[str]:
    """The organisations whose runners the hold is about.

    Args:
        runners: the repositories that share the runners.

    Returns:
        The owners of those repositories, sorted, each once.
    """
    return sorted({each.owner for each in runners.repositories})


def applies(runners: Runners, slug: str | None) -> bool:
    """Whether the hold applies to a repository.

    Args:
        runners: the repositories that share the runners.
        slug: the repository, None when it is not known (it is held).

    Returns:
        False without a ``[runners]`` table, for an exempt repository and for a
        repository of an organisation that does not share the runners.
    """
    if not runners.held or (slug is not None and slug in runners.exempt):
        return False
    return slug is None or slug.partition("/")[0] in organisations(runners)


def saying(runners: Runners) -> str:
    """The line that names the organisations a hold covers.

    Args:
        runners: the repositories that share the runners.

    Returns:
        The line.
    """
    return OTHER_ORGANISATION.format(orgs=", ".join(organisations(runners)))


def scope(runners: Runners) -> str:
    """The clause of the pressure line that names the organisations.

    Args:
        runners: the repositories that share the runners.

    Returns:
        The clause.
    """
    return SCOPE.format(orgs=", ".join(organisations(runners)))
