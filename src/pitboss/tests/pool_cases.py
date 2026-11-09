"""The inputs of the rule on pools and threads (keyword: captured-run, pitboss#402)."""

from collections.abc import Mapping, Sequence

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
    "a subclass whose run does arithmetic": (
        """
import threading

class Worker(threading.Thread):
    def run(self):
        self.total = sum(range(3))
""",
        [],
    ),
    "a subclass whose run runs a subprocess": (
        """
import subprocess
import threading

class Worker(threading.Thread):
    def run(self):
        subprocess.run(["x"])
""",
        [5],
    ),
    "a process subclass imported by name": (
        """
from multiprocessing import Process as Child
import subprocess

class Worker(Child):
    def run(self):
        subprocess.run(["x"])
""",
        [5],
    ),
    "a positional target": (
        """
import subprocess
import threading

def go():
    subprocess.run(["x"])

def start():
    threading.Thread(None, go).start()
""",
        [9],
    ),
    "a positional target that does arithmetic": (
        """
import threading

def go():
    return sum(range(3))

def start():
    threading.Thread(None, go).start()
""",
        [],
    ),
    "a function imported by name": (
        """
import concurrent.futures
from subprocess import run

def run_all(commands):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(run, commands))
""",
        [7],
    ),
    "a function of a module imported as another name": (
        """
import concurrent.futures
import subprocess as sp

def go(command):
    return sp.run(command)

def run_all(commands):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(go, commands))
""",
        [10],
    ),
}
# a function of the package outside the tests, and a file of the tests that maps it
PACKAGE = """
import subprocess

def run_git(directory):
    return subprocess.run(["git", "-C", directory, "status"])
"""
MAPS_PACKAGE = """
import concurrent.futures

from pitboss import gitutil

def statuses(directories):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return list(pool.map(gitutil.run_git, directories))
"""
