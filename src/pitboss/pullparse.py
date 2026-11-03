"""Parsing a page of the open PRs of a repository, with where each head lives."""

import dataclasses
import json
from typing import Sequence

from . import parsing, shapes


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
    items = json.loads(text)
    pulls = [parsing.pull(json.dumps(item)) for item in items]
    heads = [item["head"].get("repo") or {} for item in items]
    return [
        with_repo(pull, head.get("full_name", "")) for pull, head in zip(pulls, heads)
    ]
