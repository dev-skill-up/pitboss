"""What the capability rule counts as reaching the world (capability, #524).

``ALLOWED`` modules hold only values and syntax; ``WORLD_MODULES`` read or change the
world, each with the names of it that do neither; the banned calls, attributes and
methods reach a name or a file without writing it; ``FRAMEWORK`` is what the command
line hands a command and ``MODULE_FILE`` a path to a package's own file.
"""

import re
from typing import AbstractSet, Mapping


def _dunder(name: str) -> str:
    # written so that this file holds no string that names a dunder (a banned thing)
    return f"__{name}__"


# modules whose every use is a value or syntax: nothing in them reads
ALLOWED = frozenset(
    {
        _dunder("future"),
        "abc",
        "argparse",
        "ast",
        "base64",
        "collections",
        "contextlib",
        "dataclasses",
        "decimal",
        "enum",
        "fnmatch",
        "fractions",
        "functools",
        "hamcrest",  # matchers over values
        "html",
        "hashlib",
        "heapq",
        "itertools",
        "json",
        "logging",
        "math",
        "pathlib",
        "re",
        "shlex",
        "stat",
        "statistics",
        "string",
        "textwrap",
        "typing",
        "unicodedata",
        "urllib.parse",
    }
)
# modules that read or change the world, and the names of each that do neither
WORLD_MODULES: Mapping[str, AbstractSet[str]] = {
    "subprocess": frozenset(
        {"CalledProcessError", "TimeoutExpired", "CompletedProcess", "SubprocessError"}
    ),
    "os": frozenset(
        {"fspath", "sep", "linesep", "PathLike", "path"}
    ),  # path: capabilitypure
    "sys": frozenset({"stdout", "stderr", "exit", "version_info"}),
    "datetime": frozenset(
        {"datetime", "date", "time", "timedelta", "timezone", "UTC", "tzinfo"}
    ),
    "tomllib": frozenset({"loads", "TOMLDecodeError"}),
    "yaml": frozenset({"safe_load", "YAMLError"}),
    "gather.commands": frozenset({"add_argument", "set_parser", "ProcessRunner"}),
    "gather.api": frozenset({"Wrapper", "unique"}),
    "time": frozenset(),
    "tempfile": frozenset(),
    "shutil": frozenset(),
    "threading": frozenset(),
    "concurrent": frozenset(),
    "importlib": frozenset(),
    "urllib.request": frozenset(),
    "zipfile": frozenset(),
    "zoneinfo": frozenset(),
    "random": frozenset(),
    "unittest": frozenset({"TestCase"}),  # a base class: its asserts read nothing
    "gather": frozenset(),
    "commander_data": frozenset(),
}
# what opens a file by an argument or a setting, in modules that are otherwise values
FILE_OPENERS = frozenset(
    {
        "FileType",
        "basicConfig",
        "FileHandler",
        "WatchedFileHandler",
        "RotatingFileHandler",
        "TimedRotatingFileHandler",
    }
)
BANNED_CALLS = frozenset(
    {
        *FILE_OPENERS,
        "open",
        "exec",
        "eval",
        "compile",
        _dunder("import"),
        "input",
        "breakpoint",
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "globals",
        "locals",
        "dir",
    }
)
# attributes of any object that no pure module may use
BANNED_ATTRIBUTES = frozenset(
    {
        *FILE_OPENERS,
        _dunder("setattr"),
        _dunder("class"),
        _dunder("dict"),
        _dunder("globals"),
        _dunder("subclasses"),
        _dunder("builtins"),
        _dunder("members"),
        _dunder("replace"),
        "attrgetter",
        "itemgetter",
        "methodcaller",
        "parse_args",
        "parse_known_args",
        "parse_intermixed_args",
    }
)
# methods that read or change the world when called (a field of the same name is data)
BANNED_METHODS = frozenset(
    {
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "iterdir",
        "glob",
        "rglob",
        "exists",
        "is_file",
        "is_dir",
        "is_symlink",
        "mkdir",
        "unlink",
        "rmdir",
        "touch",
        "stat",
        "lstat",
        "resolve",
        "samefile",
        "readlink",
        "symlink_to",
        "rename",
        "open",
        "cwd",
        "home",
        "expanduser",
        "chmod",
        "now",
        "today",
        "utcnow",
        "isfile",
        "isdir",
        "islink",
        "getsize",
        "getmtime",
        "realpath",
        "abspath",
    }
)
FRAMEWORK = frozenset({"world"})
MODULE_FILE = re.compile(rf"^[\w/.]*/{_dunder('(init|main)')}\.py$")
