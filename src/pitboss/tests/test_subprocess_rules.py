"""The tests keep a failed command readable and run one at a time (pitboss#402).

The rules are read from the syntax of the files of the tests (keyword: captured-run):
a function that keeps a command's output hands the process back or says the command,
the status and the error; no pool or thread runs a subprocess.
"""

import pathlib
import unittest
from collections.abc import Mapping, Sequence

from hamcrest import assert_that, equal_to

from . import capturescan, poolscan, scanning

HERE = pathlib.Path(__file__).resolve().parent

# the line of the call that keeps the output, or none when the text is accepted;
# the refused ones are the nearest inputs, each short of one thing
CAPTURES: Mapping[str, tuple[str, Sequence[int]]] = {
    "the process": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    return done
""",
        [],
    ),
    "the call": (
        """
import subprocess

def ran(command):
    return subprocess.run(command, stdout=subprocess.PIPE)
""",
        [],
    ),
    "all three": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"{done.args} {done.returncode} {done.stderr}")
    return done.stdout
""",
        [],
    ),
    "the command as it was given": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    assert not done.returncode, f"{command} {done.returncode} {done.stderr}"
    return done.stdout
""",
        [],
    ),
    "all three of merged output": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if done.returncode:
        raise AssertionError(f"{done.args} {done.returncode} {done.stdout}")
    return done.stdout
""",
        [],
    ),
    "an annotated name": (
        """
import subprocess

def ran(command):
    done: object = subprocess.run(command, capture_output=True)
    return done
""",
        [],
    ),
    "no output kept": (
        """
import subprocess

def ran(command):
    return subprocess.run(command).returncode
""",
        [],
    ),
    "a status and booleans": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    return (done.returncode, "x" in done.stderr)
""",
        [5],
    ),
    "no error": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"{done.args} {done.returncode}")
    return done.stdout
""",
        [5],
    ),
    "no command": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"{done.returncode} {done.stderr}")
    return done.stdout
""",
        [5],
    ),
    "no status": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"{done.args} {done.stderr}")
    return done.stdout
""",
        [5],
    ),
    "a check that shows neither": (
        """
import subprocess

def ran(command):
    return subprocess.run(command, capture_output=True, check=True).stdout
""",
        [5],
    ),
    "a status and the output": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, stdout=subprocess.PIPE)
    return done.returncode, done.stdout
""",
        [5],
    ),
    "a popen": (
        """
import subprocess

def ran(command):
    child = subprocess.Popen(command, stderr=subprocess.PIPE)
    return child.wait()
""",
        [5],
    ),
    "a function in a function": (
        """
import subprocess

def outer(command):
    def inner():
        return subprocess.run(command, capture_output=True).stdout
    return inner
""",
        [6],
    ),
}
# the line of the call that hands a function to a pool or a thread, or none
POOLS: Mapping[str, tuple[str, Sequence[int]]] = {
    "a pool that does arithmetic": (
        """
import concurrent.futures

def double(number):
    return number * 2

def doubled(numbers):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(double, numbers))
""",
        [],
    ),
    "a thread that does arithmetic": (
        """
import threading

def start(numbers):
    return threading.Thread(target=lambda: sum(numbers)).start()
""",
        [],
    ),
    "a map with no pool in the file": (
        """
import subprocess

def run_one(command):
    return subprocess.run(command)

def run_all(commands):
    return list(map(run_one, commands))
""",
        [],
    ),
    "a map of an object in a file with no pool": (
        """
import subprocess

def run_one(command):
    return subprocess.run(command)

def run_all(table, commands):
    return table.map(run_one, commands)
""",
        [],
    ),
    "a call of a call": (
        """
import threading

def make():
    return lambda: None

def start():
    make()().real
    threading.Thread(target=make()).start()
""",
        [],
    ),
    "a function that runs a subprocess": (
        """
import concurrent.futures
import subprocess

def run_one(command):
    return subprocess.run(command)

def run_all(commands):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(run_one, commands))
""",
        [10],
    ),
    "a lambda that does": (
        """
import concurrent.futures
import subprocess

def run_all(commands):
    with concurrent.futures.ProcessPoolExecutor() as pool:
        return [pool.submit(lambda c: subprocess.call(c), x) for x in commands]
""",
        [7],
    ),
    "a function that calls one that does": (
        """
import concurrent.futures
import subprocess

def run_one(command):
    return subprocess.run(command)

def checked(command):
    return run_one(command).returncode

def run_all(commands):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(checked, commands))
""",
        [13],
    ),
    "a thread": (
        """
import subprocess
import threading

def start(command):
    return threading.Thread(target=lambda: subprocess.run(command)).start()
""",
        [6],
    ),
    "a process": (
        """
import multiprocessing
import subprocess

def run_one(command):
    return subprocess.run(command)

def start(command):
    multiprocessing.Process(target=run_one, args=(command,)).start()
""",
        [9],
    ),
    "an imported executor": (
        """
from concurrent.futures import ThreadPoolExecutor
import subprocess

def run_one(command):
    return subprocess.run(command)

def run_all(commands):
    return list(ThreadPoolExecutor().map(run_one, commands))
""",
        [9],
    ),
}


def lines_of(found: Sequence[scanning.Finding]) -> Sequence[int]:
    """The lines of findings.

    Args:
        found: the findings.

    Returns:
        Their lines, in order.
    """
    return [each.line for each in found]


class TestSubprocessRules(unittest.TestCase):
    """The files of the tests, and the nearest inputs each rule must tell apart."""

    def test_the_files_of_the_tests_pass_both_rules(self) -> None:
        """No function there loses the command or the error; no pool runs one."""
        texts = scanning.sources(HERE)
        found = [
            *capturescan.lossy_in_files(texts),
            *poolscan.pooled_subprocesses(texts),
        ]
        assert_that([scanning.shown(each) for each in found], equal_to([]))

    def test_a_function_that_loses_the_command_or_the_error_is_refused(self) -> None:
        """A status and booleans are refused; the process, or all three, pass."""
        found = {
            name: lines_of(capturescan.lossy_in_files({"x.py": text}))
            for name, (text, _) in CAPTURES.items()
        }
        assert_that(
            found, equal_to({n: list(want) for n, (_, want) in CAPTURES.items()})
        )

    def test_a_pool_that_runs_a_subprocess_is_refused(self) -> None:
        """Arithmetic in a pool passes; a function that runs a command fails."""
        found = {
            name: lines_of(poolscan.pooled_subprocesses({"x.py": text}))
            for name, (text, _) in POOLS.items()
        }
        assert_that(found, equal_to({n: list(want) for n, (_, want) in POOLS.items()}))

    def test_a_finding_names_the_file_the_line_and_the_function(self) -> None:
        """A finding reads as ``path:line: function: reason``."""
        status = CAPTURES["a status and booleans"][0]
        thread = POOLS["a function that runs a subprocess"][0]
        found = [
            *capturescan.lossy_in_files({"t.py": status}),
            *poolscan.pooled_subprocesses({"u.py": thread}),
        ]
        assert_that(
            [scanning.shown(each).split(": ")[:2] for each in found],
            equal_to([["t.py:5", "ran"], ["u.py:10", "run_one"]]),
        )
