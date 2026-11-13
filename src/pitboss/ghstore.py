"""A pull request's comments and description through ``gh api`` (expand-split)."""

import functools
import json
from typing import Sequence

from . import evidencesplit, ghapi, totaljson
from .running import Run

DRY_RUN_URL = "(dry run: no URL yet)"


def made(text: str, body: str) -> evidencesplit.Comment:
    """Read the comment a call answered with.

    Args:
        text: the answer; empty in a dry run, which changed nothing.
        body: the text that was sent.

    Returns:
        The comment; one with no id in a dry run.
    """
    if not text.strip():
        return evidencesplit.Comment(number=0, url=DRY_RUN_URL, body=body)
    found = json.loads(text)
    return evidencesplit.Comment(
        number=int(found["id"]), url=str(found["html_url"]), body=body
    )


def listed(text: str) -> Sequence[evidencesplit.Comment]:
    """Read a page of comments.

    Args:
        text: the page's JSON.

    Returns:
        The comments.
    """
    return [
        evidencesplit.Comment(
            number=int(each["id"]),
            url=str(each["html_url"]),
            body=totaljson.text(each.get("body")),
        )
        for each in json.loads(text)
    ]


def send(github: ghapi.GitHub, verb: str, path: str, body: str | None) -> str:
    """Change something (only when not a dry run).

    Args:
        github: the API.
        verb: the HTTP method.
        path: the path under ``https://api.github.com/``.
        body: the ``body`` field to send; none sends no field.

    Returns:
        The answer; empty in a dry run.
    """
    fields = [] if body is None else ["-f", f"body={body}"]
    return github.mutate(["gh", "api", "-X", verb, *fields, path]).stdout


def post(github: ghapi.GitHub, path: str, body: str) -> evidencesplit.Comment:
    """Add a comment.

    Args:
        github: the API.
        path: the path of the pull request's comments.
        body: the text.

    Returns:
        The new comment.
    """
    return made(send(github, "POST", path, body), body)


def edit(
    github: ghapi.GitHub, path: str, number: int, body: str
) -> evidencesplit.Comment:
    """Replace the text of a comment.

    Args:
        github: the API.
        path: the path of the repository's issue comments.
        number: the comment's id.
        body: the new text.

    Returns:
        The comment.
    """
    return made(send(github, "PATCH", f"{path}/{number}", body), body)


def delete(github: ghapi.GitHub, path: str, number: int) -> None:
    """Remove a comment.

    Args:
        github: the API.
        path: the path of the repository's issue comments.
        number: the comment's id.
    """
    send(github, "DELETE", f"{path}/{number}", None)


def set_body(github: ghapi.GitHub, path: str, body: str) -> None:
    """Replace the description of a pull request.

    Args:
        github: the API.
        path: the pull request's path.
        body: the new description.
    """
    send(github, "PATCH", path, body)


def store_of(runners: tuple[Run, Run], slug: str, pull: int) -> evidencesplit.Store:
    """The store of one pull request, through ``gh api``.

    Args:
        runners: the runner reads go through and the runner changes go through
            (a dry run unless asked).
        slug: the repository's ``owner/name``.
        pull: the pull request's number.

    Returns:
        The store.
    """
    github = ghapi.GitHub(run=runners[0], mutate=runners[1])
    comments = f"repos/{slug}/issues/{pull}/comments"
    every = f"repos/{slug}/issues/comments"
    return evidencesplit.Store(
        comments=functools.partial(ghapi.pages, github, comments, listed),
        post=functools.partial(post, github, comments),
        edit=functools.partial(edit, github, every),
        delete=functools.partial(delete, github, every),
        set_body=functools.partial(set_body, github, f"repos/{slug}/pulls/{pull}"),
    )


def body(github: ghapi.GitHub, path: str) -> str:
    """The description of a pull request or an issue.

    Args:
        github: the API.
        path: its path.

    Returns:
        The text; empty when it has none.
    """
    return totaljson.text(ghapi.get_object(github, path).get("body"))


def _texts(page: str) -> Sequence[str]:
    return [totaljson.text(each.get("body")) for each in json.loads(page)]


def comment_texts(github: ghapi.GitHub, path: str) -> Sequence[str]:
    """The text of every comment of a pull request or an issue.

    Args:
        github: the API.
        path: its path.

    Returns:
        The texts, oldest first.
    """
    return ghapi.pages(github, f"{path}/comments", _texts)


def label_names(github: ghapi.GitHub, path: str) -> Sequence[str]:
    """The names of the labels of a pull request or an issue.

    Args:
        github: the API.
        path: its issue path.

    Returns:
        The names.
    """
    found = totaljson.listed(ghapi.get_object(github, path), "labels")
    return [totaljson.text(each.get("name")) for each in found]


def _bodies(text: str) -> Sequence[tuple[int, str]]:
    found = json.loads(text)
    return [(int(each["number"]), totaljson.text(each.get("body"))) for each in found]


def pull_bodies(github: ghapi.GitHub, slug: str) -> Sequence[tuple[int, str]]:
    """The number and description of every pull request of a repository.

    Args:
        github: the API.
        slug: the repository.

    Returns:
        The pairs.
    """
    return ghapi.every_pull(github, slug, _bodies)
