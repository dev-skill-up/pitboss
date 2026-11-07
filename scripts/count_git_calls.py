#!/usr/bin/env python3
"""Count the git processes the tests start, by fixture (keyword: git-census).

A hook on ``subprocess.Popen`` counts every process whose program is ``git``,
by its subcommand and by the fixture that asked: the first frame of the stack
inside ``pitboss/tests`` that is not one of the helpers that only run git
(``repositories.run_git`` and the like). The tests keep calling real git; the hook
only counts.

Usage, with the tests' environment (``build/nox/tests-3-13/bin/python``)::

    python scripts/count_git_calls.py [MODULE ...]

Each MODULE is a dotted name such as ``pitboss.tests.test_sync``; with none,
the whole suite runs. The totals, the subcommands and the fixtures are printed
(``--top N`` limits the fixture rows, default 25).
"""

import argparse
import collections
import os
import subprocess
import sys
import unittest

TESTS = os.sep.join(["pitboss", "tests", ""])
# only run git for a caller: the fixture is the frame above them
RELAYS = {"run_git", "__call__", "commit_file", "push", "build", "copy_of"}
HELPERS = {"fakes.py", "repositories.py"}


def fixture_of(frame):
    """The test file and function that asked for a process.

    Args:
        frame: the innermost frame.

    Returns:
        ``file:function`` of the first frame of the tests that is no relay.
    """
    while frame is not None:
        name = frame.f_code.co_filename
        relay = os.path.basename(name) in HELPERS and frame.f_code.co_name in RELAYS
        if TESTS in name and not relay:
            return f"{os.path.basename(name)}:{frame.f_code.co_name}"
        frame = frame.f_back
    return "(not from the tests)"


def install(subcommands, fixtures):
    """Hook ``subprocess.Popen`` so that git processes are counted.

    Args:
        subcommands: a counter of git subcommands.
        fixtures: a counter of fixtures.
    """
    original = subprocess.Popen.__init__

    def counted(self, args, *rest, **kwargs):
        words = [args] if isinstance(args, (str, bytes, os.PathLike)) else list(args)
        if words and os.path.basename(os.fsdecode(words[0])) == "git":
            skip = {"-c", "-C"}
            tail = [os.fsdecode(each) for each in words[1:]]
            while tail and tail[0] in skip:
                tail = tail[2:]
            subcommands[tail[0] if tail else "(none)"] += 1
            fixtures[fixture_of(sys._getframe(1))] += 1
        original(self, args, *rest, **kwargs)

    setattr(subprocess.Popen, "__init__", counted)


def main():
    """Run the tests with the hook and print the census."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--top", type=int, default=25)
    options = parser.parse_args()
    subcommands, fixtures = collections.Counter(), collections.Counter()
    install(subcommands, fixtures)
    loader = unittest.defaultTestLoader
    source = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    if options.modules:
        suite = loader.loadTestsFromNames(options.modules)
    else:
        suite = loader.discover(
            os.path.join(source, "pitboss", "tests"), top_level_dir=source
        )
    result = unittest.TextTestRunner(stream=open(os.devnull, "w")).run(suite)
    print(f"tests: {result.testsRun}, failures: {len(result.failures)}")
    print(f"git processes: {sum(subcommands.values())}")
    for name, count in subcommands.most_common():
        print(f"  git {name}: {count}")
    for name, count in fixtures.most_common(options.top):
        print(f"  fixture {name}: {count}")
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
