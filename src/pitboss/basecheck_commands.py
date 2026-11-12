"""The ``base-check`` command: the tests a PR body names, run on the base."""

import argparse
import importlib.resources
import pathlib
import re

from gather.commands import add_argument

from . import ENTRY_DATA, basecheck, donewhenrun, lintinput


def _module_of(name: str) -> str | None:
    # the test module of the head that defines the name
    found = pathlib.Path(str(importlib.resources.files("pitboss") / "tests"))
    for path in sorted(found.glob("test_*.py")):
        if re.search(rf"def {name}\(", path.read_text(encoding="utf-8")):
            return path.stem
    return None


@ENTRY_DATA.register(
    add_argument("file", help="the PR body, in a file"),
    add_argument(
        "--ref",
        default="origin/main",
        help="the base the named tests must fail on (default: origin/main)",
    ),
    add_argument(
        "--repo",
        default=".",
        help="a checkout of pitboss, which the base is made of (default: here)",
    ),
    name="base-check",
)
def base_check(args: argparse.Namespace) -> None:
    """Print one line: whether every test the Plan rows name fails on the base.

    The head's tests run in a scratch worktree of ``--ref``. A test that passes
    there needs a body line ``Already on main: TEST: REASON``.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when a named test passes on the base with no reason.
    """
    body = lintinput.read(args.file)
    tests = basecheck.named(body, _module_of)
    with donewhenrun.base_source(pathlib.Path(args.repo), args.ref) as source:
        passed = donewhenrun.run_all(tests, source)
    line = basecheck.verdict(body, tests, passed)
    print(line)
    raise SystemExit(int(line != "base check: ok"))
