"""The brief's rule files, the recount and the brief ``act dispatch-next`` writes.

The keyword is brief-rules, pitboss#444.
"""

import dataclasses
import re
import unittest

from hamcrest import assert_that, calling, contains_string, empty, equal_to, raises

from .. import actcore, actverbs, dispatchnext, rulecount, rulefiles, totalroutes
from . import fakehub, scratch
from .knownkit import CHECKOUTS, made, shipped_kit

PLANTED = {
    "CLAUDE.md": "ROOT\n",
    "src/x.bats": "",
    "src/CLAUDE.md": "SUBDIR\n",
    "docs/CLAUDE.md": "OTHERDIR\n",
    ".claude/agents/worker.md": "WORKER\n",
    ".claude/rules/block.md": (
        '---\ndescription: a block\n  that goes on\npaths:\n  - "src/**"\n---\nBLOCK\n'
    ),
    ".claude/rules/sub/nested.md": "---\n\npaths:\n  - src/**\n---\nNESTED\n",
    ".claude/rules/none.md": "no front matter: always\n",
    ".claude/rules/other.md": "---\npaths:\n  - docs/**\n---\nNOT-APPLICABLE\n",
    ".claude/rules/described.md": "---\ndescription: no paths\n---\nDESCRIBED\n",
}
REFUSED = {
    "flow.md": ('---\npaths: ["src/**"]\n---\nFLOW\n', "not a block list"),
    "unknown-key.md": ("---\nglobs:\n  - src/**\n---\nKEY\n", "has no row"),
    "unclosed.md": ("---\npaths:\n  - src/**\nUNCLOSED\n", "not closed"),
    "empty.md": ("---\npaths:\n---\nEMPTY\n", "no entry"),
    "loose.md": ("---\npaths:\nsrc/**\n---\nLOOSE\n", "not in a known form"),
}


def _planted() -> rulefiles.Ticket:
    root, home = scratch.directory(), scratch.directory()
    for name, text in PLANTED.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    (home / ".claude").mkdir()
    (home / ".claude" / "CLAUDE.md").write_text("USERLEVEL\n", encoding="utf-8")
    return rulefiles.Ticket(checkout=root, paths=["src/x.bats", "src/"], home=home)


class TestWriter(unittest.TestCase):
    """The closed-world writer."""

    def test_444_the_planted_repository(self) -> None:
        """Every file that binds the path is carried, the others are not.

        And the recount agrees.
        """
        ticket = _planted()
        text = rulefiles.write(ticket)
        for said in (
            "ROOT",
            "SUBDIR",
            "WORKER",
            "BLOCK",
            "NESTED",
            "always",
            "DESCRIBED",
            "USERLEVEL",
        ):
            assert_that(text, contains_string(said))
        assert_that(
            (
                "OTHERDIR" in text,
                "NOT-APPLICABLE" in text,
                rulecount.missing(text, ticket),
            ),
            equal_to((False, False, [])),
        )

    def test_444_every_form_the_writer_does_not_read_refuses(self) -> None:
        """Each refused form names its file."""
        for name, (text, said) in REFUSED.items():
            with self.subTest(name):
                ticket = _planted()
                (ticket.checkout / ".claude" / "rules" / name).write_text(
                    text, encoding="utf-8"
                )
                assert_that(
                    calling(rulefiles.write).with_args(ticket),
                    raises(rulefiles.Refused, re.escape(said)),
                )

    def test_444_68_real_rule_files_0_refused(self) -> None:
        """The rule files of six real repositories are each read."""
        files = [
            path
            for checkout in CHECKOUTS.values()
            for path in sorted((checkout / rulefiles.RULES).rglob("*.md"))
        ]
        for path in files:
            rulefiles.front(path.read_text(encoding="utf-8"), str(path))
        assert_that(len(files), equal_to(68))

    def test_444_the_gates_of_the_paths(self) -> None:
        """A workflow, a markup file and CODEOWNERS each name their gate."""
        ticket = rulefiles.Ticket(
            checkout=scratch.directory(),
            paths=[".github/workflows/a.yml", "README.md", "CODEOWNERS"],
            home=scratch.directory(),
        )
        text = rulefiles.write(ticket)
        assert_that(
            (text.count("\n- "), text.startswith(f"\n{rulefiles.GATES}")),
            equal_to((3, True)),
        )


