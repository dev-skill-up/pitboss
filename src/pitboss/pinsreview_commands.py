"""The ``pins-review`` command: the review comment of a green relock (pitboss#350).

This is the pins-review area: the comment a relock PR in a gated repository needs
when its review gate is pending.
"""

import argparse
import sys
from typing import NoReturn

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    commandarguments,
    commands,
    configsettle,
    expand_commands,
    gateform,
    ghstore,
    onepath,
    pinsonly,
    pinsreading,
    pinsreview,
    pulls,
    repoarg,
)

USAGE_ERROR = 2


def _refuse(why: str) -> NoReturn:
    raise SystemExit(f"pitboss pins-review: refused: {why}")


def _facts(found: commands.Context, text: str) -> pulls.PullFacts:
    named = expand_commands.PULL.match(text)
    if not named:
        print(f"{text}: not OWNER/NAME#NUMBER", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    repo = repoarg.named_repo(named.group(1), found.settings)
    reference = f"{repo.slug}#{named.group(2)}"
    # keyword: one-path: the PR's record, read as ``next <item>`` reads it
    records = [
        each for each in onepath.pull_records(found) if each.row.reference == reference
    ]
    if not records:
        _refuse(f"{reference}: no open PR of the configuration")
    return records[0].facts


def _cleared(found: commands.Context, facts: pulls.PullFacts) -> pinsreading.Reading:
    settings = found.settings
    why = pinsreview.unready(facts, settings.lint.relock_prefix)
    if why:
        _refuse(why)
    reading = pinsonly.verify(found.github.run, settings, facts.repo, facts.pull)
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
    commandarguments.NOW_ARGUMENT,
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
    found = commands.load_context(args)
    facts = _facts(found, args.pull)
    reading = _cleared(found, facts)
    form = gateform.read(args.safe_run, found.settings, facts.repo.slug).form
    text = pinsreview.comment(form, facts.pull.head.sha, reading)
    path = f"repos/{facts.repo.slug}/issues/{facts.pull.number}/comments"
    print(text, end="")
    print(f"# {ghstore.post(found.github, path, text).url}")
