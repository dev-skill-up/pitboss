"""A repository's review gate is read from its workflow (pitboss#166)."""

import dataclasses
import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, gates, ghapi, headchecks, shapes
from . import decisionline, fakes, quietworld, suggestions, test_commands
from . import test_flow_sweep, world
from .gateworld import (
    FORM,
    GATE,
    PROJECT_GATE,
    SUCCESS,
    THIRD_STATUS,
    contents,
    with_gate,
)

LIBRARY_GATE = f"{world.LIBRARY}/contents/{gates.WORKFLOW}"
PENDING = {
    "statuses": [
        {
            "context": "adversarial-review",
            "state": "pending",
            "description": "No adversarial review yet",
            "created_at": "2030-01-01T00:00:00Z",
            "target_url": "https://example.org/run/1",
        }
    ]
}

REVIEW = "REVIEWER: owner/project#{number}: grade Plan and Execution together"


def library_form(text: str | None) -> str:
    """What ``review-form`` prints for the library.

    Args:
        text: its gate workflow, None for a library with none.

    Returns:
        The output.
    """
    here = world.make_world()
    if text is not None:
        with_gate(here, LIBRARY_GATE, text)
    return world.again(here, "review-form", "lib").out


def swept_ungated() -> str:
    """A sweep of the world, whose project has no gate workflow.

    Returns:
        What the sweep printed.
    """
    return test_commands.sweep(quietworld.calm(world.make_world())).out


def swept(status: object = None) -> str:
    """A sweep of a world whose project is gated, and PR 3 has a status.

    Args:
        status: the body of PR 3's head status, None to leave it as it is.

    Returns:
        What the sweep printed.
    """
    here = quietworld.calm(with_gate(world.make_world(), PROJECT_GATE))
    here.bodies[THIRD_STATUS] = status or fakes.NO_STATUS
    return test_commands.sweep(here).out


def posted(*pairs: tuple[str, str]) -> Sequence[shapes.CommitStatus]:
    """Commit statuses.

    Args:
        *pairs: each status's context and state.

    Returns:
        The statuses.
    """
    return [
        shapes.CommitStatus(
            context=context,
            succeeded=state == "success",
            created_at="",
            state=state,
            run=0,
            description="",
            url="",
        )
        for context, state in pairs
    ]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FailingGate:
    """Processes that fail to read a workflow file.

    Attributes:
        inner: the processes the others go to.
        status: the HTTP status of the failure.
    """

    inner: fakes.Processes
    status: int

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> fakes.Output:
        """Run a command, failing on a workflow read.

        Args:
            cmdargs: the command line.
            **kwargs: passed on.

        Returns:
            The finished process.

        Raises:
            subprocess.CalledProcessError: for a read of the gate workflow.
        """
        if cmdargs[-1].endswith(gates.WORKFLOW):
            raise subprocess.CalledProcessError(
                1, list(cmdargs), output="", stderr=f"gh: (HTTP {self.status})\n"
            )
        return self.inner(cmdargs, **kwargs)


def failing_world(status: int) -> world.World:
    """A world whose reads of a gate workflow fail.

    Args:
        status: the HTTP status of the failure.

    Returns:
        The world.
    """
    here = world.make_world()
    failing = FailingGate(inner=here.processes, status=status)
    return dataclasses.replace(here, processes=failing)


class TestForm(unittest.TestCase):
    """The form is read from the text of the workflow."""

    def test_the_gate_workflow_gives_its_form(self) -> None:
        """First line, Verdict line, Reviewed line, and the verdict words."""
        assert_that(gates.form_of(GATE), equal_to(FORM))

    def test_a_workflow_that_is_not_a_gate_this_reads_has_no_form(self) -> None:
        """Something else is named, never guessed."""
        assert_that(gates.form_of("name: other\n"), equal_to(None))

    def test_a_missing_changes_needed_word_is_the_usual_one(self) -> None:
        """Only the approving word and the first line are essential."""
        text = GATE.replace('verdicts == (["Verdict: changes needed"]', "x")
        assert_that(gates.form_of(text), equal_to(FORM))

    def test_the_trusted_authors_are_read_or_the_usual_ones(self) -> None:
        """The workflow's own set, else owner, member and collaborator."""
        narrow = GATE.replace('"MEMBER", ', "")
        found = [gates.gate_of(GATE).trusted, gates.gate_of(narrow).trusted]
        found.append(gates.gate_of("x").trusted)
        usual = ["COLLABORATOR", "MEMBER", "OWNER"]
        assert_that(found, equal_to([usual, ["COLLABORATOR", "OWNER"], usual]))


