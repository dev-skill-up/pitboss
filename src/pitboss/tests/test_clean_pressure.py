"""End-to-end tests of the root files and of the disk pressure line."""

import dataclasses
import datetime
import unittest

from .. import cleanconfig, diskline
from . import cleanworld, world

LATER = ("--now", world.FUTURE)


class TestRootFiles(unittest.TestCase):
    """Files in the container's root written after it started."""

    def test_root_files_are_dead_paths(self) -> None:
        """A file written well after the marker is listed; a live one is not."""
        root = cleanworld.session_root("written", "shared")
        here = world.make_world()
        cleanworld.configure(here, root)
        arguments = ("--marker", str(root / "marker"), "--root", str(root))
        out = world.again(here, "clean-container", *arguments).out
        pieces = [f"REMOVED PATH {root / 'written'}", "written over 1 hours after"]
        cleanworld.same(cleanworld.absent(out, pieces), [])
        cleanworld.same(f"{root / 'shared'}" in out, False)


class TestPressure(unittest.TestCase):
    """The warning of a sweep."""

    def test_pressure_names_the_largest_dead_paths(self) -> None:
        """Under the minimum a sweep names the dead paths that could be freed."""
        here = world.make_world()
        cleanworld.crowd(here, "1e9")
        late = world.again(here, "sweep", *LATER).out
        pieces = [f"DISK PRESSURE {here.workspace}:", "merged-work (its PR merged)"]
        busy = world.again(here, "sweep").out
        cleanworld.same(
            (cleanworld.absent(late, pieces), "merged-work" in busy), ([], False)
        )

    def test_the_pressure_line_scans_what_the_dry_run_lists(self) -> None:
        """The root files are in the one scan: the line names them too."""
        root = cleanworld.session_root("written")
        settings = cleanconfig.Clean(scratch=[], live=[], min_free_gib=1e9)
        look = dataclasses.replace(
            cleanworld.look_in(root), clean=settings, watch=cleanworld.watching(root)
        )
        now = datetime.datetime.fromtimestamp(0, datetime.timezone.utc)
        text = "\n".join(diskline.lines(look, now + datetime.timedelta(days=99999)))
        cleanworld.same(
            cleanworld.absent(
                text, ["DISK PRESSURE", f"{root / 'written'} (written over 1 hours"]
            ),
            [],
        )

    def test_no_pressure_no_line(self) -> None:
        """With room there is no line and nothing is scanned."""
        out = world.again(world.make_world(), "sweep", *LATER).out
        cleanworld.same("DISK PRESSURE" in out, False)
