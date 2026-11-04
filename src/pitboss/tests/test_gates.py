"""A repository's review gate is read from its workflow (pitboss#166)."""

import base64
import dataclasses
import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, gates, ghapi, headchecks, shapes
from . import fakes, suggestions, test_commands, test_flow_sweep, world

GATE = """
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
    if raw[0] != "## Adversarial review" or not shown:
    if verdicts == (["Verdict: changes needed"], ["Verdict: changes needed"]):
    if verdicts != (["Verdict: approved"], ["Verdict: approved"]):
    if (reviewed[0] not in (["Reviewed: " + head[:7]], ["Reviewed: " + head])
            or reviewed[1] != ["Reviewed: " + head]):
"""
LIBRARY_GATE = f"{world.LIBRARY}/contents/{gates.WORKFLOW}"
PROJECT_GATE = f"{world.PROJECT}/contents/{gates.WORKFLOW}"
THIRD_STATUS = fakes.page(f"{world.PROJECT}/commits/{'3' * 40}/status")
FORM = config.ReviewForm(
    lines=["## Adversarial review", "Verdict: {verdict}", "Reviewed: {sha}"],
    approved="approved",
    changes_needed="changes needed",
)
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
SUCCESS = {
    "statuses": [
        {
            "context": "adversarial-review",
            "state": "success",
            "created_at": "2030-01-01T00:00:00Z",
        }
    ]
}


def contents(text: str) -> object:
    """A file as the contents API gives it, its base64 in lines.

    Args:
        text: the file.

    Returns:
        The JSON.
    """
    return {"content": base64.encodebytes(text.encode()).decode(), "encoding": "base64"}


def with_gate(here: world.World, path: str, text: str = GATE) -> world.World:
    """Give a repository of the world a review gate.

    Args:
        here: the world.
        path: the path of the workflow file in the fake API.
        text: the workflow.

    Returns:
        The world.
    """
    here.bodies[path] = contents(text)
    return here


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
    return test_commands.sweep(world.make_world()).out


def swept(status: object = None) -> str:
    """A sweep of a world whose project is gated, and PR 3 has a status.

    Args:
        status: the body of PR 3's head status, None to leave it as it is.

    Returns:
        What the sweep printed.
    """
    here = with_gate(world.make_world(), PROJECT_GATE)
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
            context=context, succeeded=state == "success", created_at="", state=state
        )
        for context, state in pairs
    ]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FailingGate:
    """Processes that fail to read a workflow file, with HTTP 500.

    Attributes:
        inner: the processes the others go to.
    """

    inner: fakes.Processes

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
                1, list(cmdargs), output="", stderr="gh: server error (HTTP 500)\n"
            )
        return self.inner(cmdargs, **kwargs)


def failing_world() -> world.World:
    """A world whose reads of a gate workflow fail with HTTP 500.

    Returns:
        The world.
    """
    here = world.make_world()
    return dataclasses.replace(here, processes=FailingGate(inner=here.processes))


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
        failing = FailingGate(inner=fakes.FakeProcesses(bodies={}))
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
        found = world.again(failing_world(), "review-form", "lib")
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
    path.write_text(f"## Adversarial review\nVerdict: approved\nReviewed: {head}\n")
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
        """UNREADABLE for each repository, as the configuration has it."""
        out = test_commands.sweep(failing_world()).out
        said = f"UNREADABLE owner/lib: {gates.WORKFLOW} answered HTTP 500: gated as"
        assert_that(out, contains_string(said))

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
    """The sweep says a gate that is not success (the case of capacitor-plugins)."""

    def test_the_head_without_a_status_is_pending(self) -> None:
        """A gated repository's PR with no status at all."""
        line = "GATE PENDING owner/project#2: adversarial-review no status posted"
        assert_that(swept(), contains_string(line))

    def test_a_pending_status_is_named_with_its_text_and_link(self) -> None:
        """The state, what the gate said and where."""
        line = (
            "GATE PENDING owner/project#3: adversarial-review pending: No"
            " adversarial review yet (https://example.org/run/1):"
        )
        assert_that(swept(PENDING), contains_string(line))

    def test_an_approved_pr_whose_gate_is_pending_is_not_ready_to_merge(self) -> None:
        """PR 2 is green, clean and approved: ready, unless the gate says no."""
        ready = "READY TO MERGE owner/project#2"
        assert_that(
            [ready in swept_ungated(), ready in swept()], equal_to([True, False])
        )

    def test_a_gate_that_passes_prints_nothing(self) -> None:
        """Success is quiet."""
        assert_that("GATE PENDING owner/project#3" in swept(SUCCESS), equal_to(False))

    def test_an_ungated_repository_prints_none(self) -> None:
        """No workflow, no line."""
        assert_that("GATE PENDING" in swept_ungated(), equal_to(False))

    def test_the_status_is_read_from_the_head_statuses(self) -> None:
        """Without a description or a link, only the state."""
        failed = posted(("check", "success"), ("adversarial-review", "failure"))
        found = [
            headchecks.pending_gate(failed),
            headchecks.pending_gate(failed[:1]),
        ]
        assert_that(found, equal_to(["failure", "no status posted"]))
