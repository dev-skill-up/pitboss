"""The kinds of ``lint`` that read a fixed list of files (keyword: lint-input)."""

import argparse
import pathlib

from . import e2ewaits, flowfiles, lintinput, reporules, rulinglint


def change(args: argparse.Namespace) -> None:
    """Check a diff against the flow files (keyword: flow-change, pitboss#444).

    Args:
        args: the parsed arguments; the file is ``git diff`` of the PR.
    """
    (diff,) = lintinput.exactly(args, ["one diff"])
    lintinput.finish(flowfiles.findings(diff), "ok")


def repo_rules(args: argparse.Namespace) -> None:
    """Check a diff against the repository's rules (keyword: repo-rules, pwa#320).

    Args:
        args: the parsed arguments; the files are the diff, CLAUDE.md, the body.
    """
    diff, claude, body = lintinput.exactly(
        args, ["the diff", "the CLAUDE.md", "the PR body"]
    )
    lintinput.finish(reporules.findings("body", claude, diff, body), "ok")


def ruling(args: argparse.Namespace) -> None:
    """Check a ruling's steps against the gates (keyword: ruling-lint, bats#654).

    Args:
        args: the parsed arguments; the files are the ruling, the ticket, the body.
    """
    said, ticket, body = lintinput.exactly(
        args, ["the ruling", "the ticket", "the PR body"]
    )
    lintinput.finish(rulinglint.findings(said, ticket, body, args.head or ""), "ok")


def e2e_waits(args: argparse.Namespace) -> None:
    """Refuse fixed waits and nameless quarantine marks (keyword: e2e-waits).

    Args:
        args: the parsed arguments; the one file is the root of the checkout.
    """
    (root,) = args.files
    allowed = pathlib.Path(args.allowed) if args.allowed else None
    found = e2ewaits.findings(pathlib.Path(root), args.dir, allowed)
    lintinput.finish(found, "ok")
