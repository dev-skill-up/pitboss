"""Pitboss is exempt from holds and has no drafts (keyword: pitboss-exempt).

The runner-pressure hold, the draft and the spacing of CI-triggering actions exist
for quire's runner quota (bats-lang), not for ``dev-skill-up/pitboss`` (owner,
2026-11-08T15:05Z: "PITBOSS IS NOT SUBJECT TO HOLDS", pitboss#113). A repository
is exempt when it is pitboss itself or is listed in ``[runners] exempt``; it has
no drafts when it is pitboss or listed in ``[slots.brief] no_drafts``. The module
reads no file and runs nothing: the callers give it the lists and the text of a
remote.
"""

import re
from typing import AbstractSet, Iterable, Mapping, Sequence

PITBOSS = "dev-skill-up/pitboss"
SAYING = (
    f"pitboss is exempt from holds: pushes to {PITBOSS}, and to the repositories of"
    " [runners] exempt, are never held, whatever the runner pressure"
)
SWEEP_SAYING = (
    "pitboss is exempt from holds: pushes, undrafts, enqueues and merges of"
    f" {PITBOSS}{{names}} are never held, whatever the line above says;"
    " the hold above covers the other repositories"
)
OVERRIDE = (
    "OVERRIDE: when a printed step is wrong because of a bug with an open ticket,"
    " override it on the spot, say so, and cite the ticket; the review of such a PR"
    " is one pass over the whole PR (Plan and Execution) once CI is green, not a"
    " Plan round and an Execution round"
)
OPEN_READY = "open ready: this repository has no drafts"
_REMOTE = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*://|[^/@\s]+@[^/:\s]+:)"  # a URL or an scp address
    r".*?([^/:\s]+)/([^/:\s]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def slug_of(url: str) -> str | None:
    """The ``owner/name`` a remote's URL names.

    Args:
        url: what ``git remote get-url`` printed (https, ssh or a proxy path).

    Returns:
        The slug, or None when the URL names no ``owner/name`` (a local path).
    """
    found = _REMOTE.match(url.strip())
    return f"{found.group(1)}/{found.group(2)}" if found else None


def slugs(names: Iterable[str], owner: str) -> AbstractSet[str]:
    """The repositories a list names, pitboss itself included.

    Args:
        names: the names, ``owner/name`` or a bare name.
        owner: the owner of a bare name.

    Returns:
        The slugs.
    """
    each = (one if "/" in one else f"{owner}/{one}" for one in names)
    return frozenset({PITBOSS, *each})


def owner_of(document: Mapping[str, object]) -> str:
    """The project's owner, which a bare repository name belongs to.

    Args:
        document: the parsed configuration.

    Returns:
        The owner; empty when the document names none.
    """
    project = document.get("project", {})
    return str(project.get("owner", "")) if isinstance(project, dict) else ""


def is_exempt(slug: str | None, listed: AbstractSet[str]) -> bool:
    """Whether a repository is never held.

    Args:
        slug: the repository, None when it is not known.
        listed: the exempt repositories, as ``slugs`` gives them.

    Returns:
        True for pitboss and for a listed repository.
    """
    return slug is not None and (slug == PITBOSS or slug in listed)


def others(listed: AbstractSet[str]) -> Sequence[str]:
    """The exempt repositories besides pitboss.

    Args:
        listed: the exempt repositories.

    Returns:
        Their slugs, sorted.
    """
    return sorted(listed - {PITBOSS})


def sweep_saying(listed: AbstractSet[str]) -> str:
    """The line the sweep prints under a hold.

    Args:
        listed: the exempt repositories.

    Returns:
        The line; it names the configured ones besides pitboss.
    """
    extra = others(listed)
    return SWEEP_SAYING.format(names=f" and {', '.join(extra)}" if extra else "")