class TestReading(unittest.TestCase):
    """The workflow is read through the default branch."""

    def test_a_repository_with_a_workflow_has_a_gate_and_one_without_none(self) -> None:
        """A 404 is no gate."""
        api = fakes.github({"repos/o/gated/contents/" + gates.WORKFLOW: contents(GATE)})
        found = [gates.read(api, config.parse_repo(n, "o")) for n in ("gated", "plain")]
        assert_that(found, equal_to([gates.gate_of(GATE), None]))

    def test_any_other_failure_is_raised(self) -> None:
        """A server error is not 'no gate'."""
        failing = FailingGate(inner=fakes.FakeProcesses(bodies={}), status=500)
        api = ghapi.GitHub(run=failing, mutate=failing)
        with self.assertRaises(subprocess.CalledProcessError):
            gates.read(api, config.parse_repo("gated", "o"))


class TestReviewForm(unittest.TestCase):
    """``review-form`` prints what the gate accepts."""

    def test_a_repository_with_a_gate_workflow_is_gated_in_its_form(self) -> None:
        """Gated and a gate, not 'not gated' (the case of bridge)."""
        out = library_form(GATE)
        for piece in (
            "# owner/lib: gated\n",
            f"# the form is read from {gates.WORKFLOW} of owner/lib",
            "{verdict}: 'approved' or 'changes needed'",
            "ASCII only",
            "invisible characters",
            "COLLABORATOR or MEMBER or OWNER",
            "never edited",
            "\n## Adversarial review\nVerdict: {verdict}\nReviewed: {sha}\n",
        ):
            assert_that(out, contains_string(piece))
        assert_that("not gated" in out, equal_to(False))

    def test_a_repository_without_a_workflow_is_not_gated(self) -> None:
        """Only then."""
        assert_that(library_form(None), contains_string("# owner/lib: not gated"))

    def test_a_workflow_whose_form_cannot_be_read_is_said(self) -> None:
        """The configured gated form follows, with a note to read the file."""
        out = library_form("name: other\n")
        assert_that(out, contains_string("# owner/lib: gated\n"))
        assert_that(out, contains_string("which this cannot read: read the file"))
        assert_that("Adversarial" in out, equal_to(False))

    def test_a_failed_read_stops_the_command(self) -> None:
        """Neither gated nor not gated is printed."""
        found = world.again(failing_world(500), "review-form", "lib")
        message = f"cannot read {gates.WORKFLOW} of owner/lib: HTTP 500"
        assert_that((found.out, found.code), equal_to(("", message)))


def gated_lint(*options: str) -> tuple[object, str]:
    """Lint a gate-form review of the library's head with ``--gated``.

    Args:
        *options: the options after the file; ``--config`` is the world's unless
            ``--no-config`` leads.

    Returns:
        The exit code and the last word printed.
    """
    here = with_gate(world.make_world(), LIBRARY_GATE)
    path = fakes.directory() / "review.md"
    head = fakes.HEAD
    graded = "Plan: approved\nExecution: approved\n"
    path.write_text(
        f"## Adversarial review\nVerdict: approved\nReviewed: {head}\n{graded}"
    )
    bare = options[:1] == ("--no-config",)
    config_options = [] if bare else ["--config", here.config]
    words = ["--gated", "--head", head, *options[bare:]]
    ran = world.invoke(here, "lint", "review", str(path), *config_options, *words)
    return ran.code, (ran.out or ran.err).split()[-1]


