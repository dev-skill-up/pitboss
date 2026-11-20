"""The ``owner-pause`` command: label a PR ``paused-owner`` and post the question."""

import argparse

from . import ghclient, ownerpause, pullfile, steps


def _check(github: ghclient.GitHub, slug: str, number: int, text: str) -> str:
    return ownerpause.refusal(text)


def label(github: ghclient.GitHub, slug: str, number: int) -> None:
    """Put the ``paused-owner`` label on a PR.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        number: the PR's number.
    """
    named = ["-f", f"labels[]={steps.PAUSED_LABEL}"]
    path = ownerpause.label_path(slug, number)
    github.mutate(["gh", "api", "-X", "POST", *named, path])


@pullfile.register("owner-pause", "the question for the owner, in a file")
def owner_pause(args: argparse.Namespace) -> None:
    """Pause a PR for the owner: put the ``paused-owner`` label, post the question.

    The question is refused, and nothing is changed, unless it names the options
    (a line that starts with ``Options``) and has a ``How we got here`` section.
    The label goes on first and the question is posted as a comment; the
    comment's URL is printed (A5, keyword: owner-pause). The exit status is 2
    for a refusal or a file it cannot read.

    Args:
        args: the parsed arguments.

    """
    pullfile.post_comment(args, "owner-pause", _check, label)
