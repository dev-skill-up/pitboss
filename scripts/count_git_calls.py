#!/usr/bin/env python3
"""Count the git processes the tests start, by fixture (keyword: git-census).

A hook on ``subprocess.Popen`` counts every process whose program is ``git``,
by its subcommand and by the fixture that asked: the first frame of the stack
inside ``pitboss/tests`` that is not one of the helpers that only run git
(``repositories.run_git`` and the like). The tests keep calling real git; the hook
only counts.

Usage, with the tests' environment (``build/nox/tests-3-13/bin/python``)::

    python scripts/count_git_calls.py [MODULE ...]
    python scripts/count_git_calls.py --before origin/main

With ``--before REF`` the whole suite of the commit REF (a detached worktree made
in a temporary directory and removed) is counted too, and what is printed is the
totals and every subcommand and fixture whose count differs, as ``name before
after``.

Each MODULE is a dotted name such as ``pitboss.tests.test_sync``; with none,
the whole suite runs. The totals, the subcommands and the fixtures are printed
(every fixture; ``--top N`` cuts the fixture rows to N, default no cut).

A process started by a thread (the commands run git in a pool) is the fixture of
the code that made the thread, so no process is left without a fixture; a
process of no test at all would be ``(not from the tests)``.
"""

import argparse
import collections
import json
import os
import tempfile
import subprocess
import sys
import threading
import unittest

TESTS = os.sep.join(["pitboss", "tests", ""])
# only run git for a caller: the fixture is the frame above them
RELAYS = {"run_git", "__call__", "commit_file", "push", "build", "copy_of"}
DETAIL = collections.Counter()
HELPERS = {"fakes.py", "repositories.py"}


def fixture_of(frame):
    """The test file and function that asked for a process.

    Args:
        frame: the innermost frame.

    Returns:
        ``file:function`` of the first frame of the tests that is no relay;
        None when there is none.
    """
    while frame is not None:
        name = frame.f_code.co_filename
        relay = os.path.basename(name) in HELPERS and frame.f_code.co_name in RELAYS
        if TESTS in name and not relay:
            return f"{os.path.basename(name)}:{frame.f_code.co_name}"
        frame = frame.f_back
    return None


def owner_of(frame):
    """The fixture that asked, or that made the thread that asked.

    Args:
        frame: the innermost frame.

    Returns:
        ``file:function``, or ``(not from the tests)``.
    """
    found = fixture_of(frame)
    inherited = getattr(threading.current_thread(), "census_owner", None)
    return found or inherited or "(not from the tests)"


def install(subcommands, fixtures, detail=None):
    """Hook ``subprocess.Popen`` so that git processes are counted.

    Args:
        subcommands: a counter of git subcommands.
        fixtures: a counter of fixtures.
        detail: a counter of the pairs of a fixture and a git subcommand.
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
            owner = owner_of(sys._getframe(1))
            fixtures[owner] += 1
            if detail is not None:
                detail[owner, tail[0] if tail else "(none)"] += 1
        original(self, args, *rest, **kwargs)

    setattr(subprocess.Popen, "__init__", counted)
    made = threading.Thread.__init__

    def owned(self, *args, **kwargs):
        made(self, *args, **kwargs)
        self.census_owner = owner_of(sys._getframe(1))

    setattr(threading.Thread, "__init__", owned)


def census(tree, modules):
    """Run the tests of a tree under the hook.

    Args:
        tree: the root of a checkout.
        modules: the dotted names of the test modules; none for the whole suite.

    Returns:
        The tests run, the failures, the subcommands and the fixtures.
    """
    subcommands, fixtures = collections.Counter(), collections.Counter()
    install(subcommands, fixtures, DETAIL)
    loader = unittest.defaultTestLoader
    source = os.path.join(tree, "src")
    if modules:
        suite = loader.loadTestsFromNames(modules)
    else:
        suite = loader.discover(
            os.path.join(source, "pitboss", "tests"), top_level_dir=source
        )
    result = unittest.TextTestRunner(stream=open(os.devnull, "w")).run(suite)
    return (
        result.testsRun,
        len(result.failures) + len(result.errors),
        subcommands,
        fixtures,
    )


def before_census(ref):
    """The census of a commit, run in a process of its own.

    Args:
        ref: a commit or ref of this repository.

    Returns:
        The same four things ``census`` gives.
    """
    top = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as scratch:
        tree = os.path.join(scratch, "tree")
        subprocess.run(
            ["git", "-C", top, "worktree", "add", "-q", "--detach", tree, ref],
            check=True,
        )
        try:
            done = subprocess.run(
                [sys.executable, os.path.abspath(__file__), "--tree", tree, "--json"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            subprocess.run(
                ["git", "-C", top, "worktree", "remove", "--force", tree], check=True
            )
    found = json.loads(done.stdout.splitlines()[-1])
    return (
        found["tests"],
        found["failures"],
        collections.Counter(found["subcommands"]),
        collections.Counter(found["fixtures"]),
    )


def changes(label, before, after):
    """Print each name whose count differs.

    Args:
        label: what the names are.
        before: the counter before.
        after: the counter after.
    """
    names = sorted(set(before) | set(after), key=lambda n: (-before[n], n))
    for name in names:
        if before[name] != after[name]:
            print(f"  {label} {name}: {before[name]} {after[name]}")


def main():
    """Run the tests with the hook and print the census."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--before", default=None)
    parser.add_argument("--tree", default=None)
    parser.add_argument("--json", action="store_true")
    options = parser.parse_args()
    default = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # before the hook is installed, so that its worktree commands are not counted
    was = before_census(options.before) if options.before else None
    tests, failures, subcommands, fixtures = census(
        options.tree or default, options.modules
    )
    if options.json:
        print(
            json.dumps(
                {
                    "tests": tests,
                    "failures": failures,
                    "subcommands": subcommands,
                    "fixtures": fixtures,
                }
            )
        )
        sys.exit(0)
    if was:
        print(f"tests: {was[0]} {tests}, failures: {was[1]} {failures}")
        print(f"git processes: {sum(was[2].values())} {sum(subcommands.values())}")
        changes("git", was[2], subcommands)
        changes("fixture", was[3], fixtures)
        sys.exit(0 if not failures else 1)
    print(f"tests: {tests}, failures: {failures}")
    print(f"git processes: {sum(subcommands.values())}")
    for name, count in subcommands.most_common():
        print(f"  git {name}: {count}")
    for name, count in fixtures.most_common(options.top):
        parts = sorted(
            ((n, c) for (f, n), c in DETAIL.items() if f == name), key=lambda p: -p[1]
        )
        print(
            f"  fixture {name}: {count} ("
            + ", ".join(f"{n} {c}" for n, c in parts)
            + ")"
        )
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
