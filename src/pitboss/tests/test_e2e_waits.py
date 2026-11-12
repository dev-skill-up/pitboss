"""``lint e2e-waits`` (keyword: e2e-waits, quire#1038)."""

import pathlib
import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import e2ewaits
from . import fakes, world
from .says import exits, outs, says


def lint(files: Mapping[str, str], allowed: str | None = None) -> world.Result:
    """Run the lint over a checkout with files.

    Args:
        files: the paths under the checkout and their text.
        allowed: the text of the allowlist, None for no allowlist.

    Returns:
        What the command did.
    """
    here = world.make_world()
    root = fakes.directory()
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    argv = ["lint", "e2e-waits", str(root), "--dir", "e2e"]
    if allowed is not None:
        listed = pathlib.Path(root) / "allowed.tsv"
        listed.write_text(allowed, encoding="utf-8")
        argv += ["--allowed", str(listed)]
    return world.invoke(here, *argv)


class TestE2eWaits(unittest.TestCase):
    """Each case of the Done-when."""

    def test_t52_wait_for_timeout_is_refused(self) -> None:
        """A fixed wait."""
        done = lint({"e2e/a.spec.js": "await page.waitForTimeout(500);\n"})
        exits(done, 1)
        says(done.out, "e2e/a.spec.js: 1 fixed waits, 0 allowed")

    def test_t52_a_bare_function_set_timeout_is_refused(self) -> None:
        """A callback and a delay."""
        done = lint({"e2e/a.js": "setTimeout(() => go(), 100);\nsetTimeout(go, 5);\n"})
        says(done.out, "2 fixed waits")

    def test_t52_the_accepted_forms_pass(self) -> None:
        """``test.setTimeout`` and a zero delay."""
        text = "test.setTimeout(60000);\nsetTimeout(() => go(), 0);\n"
        exits(lint({"e2e/a.js": text}), 0)

    def test_t52_an_allowed_wait_with_an_exact_count_passes(self) -> None:
        """The allowlist names the path, the count and the ticket."""
        files = {"e2e/a.js": "await page.waitForTimeout(1);\n"}
        exits(lint(files, "e2e/a.js\t1\t#12\n"), 0)

    def test_t52_the_allowlist_skips_blank_and_note_lines(self) -> None:
        """A ``#`` line and a blank line are not entries."""
        files = {"e2e/a.js": "await page.waitForTimeout(1);\n"}
        exits(lint(files, "# note\n\ne2e/a.js\t1\t#12\n"), 0)

    def test_t52_an_unclosed_set_timeout_is_still_counted(self) -> None:
        """The file ends before the call's ``)``."""
        says(lint({"e2e/a.js": "setTimeout(go, 5"}).out, "1 fixed waits")

    def test_t52_a_count_above_the_files_waits_is_refused(self) -> None:
        """The count only shrinks."""
        files = {"e2e/a.js": "await page.waitForTimeout(1);\n"}
        done = lint(files, "e2e/a.js\t2\t#12\n")
        exits(done, 1)
        says(done.out, "lower the count")

    def test_t52_a_fixme_without_a_ticket_is_refused(self) -> None:
        """A quarantine names its ticket."""
        outs(lint({"e2e/a.js": "test.fixme('flaky');\n"}), 1, "names no ticket")

    def test_t52_a_fixme_with_a_project_condition_is_refused(self) -> None:
        """Only ``true``."""
        text = "test.fixme(browserName === 'webkit', '#7 flaky');\n"
        done = lint({"e2e/a.js": text})
        says(done.out, "holds the condition")
        assert_that(lint({"e2e/a.js": "test.fixme('#7 flaky');\n"}).code, equal_to(0))

    def test_t52_a_malformed_allowlist_is_an_error(self) -> None:
        """A line needs three fields."""
        with self.assertRaisesRegex(ValueError, "need PATH"):
            e2ewaits.allowed(_file("only-a-path\n"))


def _file(text: str) -> pathlib.Path:
    path = fakes.directory() / "list.tsv"
    path.write_text(text, encoding="utf-8")
    return path
