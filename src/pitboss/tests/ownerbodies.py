"""What GitHub answers about the owner's repositories, for the tests (#295)."""

from typing import Mapping


def page(path: str) -> str:
    """The path ``ghapi.pages`` asks for first (``fakes.page``, which needs no import).

    Args:
        path: the list's path.

    Returns:
        The paged path.
    """
    return f"{path}{'&' if '?' in path else '?'}per_page=100&page=1"


LISTING = page("orgs/owner/repos")
USERS_LISTING = page("users/owner/repos")
EXTRA = "repos/owner/extra"


def listing(*rows: tuple[str, bool]) -> object:
    """The owner's repositories as the API lists them.

    Args:
        *rows: each repository's ``owner/name`` and whether it is archived.

    Returns:
        The JSON.
    """
    return [{"full_name": slug, "archived": archived} for slug, archived in rows]


def listed(*more: tuple[str, bool]) -> object:
    """The project, the library and other repositories of the owner, listed.

    Args:
        *more: other repositories, with whether each is archived.

    Returns:
        The JSON.
    """
    return listing(("owner/project", False), ("owner/lib", False), *more)


def extra() -> Mapping[str, object]:
    """The repository ``extra``: not configured, and with an open PR 5.

    Returns:
        The bodies of its calls.
    """
    answers: dict[str, object] = {
        "pulls?state=open": [{"number": 5}],
        "actions/runs?event=merge_group": {"workflow_runs": []},
        "issues/comments": [],
        "pulls?state=all": [],
        "issues?state=open&labels=urgent": [],
    }
    found: dict[str, object] = {EXTRA: {}}
    found.update({page(f"{EXTRA}/{path}"): got for path, got in answers.items()})
    return found


BODIES: Mapping[str, object] = {LISTING: listed()}
