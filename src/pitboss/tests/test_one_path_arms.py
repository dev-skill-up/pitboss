"""Each arm of the one path on typed state (plan 6.1 and 6.2, keyword: one-path)."""

import dataclasses
import itertools
import pathlib
import tempfile
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, none

from .. import answer, config, decide, gateverbs, listed
from .. import mode, nextcommand, onepath, pullnames, pushdraft, refill, render
from .. import sharedred, shapes, slotbook, slotsheader, steps
from .. import sweepline, work, workorder, world
from . import fakes, gatewords, knownkit, knownshipped, test_decide, test_work
from . import totalcomplete, totalpairs, totalworld
from . import world as scenes
from .says import errs

REPO = config.make_repo("owner", "project")
NONE = answer.NotEnoughWork()
NOTHING = answer.Decided(answer=NONE, by_item={})
PLAIN = "repos/owner/project/issues?state=open&labels=p1"
REFERENCE = "o/r#1"


def pull_record(*, held: bool, stuck: Sequence[str]) -> world.PullRecord:
    """An open, green PR of the project, as the walk reads it.

    Args:
        held: whether a slot holds it.
        stuck: the owner's verbs for a stuck run, if any.

    Returns:
        Its record.
    """
    return world.PullRecord(
        row=listed.listed_row(REPO, "relock/", fakes.pull_body(3)),
        facts=test_work.facts(3, test_work.NONE),
        blockers=[],
        stuck=stuck,
        gated=None,
        held=held,
        failures={},
    )


def act_line(*words: str) -> scenes.Result:
    """Run ``act`` on the command line, in a world of the project.

    Args:
        *words: the verb, its target and its options.

    Returns:
        What the command did.
    """
    here = scenes.make_world()
    given = ("--config", here.config, "--now", scenes.FUTURE)
    return scenes.invoke(here, "act", *words, *given)


def ticket_judgement() -> decide.Judgement:
    """What one world with one startable ticket decides.

    Returns:
        The judgement.
    """
    walk = world.Stopped(examined=[test_decide.ticket(1)], stop=1)
    made = world.World(listing=[], walk=walk, named=[], book=test_decide.BOOK, free=1)
    return decide.decide(made)


def no_pick(record: world.Record) -> None:
    """A slot takes nothing for any record.

    Args:
        record: the record.
    """
    del record


def issue(number: int) -> object:
    """A p1 ticket as GitHub lists it, opened ``number`` minutes in.

    Args:
        number: its number.

    Returns:
        The JSON.
    """
    hour, minute = divmod(number, 60)
    return {
        "number": number,
        "title": f"ticket {number}",
        "created_at": f"2026-01-01T{hour:02}:{minute:02}:00Z",
        "labels": [{"name": "p1"}],
        "body": "",
    }


def p1_settings() -> config.Config:
    """The project's configuration, ranking the label ``p1``.

    Returns:
        The configuration.
    """
    settings = fakes.settings(fakes.directory())
    slots = dataclasses.replace(settings.slots, priority_labels=("p1",))
    return dataclasses.replace(settings, slots=slots)


class TestDecideItem(unittest.TestCase):
    """Plan 6.1 and 6.2: ``decide_item`` on hand-made pull request records."""

    def test_a_pr_a_slot_holds_has_no_decision(self) -> None:
        """Its agent is at work on it: no actor is told to take it."""
        found = decide.decide_item(pull_record(held=True, stuck=["re-run it"]))
        assert_that(found, none())

    def test_a_stuck_run_is_the_owners(self) -> None:
        """A run stuck past its limit is the owner's verb on the PR."""
        found = decide.decide_item(pull_record(held=False, stuck=["re-run it"]))
        said = answer.Decision(
            actor=answer.Actor.OWNER,
            verb="re-run it",
            item="owner/project#3",
            title="PR 3",
        )
        assert_that(found, equal_to(said))


class TestAnswers(unittest.TestCase):
    """Plan 6.1: each mode's projection and renderer, ``NotEnoughWork`` too."""

    def test_dispatch_of_no_work_is_the_one_line(self) -> None:
        """``dispatch-next`` with nothing startable says not enough work."""
        assert_that(render.dispatch(NONE), equal_to([render.NOT_ENOUGH_WORK]))

    def test_a_question_with_no_work_prints_no_decision(self) -> None:
        """``next <item>`` of an undecided item prints the one line, briefs nothing."""
        asked = mode.ItemNext(asked=mode.Asked.NEXT, item="o/r#1")
        found = onepath.answered(asked, NOTHING)
        assert_that(found, equal_to(([render.NOT_ENOUGH_WORK], [])))

    def test_a_mode_that_asks_no_question_prints_nothing(self) -> None:
        """The sweep's mode prints no answer of ``next``."""
        found = onepath.answered(mode.Sweep(task_list=""), NOTHING)
        assert_that(found, equal_to(([], [])))

    def test_a_kept_item_gives_a_slot_nothing(self) -> None:
        """An item the read kept is no pick."""
        kept = world.Kept(by=world.Keeper.HOLD, reference=REFERENCE)
        assert_that(onepath.pick(kept), none())

    def test_an_emptied_slot_takes_the_first_when_none_fits(self) -> None:
        """With no decision a slot can take, the line is the answer's first."""
        judgement = ticket_judgement()
        book = test_decide.BOOK
        said = refill.line((judgement, book), test_work.SLOTS, "s1", no_pick)
        first = render.first(judgement.decided.answer)
        assert_that(said, equal_to(f"SLOT s1 NEXT: {first}"))


