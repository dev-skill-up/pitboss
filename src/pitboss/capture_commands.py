"""The ``capture-timeline`` command: a PR's recorded timeline as JSON (pitboss#444)."""

import argparse
import json
import pathlib
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, capture, expand_commands, ghclient


def _edits(source: str | None) -> Sequence[capture.Item]:
    # REST keeps no earlier text of a body: without a file, no edits are recorded
    # and a replay reads the final body at every mark (keyword: body-edits)
    if source:
        return capture.body_edits(json.loads(pathlib.Path(source).read_text("utf-8")))
    return ()


def _timeline(pull: str, github: ghclient.GitHub, source: str | None) -> str:
    found = expand_commands.PULL.match(pull)
    if not found:
        raise SystemExit(f"capture-timeline: {pull}: not OWNER/NAME#NUMBER")
    slug, number = found.group(1), int(found.group(2))
    edits = _edits(source)
    data = capture.capture(github, slug, number, edits)
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


@ENTRY_DATA.register(
    add_argument("pull", help="OWNER/NAME#NUMBER: the pull request"),
    add_argument(
        "--to",
        default=None,
        help="write the timeline to this file (default: print it)",
    ),
    add_argument(
        "--edits",
        default=None,
        help="the body edits as a file of userContentEdits JSON (default: none)",
    ),
    name="capture-timeline",
)
def capture_timeline(args: argparse.Namespace) -> None:
    """Read a PR's whole recorded timeline and write it as JSON.

    A scenario test (``tests/scenarios``) replays the file at its marked events
    and requires the step the rules give there. The body at a mark is the body
    after the newest edit by then (``--edits``); without it the final
    body (REST keeps no earlier text of a body). Nothing is changed on GitHub.

    Args:
        args: the parsed arguments.
    """
    text = _timeline(args.pull, ghclient.read_only(args.safe_run), args.edits)
    if args.to:
        pathlib.Path(args.to).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
