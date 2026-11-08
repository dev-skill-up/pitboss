"""The ``pins-review`` command: the review comment of a green relock (pitboss#350).

This is the pins-review area. The sweep names the command on the ``PINS-ONLY OK``
line of a relock PR in a gated repository whose review gate is pending.
"""

import argparse
import sys
from typing import NoReturn

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    commandarguments,
    commands,
    config,
    configsettle,
    expand_commands,
    gateform,
    ghapi,
    ghstore,
    pinsonly,
    pinsreading,
    pinsreview,
    pulls,
    repoarg,
    shapes,
)

USAGE_ERROR = 2


def _refuse(why: str) -> NoReturn:
    raise SystemExit(f"pitboss pins-review: refused: {why}")


def _facts(github: ghapi.GitHub, settings: config.Config, text: str) -> pulls.PullFacts:
    found = expand_commands.PULL.match(text)
    if not found:
        print(f"{text}: not OWNER/NAME#NUMBER", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    source = pulls.Source(
        github=github,
        review=settings.review,
        undraft=lambda: True,
        relock_prefix=settings.lint.relock_prefix,
    )
    repo = repoarg.named_repo(found.group(1), settings)
    read = pulls.fetch_or_unreadable(source, repo, int(found.group(2)))
    if isinstance(read, shapes.Unreadable):
        _refuse(f"{read.reference}: {read.call} answered {read.status}")
    return read


def _cleared(
    github: ghapi.GitHub, settings: config.Config, facts: pulls.PullFacts
) -> pinsreading.Reading:
    why = pinsreview.unready(facts, settings.lint.relock_prefix)
    if why:
        _refuse(why)
    reading = pinsonly.verify(github.run, settings, facts.repo, facts.pull)
    why = pinsreview.unclear(reading)
    if why:
        _refuse(why)
    return reading


@ENTRY_DATA.register(
    add_argument("pull", help="OWNER/NAME#NUMBER: a pull request on a relock branch"),
    add_argument(
        "--config",
        default=None,
        help="the project's configuration: a path, or a name in"
        " .claude/pitboss/<name>.toml (default: $PITBOSS_CONFIG, else the search,"
        " else the copy fetched by the repository's name)",
    ),
    commandarguments.DRY_RUN_ARGUMENT,
    name="pins-review",
)
def pins_review(args: argparse.Namespace) -> None:
    """Post the approving review comment of a green relock whose pins-check is OK.

    The PR must be on a branch with the ``[relock] prefix`` with every check of
    its head green, and ``[relock] pins_check_command`` (default
    ``bats pins-check {base} {head} --compiler ../bats``), run on the head, must
    print ``OK`` from a compiler that contains the head's
    ``.github/bats-version``; the comment is in the repository's own form
    (``review-form``) with ``Verdict: approved``, ``Reviewed: <the full head
    SHA>``, the pins-check's line and the owner's ruling. Otherwise nothing is
    posted, the reason is printed and the exit status is 1.
    A dry run unless ``--no-dry-run``.

    Args:
        args: the parsed arguments.
    """
    configsettle.find_or_say(args)
    settings = commands.load_settings(args)
    github = ghapi.GitHub(mutate=args.run, run=args.safe_run)
    facts = _facts(github, settings, args.pull)
    reading = _cleared(github, settings, facts)
    form = gateform.read(args.safe_run, settings, facts.repo.slug).form
    text = pinsreview.comment(form, facts.pull.head.sha, reading)
    path = f"repos/{facts.repo.slug}/issues/{facts.pull.number}/comments"
    print(text, end="")
    print(f"# {ghstore.post(github, path, text).url}")
