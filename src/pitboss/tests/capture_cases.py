"""The inputs of the rule on a kept output (keyword: captured-run, pitboss#402)."""

from collections.abc import Mapping, Sequence

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
    "a message with all three, apart from its condition": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    assert not done.returncode, f"{command} {done.returncode} {done.stderr}"
    return done.stdout
""",
        [],
    ),
    "a bare assert that reads all three in its condition": (
        """
import subprocess

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    assert (done.returncode, done.stderr) == (0, ""), command
""",
        [5],
    ),
    "a lambda that is the call": (
        """
import subprocess

ran = lambda command: subprocess.run(command, capture_output=True)
""",
        [],
    ),
    "a lambda that reads the status": (
        """
import subprocess

missing = lambda command: subprocess.run(command, capture_output=True).returncode == 0
""",
        [4],
    ),
    "an async def that returns the status and a boolean": (
        """
import subprocess

async def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    return done.returncode, "x" in done.stderr
""",
        [5],
    ),
    "a function imported by name": (
        """
from subprocess import run

def ran(command):
    done = run(command, capture_output=True, text=True)
    return done.returncode, "x" in done.stderr
""",
        [5],
    ),
    "a function imported by name as another": (
        """
from subprocess import Popen as start

def ran(command):
    child = start(command, stderr=-1)
    return child.wait()
""",
        [],
    ),
    "a module imported as another name": (
        """
import subprocess as sp

def ran(command):
    done = sp.run(command, capture_output=True, text=True)
    return done.returncode, "x" in done.stderr
""",
        [5],
    ),
    "an assert_that whose reason has all three": (
        """
import subprocess
from hamcrest import assert_that, equal_to

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    assert_that(
        done.returncode, equal_to(0), f"{command} {done.returncode} {done.stderr}"
    )
""",
        [],
    ),
    "an assert_that whose value has all three": (
        """
import subprocess
from hamcrest import assert_that, equal_to

def ran(command):
    done = subprocess.run(command, capture_output=True, text=True)
    assert_that((done.returncode, done.stderr), equal_to((0, "")), command)
""",
        [6],
    ),
}
