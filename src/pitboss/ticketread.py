"""Read one ticket of GitHub: its title, labels and text (pitboss#278)."""

import dataclasses
import json
import subprocess
from typing import AbstractSet

from . import ghapi


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """A ticket as ``issues/<number>`` gives it.

    Attributes:
        title: its title.
        labels: its labels.
        body: its text.
    """

    title: str
    labels: AbstractSet[str]
    body: str


def text(github: ghapi.GitHub, ticket: str) -> str | None:
    """The API's text for a ticket.

    Args:
        github: the API.
        ticket: the ticket as ``owner/name#N``.

    Returns:
        The response body; None when the API cannot give it.
    """
    slug, _, number = ticket.rpartition("#")
    try:
        return ghapi.get(github, f"repos/{slug}/issues/{number}")
    except subprocess.CalledProcessError:
        return None


def issue(github: ghapi.GitHub, ticket: str) -> Seen | None:
    """What a ticket is.

    Args:
        github: the API.
        ticket: the ticket as ``owner/name#N``.

    Returns:
        The ticket; None when the API cannot give it or it is a PR.
    """
    got = text(github, ticket)
    item: dict[str, str | list[dict[str, str]]] = json.loads(
        got or '{"pull_request": ""}'
    )
    if "pull_request" in item:
        return None
    listed = item.get("labels", [])
    names = (str(each["name"]) for each in listed if isinstance(each, dict))
    title, body = (str(item.get(key) or "") for key in ("title", "body"))
    return Seen(title=title, labels=frozenset(names), body=body)
