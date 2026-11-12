"""A ruling's steps pass the gates they lead to (keyword: ruling-lint, bats#654)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length, is_

import json

from .. import ghapi, ruling_commands, rulinglint
from . import fakes, world
from .test_ticket_corpus import body as corpus

HEAD = "a" * 40
ITEM = "The run passes, demonstrated by a fixture."
TICKET = f"Context.\n\n## Done when\n\n- {ITEM}\n\nFound by quire#1118.\n"
PR_BODY = f"Fixes #1\n\nHead: {HEAD}\n\n## Plan\n\n1. {ITEM}\n\n## Execution\n\ndone\n"


def ruling(*steps: str) -> str:
    """A ruling with steps.

    Args:
        *steps: the lines of its steps.

    Returns:
        Its text.
    """
    lines = "\n".join(steps)
    return (
        f"Opus ruling\nRuling: do these steps\n\n## How we got here\n\nx\n\n{lines}\n"
    )


class TestRulingLint(unittest.TestCase):
    """The case of bats#654 and its neighbours."""

    def test_c34_deleting_the_origin_sentence_passes_the_gates(self) -> None:
        """The sentence is no item; the ruling that deletes it is carried out."""
        said = ruling("1. ticket delete: Found by quire#1118.")
        assert_that(rulinglint.findings(said, TICKET, PR_BODY, HEAD), equal_to([]))

    def test_c34_the_real_bodies_of_the_ticket_pass(self) -> None:
        """The origin line of bats#653 is deleted in the real body."""
        said = ruling("1. ticket delete: Found by quire#1118.")
        found = rulinglint.findings(said, corpus("bats-lang-bats-653"), PR_BODY, HEAD)
        assert_that([each for each in found if "step" in each], equal_to([]))

    def test_c34_a_step_whose_text_is_not_there_is_refused_by_step(self) -> None:
        """An impossible step is named."""
        said = ruling("1. ticket delete: Found by quire#1118.", "2. body delete: nope")
        found = rulinglint.findings(said, TICKET, PR_BODY, HEAD)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("ruling step 2"))

    def test_c34_a_step_that_breaks_plan_check_names_the_gate(self) -> None:
        """Editing a Done-when item leaves the Plan without it word for word."""
        said = ruling("1. ticket replace: The run passes => The run fails")
        found = rulinglint.findings(said, TICKET, PR_BODY, HEAD)
        assert_that(any("gate plan-check" in each for each in found), is_(True))

    def test_c34_a_ruling_without_edits_is_not_judged(self) -> None:
        """No step, no finding."""
        assert_that(rulinglint.edits(ruling("1. split the PR")), equal_to([]))
        assert_that(
            rulinglint.findings(ruling("x"), TICKET, "no plan", HEAD), equal_to([])
        )

    def test_c34_ruling_post_refuses_the_same_steps(self) -> None:
        """``ruling post`` reads the PR and its ticket and refuses an impossible.

        Step.
        """
        answers = {
            "repos/o/r/pulls/5": {"body": PR_BODY.replace("Fixes #1", "Fixes #1")},
            "repos/o/r/issues/1": {"body": TICKET},
        }

        def get(command: object, /, **kwargs: object) -> fakes.Output:
            return fakes.Output(stdout=json.dumps(answers[list(command)[-1]]))  # type: ignore[call-overload]

        github = ghapi.GitHub(mutate=get, run=get)  # type: ignore[arg-type]
        bad = ruling("1. ticket delete: nope")
        good = ruling("1. ticket delete: Found by quire#1118.")
        assert_that(
            ruling_commands._steps(github, "o/r", 5, bad), contains_string("step 1")
        )
        assert_that(ruling_commands._steps(github, "o/r", 5, good), equal_to(""))

    def test_c34_the_lint_kind_and_the_post_run_it(self) -> None:
        """``lint ruling`` prints the finding; ``ruling post`` refuses the same."""
        here = world.make_world()
        files = {}
        for name, text in (
            ("r", ruling("1. body delete: nope")),
            ("t", TICKET),
            ("b", PR_BODY),
        ):
            path = here.workspace / name
            path.write_text(text, encoding="utf-8")
            files[name] = str(path)
        done = world.invoke(
            here, "lint", "ruling", files["r"], files["t"], files["b"], "--head", HEAD
        )
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("ruling step 1"))
