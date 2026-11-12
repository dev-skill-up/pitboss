"""``pitboss pins-review`` posts the gate's comment on a green relock (pitboss#350)."""

import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import forms, pinsreading, pinsreview
from . import fakes, repositories, world
from . import gateworld as gate_fixture
from . import pinsworld as pw
from .formchecks import subject
from .says import says

PULL = "owner/project#3"
COMMENTS = f"POST {world.PROJECT}/issues/3/comments"
CHECKS = fakes.page(f"{world.PROJECT}/commits/{pw.HEAD}/check-runs")
POSTED = {"id": 5, "html_url": "https://github.example/owner/project/pull/3#c5"}
PENDING_RUN = {"id": 9, "name": "slow", "status": "in_progress"}
REFUSED = "pitboss pins-review: refused: "
NAMES = f"run `pitboss pins-review {PULL} --no-dry-run`"
UNFIT_LINES = (
    "OK: café",
    "OK: ```x",
    "OK: ~~~x",
    "OK: <b>x",
    "OK: </b>",
    "[x]: http://y",
    "OK: Verdict: approved",
    "OK: reviewed: abc",
)


PIN = "a" * 40


def compiler_checkout(here: world.World, name: str) -> pathlib.Path:
    """A git checkout, in the workspace, whose commit does not contain ``PIN``.

    Args:
        here: the world.
        name: its directory's name.

    Returns:
        The directory.
    """
    path = here.workspace / name
    path.mkdir()
    repositories.run_git(path, "init", "--quiet")
    repositories.run_git(
        path,
        *repositories.IDENTITY,
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "old",
    )
    return path


def refused_for_age(here: world.World, compiler: pathlib.Path) -> None:
    """Give PR 3 a head whose bats pin is ``PIN`` and assert the age refusal.

    Args:
        here: the world, a relock whose command names ``compiler``.
        compiler: the checkout of the compiler, without ``PIN``.
    """
    pin = here.clone / ".github" / "bats-version"
    pin.parent.mkdir(exist_ok=True)
    pin.write_text(PIN + "\n")
    repositories.run_git(here.clone, "add", ".github/bats-version")
    repositories.run_git(
        here.clone, *repositories.IDENTITY, "commit", "--quiet", "-m", "pin"
    )
    head = repositories.run_git(here.clone, "rev-parse", "HEAD").strip()
    local = repositories.run_git(compiler, "rev-parse", "HEAD").strip()
    for key in [each for each in here.bodies if pw.HEAD in each]:
        here.bodies[key.replace(pw.HEAD, head)] = here.bodies.pop(key)
    pull = here.bodies[f"{world.PROJECT}/pulls/3"]
    assert isinstance(pull, dict)
    pull["head"] = {"sha": head, "ref": pw.RELOCK_BRANCH}
    here = with_gate(here)
    done = review(here, "--no-dry-run")
    assert_that(
        str(done.code), contains_string(f"{REFUSED}pins-check did not print OK")
    )
    assert_that(str(done.code), contains_string(local))
    assert_that(str(done.code), contains_string(PIN))
    assert_that(posts(here), equal_to([]))


def with_gate(here: world.World) -> world.World:
    """Give the project a review gate.

    Args:
        here: the world.

    Returns:
        The world.
    """
    return gate_fixture.with_gate(here, gate_fixture.PROJECT_GATE)


def plain_relock() -> world.World:
    """PR 3 on a relock branch, the project with no gate, a pins-check that is OK.

    Returns:
        The world.
    """
    here = pw.relock(pw.OK_COMMAND)
    here.bodies[COMMENTS] = POSTED
    return here


def gated_relock() -> world.World:
    """The same, and the project has a review gate.

    Returns:
        The world.
    """
    return with_gate(plain_relock())


def off_branch() -> world.World:
    """PR 3 off a relock branch, a gated project, a pins-check that is OK.

    Returns:
        The world.
    """
    return with_gate(pw.make("branch-3", pw.OK_COMMAND, pw.PIN_FILES))


