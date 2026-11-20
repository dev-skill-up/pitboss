"""The ``ruling`` command: post an Opus ruling file as a PR comment (pitboss#466)."""

import argparse

from gather.commands import add_argument


from . import (
    ENTRY_DATA,
    folds,
    forms,
    ghclient,
    ghstore,
    pullfile,
    rulingform,
    rulinglint,
    rulingguard,
)


def _already(github: ghclient.GitHub, slug: str, number: int) -> str:
    # keyword: one-ruling (A6): the PR's comments and labels, as GitHub has them
    path = f"repos/{slug}/issues/{number}"
    texts = ghstore.comment_texts(github, path)
    return rulingguard.refusal(texts, ghstore.label_names(github, path))


def step_findings(github: ghclient.GitHub, slug: str, number: int, text: str) -> str:
    """What a ruling's edit steps leave failing on a PR and its ticket.

    The keyword is ruling-lint (bats#654): the steps must pass the gates they
    lead to.

    Args:
        github: the API.
        slug: the PR's repository.
        number: the PR.
        text: the ruling.

    Returns:
        The findings, joined by "; "; "" when it orders no edit or none fails.
    """
    if not rulinglint.orders_edits(text):
        return ""
    body = ghstore.body(github, f"repos/{slug}/pulls/{number}")
    ticket = ""
    for each in folds.tickets(body)[:1]:
        where, _, issue = each.partition("#")
        ticket = ghstore.body(github, f"repos/{where or slug}/issues/{issue}")
    head = "".join(forms.HEAD_LINE.findall(body)[-1:])
    return "; ".join(rulinglint.findings(text, ticket, body, head))


def _check(github: ghclient.GitHub, slug: str, number: int, text: str) -> str:
    return (
        rulingform.refusal(text)
        or step_findings(github, slug, number, text)
        or _already(github, slug, number)
    )


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
