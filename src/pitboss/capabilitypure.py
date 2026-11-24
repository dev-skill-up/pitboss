"""The pure names of the submodules of a world module (capability, #524)."""

from typing import AbstractSet, Mapping

# submodules of a world module that must be named through, each with its pure names:
# every other name of it (getctime, lexists, expandvars) reads the world
PURE_NAMES: Mapping[str, AbstractSet[str]] = {
    "os.path": frozenset(
        {
            "basename",
            "commonpath",
            "commonprefix",
            "dirname",
            "isabs",
            "join",
            "normcase",
            "normpath",
            "relpath",
            "sep",
            "split",
            "splitext",
        }
    )
}
