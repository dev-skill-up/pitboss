"""What GitHub answers about the owner's repositories, for the tests (#295)."""

from typing import Mapping

from .. import shapes


def comment_json(posted: shapes.Comment) -> Mapping[str, str]:
    """An issue comment as the API gives it.

    Args:
        posted: the comment.

    Returns:
        Its JSON.
    """
    return {
        "body": posted.body,
        "author_association": posted.author_association,
        "created_at": posted.created_at,
        "html_url": posted.url,
    }


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
SEARCH = "search/repositories?q="
ORG_SEARCH = page(f"{SEARCH}org:owner%20archived:false")
USER_SEARCH = page(f"{SEARCH}user:owner%20archived:false")
BOUND_MESSAGE = (
    "gh: This GitHub API path is not available: sessions are bound to their"
    " configured repositories. Use repository-scoped endpoints"
    " (repos/{owner}/{repo}...)\n"
)


def searched(*rows: tuple[str, bool]) -> object:
    """The search's answer for repositories.

    Args:
        *rows: each repository's ``owner/name`` and whether it is archived.

    Returns:
        The JSON.
    """
    return {"total_count": len(rows), "items": listing(*rows)}


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
        "issues?state=all": [],
    }
    found: dict[str, object] = {EXTRA: {}}
    found.update({page(f"{EXTRA}/{path}"): got for path, got in answers.items()})
    return found


BODIES: Mapping[str, object] = {LISTING: listed()}