class TestRecount(unittest.TestCase):
    """The recount catches a writer that drops a file."""

    def test_444_a_dropped_file_is_named(self) -> None:
        """A file cut from the brief.

        The user's file and a nested rule are each missed.
        """
        ticket = _planted()
        text = rulefiles.write(ticket)
        for cut, named in (
            ("SUBDIR\n", "src/CLAUDE.md"),
            ("USERLEVEL\n", "CLAUDE.md"),
            ("NESTED\n", "nested.md"),
        ):
            assert_that(
                " ".join(rulecount.missing(text.replace(cut, ""), ticket)),
                contains_string(named),
            )

    def test_444_the_loose_reading(self) -> None:
        """A flow list, no front matter, no paths key, an unclosed one."""
        assert_that(
            rulecount.globs_of('---\npaths: ["a/**", b]\n---\n'),
            equal_to(["a/**", "b"]),
        )
        assert_that(
            rulecount.globs_of("---\npaths:\n  - a\nnot a list\n---\n"), equal_to(["a"])
        )
        for text in ("plain\n", "---\ndescription: x\n---\n", "---\npaths:\n"):
            assert_that(rulecount.globs_of(text), equal_to(None))
        assert_that(
            [
                rulecount.segments_match(["a", "b"], glob)
                for glob in (["**"], ["a"], [], ["*", "b"])
            ],
            equal_to([True, False, False, True]),
        )

    def test_444_skipped_folders_and_other_files(self) -> None:
        """A rule file under ``build`` and a text file under rules are not wanted."""
        ticket = _planted()
        (ticket.checkout / "build").mkdir()
        (ticket.checkout / "build" / "CLAUDE.md").write_text(
            "BUILT\n", encoding="utf-8"
        )
        (ticket.checkout / ".claude" / "rules" / "notes.txt").write_text(
            "TEXT\n", encoding="utf-8"
        )
        assert_that(rulecount.missing(rulefiles.write(ticket), ticket), empty())


FIFTH = dispatchnext.Item(
    ref="o/r#5", kind="ticket", created="2026-11-01", priority="p1"
)


class TestDispatchBrief(unittest.TestCase):
    """``act dispatch-next`` with a checkout writes the brief."""

    def test_444_the_brief_carries_the_rules_and_the_instructions(self) -> None:
        """The item, then the rule files, then what each actor writes."""
        ticket = _planted()
        hub = made(shipped_kit())
        state = fakehub.state(items=[FIFTH])
        world = dataclasses.replace(hub.act, work=lambda: state)
        options = {
            "checkout": str(ticket.checkout),
            "paths": "src/x.bats",
            "home": str(ticket.home),
        }
        said = actverbs.dispatch_next(world, actcore.Target(repo=""), options)
        ends = said.endswith(totalroutes.instructions())
        assert_that(
            (said.startswith("o/r#5\n"), "ROOT" in said, ends),
            equal_to((True, True, True)),
        )

    def test_444_a_linked_rule_cut_from_the_brief_is_named(self) -> None:
        """A file linked into the rules and cut from the brief is named."""
        ticket = _planted()
        outside = scratch.directory() / "linked.md"
        outside.write_text("LINKED\n", encoding="utf-8")
        (ticket.checkout / ".claude" / "rules" / "linked").mkdir()
        (ticket.checkout / ".claude" / "rules" / "linked" / "x.md").symlink_to(outside)
        written = rulefiles.write(ticket).replace("LINKED\n", "")
        assert_that(
            rulecount.missing(written, ticket), equal_to([".claude/rules/linked/x.md"])
        )

    def test_444_brief_refuses_when_the_recount_finds_a_file_missing(self) -> None:
        """A glob the two read differently.

        (a class, literal to the writer) refuses the brief.
        """
        ticket = _planted()
        (ticket.checkout / ".claude" / "rules" / "class.md").write_text(
            "---\npaths:\n  - src/[x].bats\n---\nCLASS\n", encoding="utf-8"
        )
        assert_that(
            calling(actverbs.brief).with_args(ticket),
            raises(actcore.Refused, "class.md"),
        )
