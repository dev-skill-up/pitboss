"""Parsing a page of the open PRs of a repository, with where each head lives."""

import dataclasses
from typing import Sequence

from . import parsing, shapes, totaljson


def with_repo(pull: shapes.Pull, repo: str) -> shapes.Pull:
    """Say which repository a PR's head lives in.

    Args:
        pull: the PR.
        repo: the ``owner/name`` of that repository.

    Returns:
        The PR, its head with the repository.
    """
    return dataclasses.replace(pull, head=dataclasses.replace(pull.head, repo=repo))


def open_pulls(text: str) -> Sequence[shapes.Pull]:
    """Parse a page of pull requests.

    Args:
        text: the response body of ``pulls``.

    Returns:
        The pull requests, in the order GitHub lists them, each head with the
        ``owner/name`` of the repository it lives in (empty for a deleted fork).
    """
    items = totaljson.read(text)
    listed = totaljson.listing(items)
    heads = [totaljson.name_at(item, "head", "repo", "full_name") for item in listed]
    return [
        with_repo(pull, head) for pull, head in zip(parsing.pulls_of(listed), heads)
    ]
