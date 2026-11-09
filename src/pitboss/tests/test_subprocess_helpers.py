"""The tests keep a failed command readable and run one at a time (pitboss#402)."""

import pathlib
import unittest
from collections.abc import Sequence

from hamcrest import assert_that, equal_to

from . import subprocscan

HERE = pathlib.Path(__file__).resolve().parent

# what ``missing`` was: the status and booleans read from the error output
STATUS_AND_BOOLEANS = """
import subprocess

def missing(command):
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    return (done.returncode, "x" in done.stderr)
"""
HANDS_BACK = """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    return done
"""
HANDS_BACK_THE_CALL = """
import subprocess

def ran(command):
    return subprocess.run(command, stdout=subprocess.PIPE, text=True, check=False)
"""
SAYS_ALL = """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode:
        raise AssertionError(f"{done.args} exited {done.returncode}: {done.stderr}")
    return done.stdout
"""
SAYS_ALL_WITH_THE_COMMAND_AS_GIVEN = """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"{command} exited {done.returncode}: {done.stderr}"
    return done.stdout
"""
SAYS_ALL_OF_MERGED_OUTPUT = """
import subprocess

def ran(command):
    done = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
    )
    if done.returncode:
        raise AssertionError(f"{done.args} exited {done.returncode}: {done.stdout}")
    return done.stdout
"""
LACKS_THE_ERROR = """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode:
        raise AssertionError(f"{done.args} exited {done.returncode}")
    return done.stdout
"""
LACKS_THE_COMMAND = """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode:
        raise AssertionError(f"exited {done.returncode}: {done.stderr}")
    return done.stdout
"""
CHECKED = """
import subprocess

def ran(command):
    return subprocess.run(command, capture_output=True, check=True).stdout
"""
PIPED_OUTPUT_ONLY = """
import subprocess

def ran(command):
    done = subprocess.run(command, stdout=subprocess.PIPE, check=False)
    return done.returncode, done.stdout
"""
POPEN_LOSING_IT = """
import subprocess

def started(command):
    child = subprocess.Popen(command, stderr=subprocess.PIPE)
    return child.wait()
"""
NOTHING_CAPTURED = """
import subprocess

def ran(command):
    return subprocess.run(command, check=False).returncode
"""
IN_A_NESTED_FUNCTION = """
import subprocess

def outer(command):
    def inner():
        return subprocess.run(command, capture_output=True).stdout
    return inner
"""

ANNOTATED = """
import subprocess

def ran(command):
    done: object = subprocess.run(command, capture_output=True)
    return done
"""
POOL_FROM_AN_IMPORT = """
from concurrent.futures import ThreadPoolExecutor
import subprocess

def run_one(command):
    return subprocess.run(command)

def run_all(commands):
    return list(ThreadPoolExecutor().map(run_one, commands))
"""
CALLED_CALL = """
import threading

def make():
    return lambda: None

def start():
    make()().real
    threading.Thread(target=make()).start()
"""
ARITHMETIC_POOL = """
import concurrent.futures

def double(number):
    return number * 2

def doubled(numbers):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(double, numbers))
"""
POOL_OF_SUBPROCESSES = """
import concurrent.futures
import subprocess

def run_one(command):
    return subprocess.run(command, capture_output=True)

def run_all(commands):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(run_one, commands))
"""
POOL_OF_A_LAMBDA = """
import concurrent.futures
import subprocess

def run_all(commands):
    with concurrent.futures.ProcessPoolExecutor() as pool:
        return [pool.submit(lambda each: subprocess.call(each), c) for c in commands]
"""
POOL_THROUGH_A_HELPER = """
import concurrent.futures
import subprocess

def run_one(command):
    return subprocess.run(command, capture_output=True)

def checked(command):
    return run_one(command).returncode

def run_all(commands):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(checked, commands))
"""
THREAD_OF_A_SUBPROCESS = """
import subprocess
import threading

def start(command):
    return threading.Thread(target=lambda: subprocess.run(command)).start()
"""
PROCESS_OF_A_SUBPROCESS = """
import multiprocessing
import subprocess

def work(command):
    subprocess.run(command)

def start(command):
    multiprocessing.Process(target=work, args=(command,)).start()
"""
THREAD_OF_ARITHMETIC = """
import threading

def start(numbers):
    return threading.Thread(target=lambda: sum(numbers)).start()
"""
SUBPROCESS_WITHOUT_A_POOL = """
import subprocess

def run_all(commands):
    return list(map(subprocess.run, commands))
"""
MAP_OF_AN_OBJECT_IN_A_FILE_WITHOUT_POOLS = """
import subprocess

def run(command):
    return subprocess.run(command)

def run_all(table, commands):
    return table.map(run, commands)
"""


