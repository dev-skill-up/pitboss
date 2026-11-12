"""The ``capture-timeline`` command: a PR's recorded timeline as JSON (pitboss#444)."""

import argparse
import json
import pathlib

from gather.commands import add_argument

from . import ENTRY_DATA, capture, expand_commands, ghapi


@ENTRY_DATA.register(
    add_argument("pull", help="OWNER/NAME#NUMBER: the pull request"),
    add_argument(
        "--to",
        default=None,
        help="write the timeline to this file (default: print it)",
    ),
    name="capture-timeline",
)
def capture_timeline(args: argparse.Namespace) -> None:
    """Read a PR's whole recorded timeline and write it as JSON.

    A scenario test (``tests/scenarios``) replays the file at its marked events
    and requires the step the rules give there. Nothing is changed on GitHub.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 2 when the argument is not OWNER/NAME#NUMBER.
    """
    found = expand_commands.PULL.match(args.pull)
    if not found:
        raise SystemExit(f"capture-timeline: {args.pull}: not OWNER/NAME#NUMBER")
    github = ghapi.read_only(args.safe_run)
    data = capture.capture(github, found.group(1), int(found.group(2)))
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    if args.to:
        pathlib.Path(args.to).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