def review(here: world.World, *more: str) -> world.Result:
    """Run ``pins-review`` on PR 3 of the world.

    Args:
        here: the world.
        *more: more arguments (``--no-dry-run``).

    Returns:
        What it did.
    """
    return world.invoke(here, "pins-review", PULL, "--config", here.config, *more)


def posts(here: world.World) -> Sequence[Sequence[str]]:
    """The comments the world's commands posted.

    Args:
        here: the world.

    Returns:
        The command lines that POST to PR 3's comments.
    """
    return [each for each in here.calls if each[-1].endswith("issues/3/comments")]


def posted_text(here: world.World) -> str:
    """The text of the one comment posted.

    Args:
        here: the world.

    Returns:
        The comment.
    """
    (call,) = posts(here)
    return call[call.index("-f") + 1].removeprefix("body=")


def refused(here: world.World, why: str) -> None:
    """Assert the command refuses with a reason and posts nothing.

    Args:
        here: the world.
        why: a piece of the reason.
    """
    done = review(here, "--no-dry-run")
    assert_that(str(done.code), contains_string(f"{REFUSED}{why}"))
    assert_that(posts(here), equal_to([]))


def ok_reading(line: str) -> pinsreading.Reading:
    """A pins-check that printed a line and exited 0.

    Args:
        line: its last line.

    Returns:
        The reading.
    """
    return pinsreading.Reading(status=pinsreading.Status.OK, detail=line)


class TestPost(unittest.TestCase):
    """A green relock whose pins-check prints OK gets the comment."""

    def test_the_comment_is_in_the_form_of_the_gate(self) -> None:
        """First line, one approved Verdict, the full head, the OK line, the ruling."""
        here = gated_relock()
        said = review(here, "--no-dry-run")
        text = posted_text(here)
        found = forms.gated_review(subject(text, pw.HEAD), gate_fixture.FORM)
        assert_that((said.code, found), equal_to((0, [])))
        assert_that(text.splitlines()[0], equal_to("## Adversarial review"))
        for part in ("Verdict: approved", f"Reviewed: {pw.HEAD}", pw.OK_ANSWER):
            assert_that(text, contains_string(part))
        assert_that(text, contains_string(pinsreview.RULING))
        for shown in (text, f"# {POSTED['html_url']}"):
            says(said.out, shown)

    def test_the_form_is_the_repositorys_own(self) -> None:
        """A repository with no gate gets the configured form's lines."""
        here = plain_relock()
        here.bodies[COMMENTS] = POSTED
        review(here, "--no-dry-run")
        assert_that(posted_text(here).splitlines()[0], equal_to("## Review"))

    def test_a_dry_run_posts_nothing(self) -> None:
        """Without --no-dry-run the comment is shown and no call is made."""
        here = gated_relock()
        done = review(here)
        assert_that(posts(here), equal_to([]))
        for shown in ("Verdict: approved", "# (dry run: no URL yet)"):
            says(done.out, shown)

    def test_no_agent_is_dispatched(self) -> None:
        """The only change the command makes is the one POST."""
        here = gated_relock()
        review(here, "--no-dry-run")
        changes = [each[-1] for each in here.calls if "-X" in each]
        assert_that(changes, equal_to([f"{world.PROJECT}/issues/3/comments"]))