def unclear(text: str) -> Sequence[str]:
    """The lines of the helpers a source text has that lose the command or error.

    Args:
        text: the source.

    Returns:
        The finding for each, as ``name@line``.
    """
    return [f"{x.name}@{x.line}" for x in subprocscan.unclear_helpers("x.py", text)]


def pooled(text: str) -> Sequence[str]:
    """The lines where a source text hands a subprocess to a pool or a thread.

    Args:
        text: the source.

    Returns:
        The line of each.
    """
    return [str(x.line) for x in subprocscan.pooled_subprocesses({"x.py": text})]


class TestCapturedOutputIsReadable(unittest.TestCase):
    """A helper that captures output hands it back or says it when it fails."""

    def test_every_helper_of_the_tests_passes(self) -> None:
        """No helper under ``src/pitboss/tests`` loses the command, status or error."""
        found = subprocscan.unclear_in_files(subprocscan.sources(HERE))
        assert_that([str(each) for each in found], equal_to([]))

    def test_a_status_and_booleans_are_refused(self) -> None:
        """The helper is named, with the line of its call (what ``missing`` did)."""
        assert_that(unclear(STATUS_AND_BOOLEANS), equal_to(["missing@5"]))

    def test_the_finding_names_the_file_the_line_and_the_helper(self) -> None:
        """A finding reads as ``path:line: helper: reason``."""
        found = subprocscan.unclear_helpers("t.py", STATUS_AND_BOOLEANS)
        assert_that(
            [str(each).split(": ")[0:2] for each in found],
            equal_to([["t.py:5", "missing"]]),
        )

    def test_the_process_or_all_three_in_the_message_pass(self) -> None:
        """Handing back the process, and a message with the three, are accepted."""
        accepted = [
            HANDS_BACK,
            HANDS_BACK_THE_CALL,
            SAYS_ALL,
            SAYS_ALL_WITH_THE_COMMAND_AS_GIVEN,
            SAYS_ALL_OF_MERGED_OUTPUT,
            NOTHING_CAPTURED,
            ANNOTATED,
        ]
        assert_that([unclear(each) for each in accepted], equal_to([[]] * 7))

    def test_a_message_short_of_one_of_the_three_is_refused(self) -> None:
        """The nearest inputs: no error, no command, a check that shows neither."""
        refused = [LACKS_THE_ERROR, LACKS_THE_COMMAND, CHECKED, PIPED_OUTPUT_ONLY]
        assert_that(
            [unclear(each) for each in refused],
            equal_to([["ran@5"]] * 4),
        )

    def test_a_popen_and_a_nested_function_are_judged_too(self) -> None:
        """``Popen`` is a runner, and the function that holds the call is the helper."""
        assert_that(
            (unclear(POPEN_LOSING_IT), unclear(IN_A_NESTED_FUNCTION)),
            equal_to((["started@5"], ["inner@6"])),
        )


class TestNoPoolRunsSubprocesses(unittest.TestCase):
    """A subprocess of the tests runs in the thread of the test, one at a time."""

    def test_no_file_of_the_tests_does(self) -> None:
        """No pool, thread or process under ``src/pitboss/tests`` runs a subprocess."""
        found = subprocscan.pooled_subprocesses(subprocscan.sources(HERE))
        assert_that([str(each) for each in found], equal_to([]))

    def test_a_pool_that_only_does_arithmetic_passes(self) -> None:
        """The nearest input it accepts: threads that run no command."""
        accepted = [
            ARITHMETIC_POOL,
            THREAD_OF_ARITHMETIC,
            SUBPROCESS_WITHOUT_A_POOL,
            CALLED_CALL,
        ]
        assert_that([pooled(each) for each in accepted], equal_to([[]] * 4))

    def test_a_pool_that_maps_a_function_running_a_subprocess_fails(self) -> None:
        """The map, the submit of a lambda, a helper and a thread are all refused."""
        refused = [
            POOL_OF_SUBPROCESSES,
            POOL_OF_A_LAMBDA,
            POOL_THROUGH_A_HELPER,
            THREAD_OF_A_SUBPROCESS,
            PROCESS_OF_A_SUBPROCESS,
            POOL_FROM_AN_IMPORT,
        ]
        assert_that(
            [pooled(each) for each in refused],
            equal_to([["10"], ["7"], ["13"], ["6"], ["9"], ["9"]]),
        )

    def test_a_file_that_uses_no_pool_is_not_read_for_one(self) -> None:
        """A ``map`` of some other object, in a file with no thread, is not a pool."""
        assert_that(pooled(MAP_OF_AN_OBJECT_IN_A_FILE_WITHOUT_POOLS), equal_to([]))

    def test_the_finding_names_the_file_the_line_and_the_function(self) -> None:
        """A finding reads as ``path:line: function: reason``."""
        found = subprocscan.pooled_subprocesses({"t.py": POOL_OF_SUBPROCESSES})
        assert_that(
            [str(each).split(": ")[0:2] for each in found],
            equal_to([["t.py:10", "run_one"]]),
        )
