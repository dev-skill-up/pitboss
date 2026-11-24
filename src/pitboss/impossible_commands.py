"""The ``impossible`` command: end a PR as impossible on an accepted impossibility."""

import argparse

from . import (
    ghstore,
    handbackpause,
    phrases,
    pullfile,
    rules,
)


@pullfile.register("impossible", "the worker's hand-back, in a file")
def impossible(args: argparse.Namespace) -> None:
    """End a PR as impossible: its worker's impossibility was accepted.

    This is the impossible-after-ruling area. The orchestrator judges the evidence
    first and sends the worker back when it is not an impossibility; when it
    accepts it, this command posts the card (``Impossible state``, the options and
    the hand-back as ``How we got here``), the terminal state the queue moves past
    (keyword: impossible-state). It is refused, and changes nothing, unless the
    hand-back shows an impossibility, the PR has an Opus ruling, it has not
    already ended impossible and the hand-back cites, in exact words
    (``Cites: "..."``), the rulings it rests on (impossiblecites). It prints the
    comment's URL; the exit status is 2 for a refusal or a file it cannot read.

    Args:
        args: the parsed arguments.
    """
    slug, number, text = pullfile.read("impossible", args.pull, args.file)
    github = pullfile.github_of(args)
    path = f"repos/{slug}/issues/{number}"
    comments = ghstore.comment_texts(github, path)
    if why := handbackpause.refusal(text, comments, _register()):
        pullfile.refuse("impossible", why)
    print(pullfile.comment(github, slug, number, handbackpause.question(text)))


def _register() -> list[str]:
    # the words of each rule of the register pitboss ships
    shipped = phrases.shipped_text("rules.tsv")
    return [each.words for each in rules.parse(shipped)[0]]
