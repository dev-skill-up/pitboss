"""The ``text-lint`` commit status of a pull request event.

The reusable workflow ``.github/workflows/text-lint-check.yml`` gives
``pitboss lint event`` the ``pull_request_target`` event's file. This module
reads the pull request out of it and decides the status to post: success when
the body is in form, failure with the first finding as its description, and
success saying ``exempt`` for a relock branch and for a bot's pull request.
"""

import dataclasses
import json
from typing import Callable, Mapping, Sequence

CONTEXT = "text-lint"
DESCRIPTION_MAX = 140
RELOCK_PREFIX = "relock/"
BOT_SUFFIX = "[bot]"


class EventError(Exception):
    """The event is not a pull request event this module can read."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullRequest:
    """What the lint reads of a pull request.

    Attributes:
        body: the description, empty when it has none.
        head: the head commit's SHA.
        branch: the head branch's name.
        author: the login of who opened it.
    """

    body: str
    head: str
    branch: str
    author: str


def _status(state: str, description: str, url: str) -> Mapping[str, str]:
    return {
        "state": state,
        "context": CONTEXT,
        "description": description,
        "target_url": url,
    }


def _member(table: object, key: str) -> object:
    if not isinstance(table, Mapping) or key not in table:
        raise EventError(f"the event has no {key}")
    return table[key]


def _text(table: object, key: str) -> str:
    found = _member(table, key)
    if not isinstance(found, str):
        raise EventError(f"the event's {key} is not text")
    return found


def parse(document: str) -> PullRequest:
    """Read a pull request event.

    Args:
        document: the event's JSON.

    Returns:
        The pull request.

    Raises:
        EventError: the text is not JSON or is no pull request event.
    """
    try:
        event = json.loads(document)
    except ValueError as error:
        raise EventError(f"the event is not JSON: {error}") from error
    pull = _member(event, "pull_request")
    body = _member(pull, "body")
    if body is not None and not isinstance(body, str):
        raise EventError("the event's body is not text")
    return PullRequest(
        body=body or "",
        head=_text(_member(pull, "head"), "sha"),
        branch=_text(_member(pull, "head"), "ref"),
        author=_text(_member(pull, "user"), "login"),
    )


def _exempt(pull: PullRequest) -> bool:
    return pull.branch.startswith(RELOCK_PREFIX) or pull.author.endswith(BOT_SUFFIX)


def _ascii(finding: str) -> str:
    shown = " ".join(finding.split()).encode("ascii", "replace").decode("ascii")
    if len(shown) <= DESCRIPTION_MAX:
        return shown
    return shown[: DESCRIPTION_MAX - 3] + "..."


def decide(
    pull: PullRequest,
    url: str,
    check: Callable[[str, str], Sequence[str]],
) -> tuple[Mapping[str, str], Sequence[str]]:
    """Decide the status of a pull request.

    Args:
        pull: the pull request.
        url: the run's address, for the status.
        check: the findings of a body and its head, none when it is in form.

    Returns:
        The body of GitHub's create-a-commit-status call (``state``,
        ``context``, ``description``, ``target_url``), and all the findings
        (none for an exempt pull request).
    """
    if _exempt(pull):
        return _status("success", "exempt", url), []
    found = check(pull.body, pull.head)
    if not found:
        return _status("success", "ok", url), []
    return _status("failure", _ascii(found[0]), url), found