class TestRefusal(unittest.TestCase):
    """Nothing is posted, and the reason is printed, when the PR may not have it."""

    def test_a_check_that_is_not_green(self) -> None:
        """A failed check, a pending one and no completed one: refused, not run."""
        cases = {
            "failed": [world.RED, world.GREEN],
            "pending": [world.GREEN, PENDING_RUN],
            "none completed": [],
        }
        for label, runs in cases.items():
            with self.subTest(label):
                here = gated_relock()
                here.bodies[CHECKS] = {"check_runs": runs}
                refused(here, f"{PULL} is not green")
                assert_that(pw.ran_commands(here), equal_to([]))

    def test_a_branch_that_is_not_a_relock(self) -> None:
        """A pins-only PR off a relock branch is not given the comment."""
        refused(off_branch(), f"{PULL} is not on a relock branch (head branch-3)")

    def test_a_pins_check_that_does_not_print_ok(self) -> None:
        """NOT OK and a failing command are refused with the command's line."""
        said = {
            "echo NOT OK: bats.lock: behind": "NOT OK: bats.lock: behind",
            "sh -c 'echo NOT-OK; exit 1'": "NOT-OK",
        }
        for shell, line in said.items():
            with self.subTest(shell):
                refused(
                    with_gate(pw.relock(shell)),
                    f"pins-check did not print OK ({line})",
                )

    def test_a_config_with_no_command_and_no_bats_is_refused(self) -> None:
        """The default command that cannot run is a refusal, never a review."""
        refused(with_gate(pw.without_bats()), "pins-check did not print OK (env: ")

    def test_a_compiler_without_the_pin_is_refused(self) -> None:
        """A ``--compiler`` command, and the default (the bats beside the repo)."""
        named = "bats pins-check {base} {head} --compiler ../older"
        for command, directory in {named: "older", "": "bats"}.items():
            with self.subTest(command or "default"):
                here = pw.with_bats(pw.relock(command))
                refused_for_age(here, compiler_checkout(here, directory))

    def test_an_ok_line_that_a_gate_would_not_read_as_plain_text(self) -> None:
        """Non-ASCII, a fence, an HTML tag, a definition, a verdict word."""
        for line in UNFIT_LINES:
            with self.subTest(line):
                why = pinsreview.unclear(ok_reading(line))
                assert_that(why, contains_string("plain text"))
        assert_that(pinsreview.unclear(ok_reading(pw.OK_ANSWER)), equal_to(""))

    def test_a_pull_request_that_cannot_be_read(self) -> None:
        """A PR the API does not know is refused with the call that failed."""
        here = gated_relock()
        argv = ("pins-review", "owner/project#99", "--config", here.config)
        done = world.invoke(here, *argv)
        assert_that(str(done.code), contains_string(f"{REFUSED}owner/project#99:"))
        assert_that(str(done.code), contains_string("answered HTTP 404"))

    def test_a_pull_request_that_is_not_a_reference(self) -> None:
        """The argument is OWNER/NAME#NUMBER; anything else exits 2."""
        here = plain_relock()
        done = world.invoke(here, "pins-review", "3", "--config", here.config)
        want = ("3: not OWNER/NAME#NUMBER", 2)
        assert_that((done.err.strip(), done.code), equal_to(want))


def names_the_command(here: world.World) -> bool:
    """Whether the sweep of the world names the command on a PINS-ONLY OK line.

    Args:
        here: the world.

    Returns:
        True when the PINS-ONLY OK line names ``pins-review``.
    """
    out = pw.swept(here)
    assert_that(pw.pins_lines(out), contains_string("PINS-ONLY OK"))
    return NAMES in pw.pins_lines(out) and "pins-review" in out


class TestSweepNamesIt(unittest.TestCase):
    """The PINS-ONLY OK line of a pending gate names the command."""

    def test_only_a_relock_whose_gate_is_pending_is_told_to_post(self) -> None:
        """Gated relock: yes; a gate that passes, no gate, not a relock: no."""
        passing = gated_relock()
        passing.bodies[gate_fixture.THIRD_STATUS] = gate_fixture.SUCCESS
        worlds = {
            "pending": (gated_relock(), True),
            "default command": (with_gate(pw.with_bats(pw.relock(""))), True),
            "passing": (passing, False),
            "no gate": (plain_relock(), False),
            "not a relock": (off_branch(), False),
        }
        found = {label: names_the_command(here) for label, (here, _) in worlds.items()}
        assert_that(found, equal_to({k: want for k, (_, want) in worlds.items()}))
