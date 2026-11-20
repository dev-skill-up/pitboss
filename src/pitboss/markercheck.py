"""The comparison of the markers pitboss prints with those the references name.

(Keyword: markup-lines, pitboss#343.) A marker in ``markers.SELF_EXPLAINED`` says
its own action in its line, so no reference has to name it; every other printed
marker must be named, and no reference may name a marker that is never printed
but a retired one (``markers.RETIRED``).
"""

from typing import AbstractSet, Sequence


def errors(
    printed: AbstractSet[str],
    self_explained: AbstractSet[str],
    named: AbstractSet[str],
    retired: AbstractSet[str] = frozenset(),
) -> Sequence[str]:
    """The disagreements between the printed markers and the named ones.

    Args:
        printed: the text of every marker pitboss prints.
        self_explained: the text of those whose line says its own action.
        named: the markers the references name.
        retired: the markers no longer printed that the references may name.

    Returns:
        One text for each marker that is printed, not self-explained and not
        named, then one for each name that is never printed.
    """
    return [
        *(
            f"marker {name!r} is not explained in the references"
            for name in sorted(printed - named - self_explained)
        ),
        *(
            f"the references name {name!r}, which pitboss never prints"
            for name in sorted(named - printed - retired)
        ),
    ]


def summary(
    printed: AbstractSet[str], self_explained: AbstractSet[str], references: int
) -> str:
    """The line the check prints when the markers agree.

    Args:
        printed: the text of every marker pitboss prints.
        self_explained: the text of those whose line says its own action.
        references: how many reference files were read.

    Returns:
        The count of all markers, of those explained in the references and of
        those explained by their own line.
    """
    own = len(self_explained)
    return (
        f"all {len(printed)} markers: {len(printed) - own} explained in"
        f" {references} references, {own} explained by their own line"
    )
