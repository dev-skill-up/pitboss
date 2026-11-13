"""The notes ``next <ticket>`` prints before its decision (keyword: done-when-names).

Not a decision and not a wait: what the ticket's own text names that does not
exist (T419), a hoped-for figure, a repeated run (pitboss#278) and a flake whose
test is not quarantined (C6). They read the ticket the walk examined and the
checkout this command runs in.
"""

import argparse
import pathlib
from typing import Mapping, Sequence

from . import (
    ENTRY_DATA,
    brief,
    commandscan,
    configfile,
    configloads,
    donewhen,
    flake,
    hopedfigure,
    mode,
    repeatruns,
    shapes,
    world,
)


def asked(
    args: argparse.Namespace, chosen: mode.Mode, records: Mapping[str, world.Record]
) -> Sequence[str]:
    """The notes of the ticket an item form names; none for the list or a PR.

    Args:
        args: the parsed arguments.
        chosen: the mode of the command.
        records: the record of each decided item.

    Returns:
        The lines.
    """
    found = records.get(mode.item_of(chosen))
    if isinstance(found, world.TicketRecord):
        return lines(args, found.reference, found.issue)
    return []


def lines(args: argparse.Namespace, ticket: str, issue: shapes.Issue) -> Sequence[str]:
    """The notes of a ticket.

    Args:
        args: the parsed arguments (the checkout and the configuration).
        ticket: its ``owner/name#number``.
        issue: the ticket as the walk read it.

    Returns:
        The lines, in order; none when its text names nothing amiss.
    """
    tree = configfile.working_directory(args)
    known = donewhen.Known(
        kinds=frozenset(brief.Kind.__members__),
        commands=frozenset(commandscan.scanned(ENTRY_DATA.collector.collect)),
        tree=tree,
    )
    said = [donewhen.missing_line(ticket, issue.body, known)]
    said += hopedfigure.findings(issue.body)  # keyword: hoped-figure (T419)
    said += [repeatruns.line(ticket, donewhen.section(issue.body))]
    if flake.issue_is_flake(issue):
        said += [_unmarked(args, ticket, tree)]
    return [each for each in said if each]


def _unmarked(args: argparse.Namespace, ticket: str, tree: pathlib.Path) -> str:
    # keyword: flake (pitboss#278): the line is empty when the test is marked
    globs = configloads.load_brief(configfile.named(args), tree).quarantine_globs
    return flake.unmarked_line(ticket, tree, globs)
