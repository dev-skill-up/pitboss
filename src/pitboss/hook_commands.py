"""The ``hook`` command: what a tracked git hook calls (keyword: pre-push-hook).

Ported from bats-lang/quire#1038 (``.githooks/pre-push``, ``scripts/pre-push.py``):
``git push`` runs the tracked hook, which calls ``pitboss hook pre-push``; the
checks are the configuration's ``[[pre_push]]`` entries, so another project
declares its own.
"""

import argparse
import pathlib
import sys

from gather.commands import add_argument

from . import ENTRY_DATA, commands, configsettle, prepush


@ENTRY_DATA.register(
    add_argument("kind", choices=("pre-push",), help="the hook that calls it"),
    add_argument(
        "words", nargs="*", help="what git passes the hook (the remote and its url)"
    ),
    add_argument(
        "--refs",
        default="-",
        help="the ref lines git gives the hook on standard input (- for it)",
    ),
    add_argument("--config", default=None, help="the project's configuration"),
    name="hook",
)
def hook(args: argparse.Namespace) -> None:
    """Run the project's ``[[pre_push]]`` checks, stopping at the first failure.

    A push that only deletes refs is not checked. A failure prints ``pre-push: check <n>
    (<name>) failed: <what>`` and ``fix: <the fix>``.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when a check fails.
    """
    refs = sys.stdin.read() if args.refs == "-" else pathlib.Path(args.refs).read_text()
    if not prepush.pushes_something(refs):
        return
    configsettle.find_or_say(args)
    settings = commands.load_settings(args)
    lines = prepush.hook_failure(
        args.safe_run, settings.project.pre_push, commands.working_directory(args)
    )
    for each in lines:
        print(each)
    if lines:
        raise SystemExit(1)
