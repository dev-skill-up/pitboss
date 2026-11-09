"""The environment of the nox sessions of ``pitboss nox`` (keyword: nox-home, #364).

CI's runner has no git identity, so a test that needs one passes on a developer's
machine and fails there. The sessions therefore run with a throwaway ``HOME`` and
a ``GIT_CONFIG_GLOBAL`` inside it, and with the identity variables of git left
out. Only the environment of the nox child is built here: the parent's
environment, ``~/.gitconfig`` and every other process are not touched, and the
throwaway directory is removed when the run ends. The caches stay where they
are (``XDG_CACHE_HOME`` and ``XDG_DATA_HOME`` keep their real values), so pip and
virtualenv still find what they stored.
"""

import contextlib
import os
import pathlib
import sys
import tempfile
from collections.abc import Iterator, Mapping

from . import devpath

USAGE_ERROR = 2

IDENTITY = (
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
    "EMAIL",
)
KEPT_DIRECTORIES = (("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"))


@contextlib.contextmanager
def throwaway_home() -> Iterator[str]:
    """Make an empty directory to be ``HOME`` for one run.

    Yields:
        Its path; the directory is removed when the run ends.

    Raises:
        SystemExit: 2, before the directory is made, when the temporary directory
            is under ``/dev``, where nothing is removed (#424).
    """
    refused = devpath.under_dev(pathlib.Path(tempfile.gettempdir()))
    if refused:
        print(f"nox: no throwaway home, {refused}", file=sys.stderr)
        raise SystemExit(USAGE_ERROR)
    with tempfile.TemporaryDirectory(prefix="pitboss-nox-home-") as home:
        yield home


def isolated(environ: Mapping[str, str], home: str) -> Mapping[str, str]:
    """The environment of a nox child: no global git config, no identity.

    Args:
        environ: the environment of this process, which is not changed.
        home: the empty directory to be ``HOME``.

    Returns:
        A new environment.
    """
    real = environ.get("HOME", "")
    kept = {
        key: environ.get(key) or os.path.join(real, default)
        for key, default in KEPT_DIRECTORIES
        if real or environ.get(key)
    }
    return {
        **{key: value for key, value in environ.items() if key not in IDENTITY},
        **kept,
        "HOME": home,
        "GIT_CONFIG_GLOBAL": os.path.join(home, "gitconfig"),
        "XDG_CONFIG_HOME": os.path.join(home, "config"),
    }