class TestAct(unittest.TestCase):
    """Plan 6.1 and P8: act looks its verb up in the decisions."""

    def test_dispatch_next_with_no_work_says_so(self) -> None:
        """The head of an empty order is the not-enough-work line."""
        said = knownkit.dispatch(knownshipped.GIVEN, NOTHING)
        assert_that(said, equal_to(render.NOT_ENOUGH_WORK))

    def test_dispatch_next_on_the_command_line(self) -> None:
        """``act dispatch-next`` reads the world once and names its head."""
        done = act_line("dispatch-next", "owner/project")
        assert_that(done.out, equal_to("owner/project#1\n"))

    def test_a_refused_verb_exits_two(self) -> None:
        """A verb that refuses ends the command with status 2 and its reason."""
        done = act_line("label", "owner/project#1", "name=nope")
        errs(done, 2, "act label: refused: label nope is not one pitboss applies")

    def test_no_work_lifts_no_stop(self) -> None:
        """With no decision standing, ``act override`` lifts nothing."""
        assert_that(gateverbs.overridable(NONE, "o/r#1", "a stop"), equal_to(False))


class TestReads(unittest.TestCase):
    """Plan 6.1 and 3.1: each fact is read once into its field."""

    def test_two_items_on_next_exit_two(self) -> None:
        """``next`` names one item at most."""
        with self.assertRaises(SystemExit) as stopped:
            nextcommand.reference(["o/r#1", "o/r#2"], REPO)
        assert_that(stopped.exception.code, equal_to(2))

    def test_a_closing_url_names_its_ticket(self) -> None:
        """``Fixes <issue URL>`` works on that ticket."""
        body = "Fixes https://github.com/o/r/issues/5"
        found = pullnames.names("", body, "work", REPO)
        assert_that(found, equal_to(frozenset({"o/r#5"})))

    def test_a_closing_word_with_no_ticket_names_none(self) -> None:
        """``Fixes the flake`` names no ticket."""
        found = pullnames.names("", "Fixes the flake", "work", REPO)
        assert_that(found, equal_to(frozenset()))

    def test_no_branch_when_git_fails(self) -> None:
        """A directory git cannot read is on no branch."""
        with tempfile.TemporaryDirectory() as base:
            run = fakes.FakeProcesses(bodies={}, cwd=pathlib.Path(base))
            assert_that(pushdraft.current_branch(run), equal_to(""))

    def test_an_idle_pr_is_in_no_category(self) -> None:
        """A PR no actor takes is offered for no round."""
        idle = steps.Idle(pending=steps.Pending.CI)
        facts = test_work.stepped(test_work.facts(3, test_work.NONE), idle)
        assert_that(work.category_of(facts), none())

    def test_a_review_slot_is_named_by_its_pr(self) -> None:
        """A slot of a review names the PR it reviews."""
        slot = slotbook.Slot(name="s1", model="m", task="o/r#3", kind="review")
        assert_that(slotsheader.subject(slot), equal_to("o/r#3"))

    def test_with_no_runners_table_nothing_is_held(self) -> None:
        """No ``[runners]`` table: the runners are not looked at."""
        runners = fakes.settings(fakes.directory()).runners
        assert_that(sweepline.clear(lambda: "not read", runners), equal_to(True))

    def test_an_unreadable_pr_is_settled_as_it_is(self) -> None:
        """A PR whose read failed is in no shared red."""
        read = shapes.Unreadable(reference="o/r#3", call="check-runs", status="500")
        found = sharedred.settle_one(fakes.github({}), read, lambda: [])
        assert_that(found, equal_to(read))

    def test_a_full_page_reads_the_next(self) -> None:
        """Plan 6.2: a page of the page size is not the last one."""
        bodies: dict[str, object] = {
            fakes.page(PLAIN, 1): [issue(n) for n in range(1, 101)],
            fakes.page(PLAIN, 2): [issue(101)],
        }
        found = list(workorder.tickets(fakes.github(bodies), p1_settings()))
        assert_that(len(found), equal_to(101))
        assert_that(found[-1].reference, equal_to("owner/project#101"))


class TestPairs(unittest.TestCase):
    """The pairs of cells name a verdict that disagrees with its parts (6.1)."""

    def test_6_1_a_verdict_that_stops_a_pair_of_goes_is_an_exception(self) -> None:
        """Each cell alone goes; the pair stops with no stop: an exception."""
        base = totalworld.base()
        origin = totalpairs.start(base, "merge")
        changed = [
            (each, set(totalpairs.change_of(origin, each.world)))
            for each in totalcomplete.base_cells()
            if each.action == "merge"
        ]
        first, keys = next((each, keys) for each, keys in changed if keys)
        other = next(each for each, more in changed if more and not more & keys)
        cells, alone, answered = [first, other], 2, itertools.count()

        def verdict(action: str, pull: object, ctx: object) -> gatewords.Answer:
            word = gatewords.GO if next(answered) < alone else gatewords.STOP
            return gatewords.Answer(word=word)

        found = totalpairs.run(base, cells, verdict)
        assert_that(found.exceptions[0], contains_string("want GO"))