class TestLintGated(unittest.TestCase):
    """``lint review --gated`` reads the form the gate accepts."""

    def test_the_repository_gives_its_workflows_form(self) -> None:
        """The configured gated form differs from the workflow's."""
        found = [gated_lint(), gated_lint("--repository", "lib")]
        assert_that(found[0][0], equal_to(1))
        assert_that(found[1], equal_to((0, "ok")))

    def test_a_repository_needs_a_configuration(self) -> None:
        """Without one there is no repository to name."""
        found = gated_lint("--no-config", "--repository", "lib")
        assert_that(found[0], equal_to(2))


class TestSettled(unittest.TestCase):
    """The commands that sweep and brief know the gates."""

    def test_a_workflow_that_cannot_be_read_is_said_and_the_sweep_goes_on(self) -> None:
        """A refusal (403) is an answer: UNREADABLE, as the configuration has it."""
        out = test_commands.sweep(failing_world(403)).out
        said = f"UNREADABLE owner/lib: {gates.WORKFLOW} answered HTTP 403: gated as"
        assert_that(out, contains_string(said))

    def test_a_workflow_read_that_keeps_failing_ends_the_sweep(self) -> None:
        """A 500 on every try: status 1, the request on standard error (3.2)."""
        found = test_commands.sweep(failing_world(500))
        assert_that((found.code, found.out), equal_to((1, "")))
        assert_that(found.err, contains_string("review-gate.yml: HTTP 500"))

    def test_a_reviewer_brief_quotes_the_form_the_gate_accepts(self) -> None:
        """Done-when 2: the form, filled in, and what else the gate wants."""
        here = with_gate(test_flow_sweep.world_with([]), PROJECT_GATE)
        header, brief = suggestions.third(here)
        text = "\n".join(brief)
        assert_that(
            header.split(": ")[1], equal_to("review the Plan and the Execution")
        )
        quoted = (
            "uvx pitboss review-form",
            f"    ## Adversarial review\n    Verdict: <approved or changes needed>\n"
            f"    Reviewed: {test_flow_sweep.HEAD}\n",
            "Gated: this repository's review-gate.yml reads the comment",
            "ASCII only",
        )
        for piece in quoted:
            assert_that(text, contains_string(piece))

    def test_an_ungated_reviewer_brief_has_no_gate_note(self) -> None:
        """The usual form only."""
        text = "\n".join(suggestions.third(test_flow_sweep.world_with([]))[1])
        assert_that("Gated:" in text, equal_to(False))


class TestPendingGate(unittest.TestCase):
    """A gate that is not success is in no answer (keyword: one-path, P8)."""

    def test_the_gate_status_is_said_by_no_line(self) -> None:
        """No status, a pending one, a success: PR 3's decision is its review."""
        for status in (None, PENDING, SUCCESS):
            with self.subTest(str(status)[:20]):
                out = swept(status)
                assert_that("GATE PENDING" in out, equal_to(False))
                third = decisionline.of(out, "owner/project#3")
                assert_that(third, contains_string(REVIEW.format(number=3)))

    def test_an_approved_pr_of_a_gated_repository_is_not_merged(self) -> None:
        """PR 2's old-form approval is the merge step only where nothing gates it."""
        ungated = decisionline.of(swept_ungated(), "owner/project#2")
        gated = decisionline.of(swept(), "owner/project#2")
        assert_that(ungated, contains_string("`act review` the head as it is now"))
        assert_that(gated, contains_string(REVIEW.format(number=2)))

    def test_the_status_is_read_from_the_head_statuses(self) -> None:
        """Without a description or a link, only the state."""
        failed = posted(("check", "success"), ("adversarial-review", "failure"))
        found = [
            headchecks.pending_gate(failed),
            headchecks.pending_gate(failed[:1]),
        ]
        assert_that(found, equal_to(["failure", "no status posted"]))
