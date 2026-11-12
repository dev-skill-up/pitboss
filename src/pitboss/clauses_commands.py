"""The ``clauses`` command: every rule line of the owner's memory is mapped.

The keyword is clauses.
"""

import argparse
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, clauses, lintinput, phrases, rules


@ENTRY_DATA.register(
    add_argument("action", choices=("check",)),
    add_argument(
        "--memory",
        default=None,
        help="the folder of MEMORY.md and its topic files: each rule line needs a row",
    ),
    add_argument("--ticket-body", default=None, help="the body of ticket 444"),
    add_argument(
        "--ticket-comments", default=None, help="its comments, the API's JSON"
    ),
    name="clauses",
)
def clauses_check(args: argparse.Namespace) -> None:
    """Check ``clauses.tsv`` against the register and, when given, the corpus.

    Without options the table alone is checked: its ids, its needles and its
    reasons. With ``--memory`` every bullet of ``MEMORY.md`` and the description
    and How to apply line of each topic file must have a row; with
    ``--ticket-body`` and ``--ticket-comments`` so must each numbered case and each
    comment of ticket 444. The unmapped clauses are listed, one a line.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when there is a finding.
    """
    register = rules.parse(phrases.shipped_text("rules.tsv"))[0]
    corpus: list[clauses.Clause] = []
    if args.memory:
        corpus += clauses.memory(pathlib.Path(args.memory))
    if args.ticket_body and args.ticket_comments:
        body = lintinput.read(args.ticket_body)
        corpus += clauses.ticket(body, lintinput.read(args.ticket_comments))
    found = clauses.findings(phrases.shipped_text("clauses.tsv"), register, corpus)
    for each in found:
        print(each)
    print(f"clauses: {len(corpus)} clauses read, {len(found)} findings")
    if found:
        raise SystemExit(1)
    print("clauses check: ok", file=sys.stdout)
