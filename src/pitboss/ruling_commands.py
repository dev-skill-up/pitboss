"""The ``ruling`` command: post an Opus ruling file as a PR comment (pitboss#466)."""

import argparse
import json
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, ghapi, pullfile, rulingform, rulingguard


def _texts(page: str) -> Sequence[str]:
    found = (each.get("body") for each in json.loads(page))
    return [str(each or "") for each in found]


def _already(github: ghapi.GitHub, slug: str, number: int) -> str:
    # keyword: one-ruling (A6): the PR's comments and labels, as GitHub has them
    path = f"repos/{slug}/issues/{number}"
    texts = ghapi.pages(github, f"{path}/comments", _texts)
    labels = [
        str(each["name"])
        for each in json.loads(ghapi.get(github, path)).get("labels", [])
    ]
    return rulingguard.refusal(texts, labels)


def _check(github: ghapi.GitHub, slug: str, number: int, text: str) -> str:
    return rulingform.refusal(text) or _already(github, slug, number)


@ENTRY_DATA.register(
    add_argument("action", choices=("post",), help="post: the file as a comment"),
    add_argument("pull", help="OWNER/NAME#NUMBER: the pull request"),
    add_argument("file", help="the ruling, in a file"),
    name="ruling",
)
def ruling(args: argparse.Namespace) -> None:
    """Post an Opus ruling file as a comment on a PR and print the comment's URL.

    This is the ruling-post area (pitboss#466): ``gh api -F body=@file`` was
    denied by the permission classifier four times. The file is refused, and
    nothing is posted, unless its first line is exactly ``Opus ruling``, its
    second line is ``Ruling: <word>`` with a word of the ruling words, and it
    has a ``How we got here`` section with the analysis in it. It is also
    refused when the PR already has an Opus ruling and is not paused for the
    owner (A6: one ruling per PR, a further rejection is the owner's). It posts
    as it is run, with no flag; the exit status is 2 for a refusal or a file it
    cannot read.

    Args:
        args: the parsed arguments.

    """
    pullfile.post_comment(args, "ruling post", _check)
