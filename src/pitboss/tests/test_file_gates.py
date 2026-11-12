"""Tests for the gates a changed file has (keyword: file-gates, quire#1120)."""

import base64
import re
import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import filegates
from . import diffrepo, world
from .repositories import run_git
from .test_ci_pointer_check import unconfigured
from .test_slot_commands import next_output
from .says import exits, lacks, says

SLUG = "bats-lang/quire"
RELOCK = ".github/workflows/relock.yml"
SCHEDULED = "name: relock\non:\n  schedule:\n    - cron: '7 5 * * *'\njobs: {}\n"
PUSHED = "name: relock\non:\n  push:\njobs: {}\n"
CLAUDE = "# quire\n\nEvery change to `src/` must commit a regenerated `bootstrap/c`.\n"
SCRATCH = (
    "1. `text_lint` on relock.yml:"
    " https://github.com/bats-lang/relock-scratch/actions/runs/1/job/2, the log of the"
    " step\n"
)
BOOTSTRAP = "2. commit bootstrap/c from the artifact bootstrap-c-regenerated-HEAD\n"
OTHER = "1. `echo ok` shows ok\n"


def repository(
    case: unittest.TestCase, main: Mapping[str, str], work: Mapping[str, str]
) -> diffrepo.Repository:
    """A repository whose main has some files and whose branch ``work`` changes others.

    Args:
        case: the test, whose end removes the repository.
        main: the files of main, by path.
        work: the files the branch writes, by path.

    Returns:
        The repository, on ``work``.
    """
    repo = diffrepo.make_repository(case)
    run_git(repo.root, "checkout", "-q", "main")
    _commit_all(repo, main)
    run_git(repo.root, "update-ref", "refs/remotes/origin/main", "HEAD")
    run_git(repo.root, "checkout", "-q", "-B", "work")
    _commit_all(repo, work)
    return repo


def _commit_all(repo: diffrepo.Repository, files: Mapping[str, str]) -> None:
    # one commit for each file, in order
    for name, text in files.items():
        diffrepo.commit(repo, name, text)


def check(repo: diffrepo.Repository, plan: str, slug: str = SLUG) -> world.Result:
    """Run ``pitboss plan-check`` for a repository of the given name.

    Args:
        repo: the repository.
        plan: the rows of the Plan.
        slug: the repository's name.

    Returns:
        What it did.
    """
    return unconfigured(repo, plan, "--repository", slug)


class TestPlanCheck(unittest.TestCase):
    """The Plan has a row for each gate of the files the diff changes."""

    def test_c25_file_gates_relock_yml_without_the_scratch_run_row_is_refused(
        self,
    ) -> None:
        """A workflow the default branch runs: no row citing relock-scratch, refused."""
        repo = repository(self, {"CLAUDE.md": CLAUDE}, {RELOCK: SCHEDULED})
        done = check(repo, OTHER)
        exits(done, 1)
        says(done.out, "file-gate")
        says(done.out, "gate scratch-run")
        says(done.out, "relock-scratch/actions/runs/RUN/job/JOB")

    def test_c25_file_gates_relock_yml_with_the_scratch_run_row_passes(self) -> None:
        """The same change with the row is not refused for the gate."""
        repo = repository(self, {"CLAUDE.md": CLAUDE}, {RELOCK: SCHEDULED})
        lacks(check(repo, SCRATCH).out, "gate scratch-run")

    def test_c25_file_gates_a_workflow_with_no_gated_trigger_has_no_gate(self) -> None:
        """A push trigger runs the pull request's own file: no scratch run is due."""
        repo = repository(self, {"CLAUDE.md": CLAUDE}, {RELOCK: PUSHED})
        lacks(check(repo, OTHER).out, "gate scratch-run")

    def test_c25_file_gates_a_src_change_without_a_bootstrap_row_is_refused(
        self,
    ) -> None:
        """A repository whose CLAUDE.md names bootstrap/c wants a row committing it."""
        repo = repository(self, {"CLAUDE.md": CLAUDE}, {"src/a.bats": "x\n"})
        done = check(repo, OTHER)
        says(done.out, "gate bootstrap-c")
        exits(done, 1)

    def test_c25_file_gates_a_src_change_with_the_bootstrap_row_passes(self) -> None:
        """The row that commits bootstrap/c meets the gate."""
        repo = repository(self, {"CLAUDE.md": CLAUDE}, {"src/a.bats": "x\n"})
        lacks(check(repo, BOOTSTRAP).out, "gate bootstrap-c")

    def test_c25_file_gates_no_gated_file_has_no_finding(self) -> None:
        """A change to a file no gate names is not refused for a gate."""
        repo = repository(self, {"CLAUDE.md": CLAUDE}, {"notes.txt": "x\n"})
        lacks(check(repo, OTHER).out, "file-gate")

    def test_c25_file_gates_another_owner_has_no_scratch_gate(self) -> None:
        """The scratch-run gate is bats-lang's: another owner's repository has none."""
        repo = repository(self, {"CLAUDE.md": CLAUDE}, {RELOCK: SCHEDULED})
        lacks(check(repo, OTHER, OTHER_SLUG).out, "gate scratch-run")


OTHER_SLUG = "someone/else"


class TestTable(unittest.TestCase):
    """The shipped table is well formed and each gate says where it comes from."""

    def test_c25_file_gates_every_gate_has_a_source_sentence_of_the_form(self) -> None:
        """REPOSITORY/FILE: a sentence, and the patterns compile."""
        form = re.compile(r"^[\w.-]+/[\w./-]+: \S.{20,}$")
        for gate in filegates.shipped():
            assert_that(form.match(gate.source) is not None, equal_to(True), gate.id)
            for pattern in (gate.paths, gate.added, gate.content, gate.needle):
                re.compile(pattern)

    def test_c25_file_gates_the_ids_are_unique(self) -> None:
        """Two gates never share a name."""
        names = [gate.id for gate in filegates.shipped()]
        assert_that(len(set(names)), equal_to(len(names)))

    def test_c25_file_gates_a_row_with_a_missing_field_is_refused(self) -> None:
        """A table with a short row is an error, not a gate that never fires."""
        with self.assertRaises(ValueError):
            filegates.parse("only\tthree\tfields\n")


class TestBrief(unittest.TestCase):
    """The worker brief lists the gates of the files the Done-when names."""

    def test_c25_file_gates_a_ticket_naming_relock_yml_gets_the_scratch_run_line(
        self,
    ) -> None:
        """The brief names the gate and the row it needs."""
        found = filegates.lines(SLUG, CLAUDE, "Done when: relock.yml runs at 05:07.")
        says("\n".join(found), "gate scratch-run")
        assert_that(found[0], contains_string("FILE GATES"))

    def test_c25_file_gates_a_ticket_naming_no_gated_file_gets_no_line(self) -> None:
        """Nothing named, nothing added."""
        assert_that(
            filegates.lines(SLUG, CLAUDE, "Done when: the docs read well."),
            equal_to([]),
        )

    def test_c25_file_gates_the_worker_brief_of_a_ticket_prints_the_lines(self) -> None:
        """`slots next` prints the gates of the files the ticket's Done-when names."""
        here = world.make_world()
        ticket = dict(world.TICKET, body="Done when: `src/lib.bats` changes.")
        here.bodies[world.project_page("issues?state=open&labels=urgent")] = [ticket]
        content = base64.b64encode(CLAUDE.encode()).decode()
        here.bodies["repos/owner/project/contents/CLAUDE.md"] = {"content": content}
        text = next_output(here)
        assert_that(text, contains_string("FILE GATES"))
        assert_that(text, contains_string("gate bootstrap-c"))
