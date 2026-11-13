"""Each command that asks of the decisions has a constructor of its own (plan 6.1)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import answer, mode, modeextent, onepath, readextent

ITEM = "o/r#5"
LISTS: Sequence[mode.Mode] = (
    mode.Next(),
    mode.SlotsNext(),
    mode.FreeCheck(),
    mode.Tasks(),
    mode.Free(),
    mode.Heard(),
    mode.Watch(),
)
NAMES: Sequence[mode.Mode] = (
    mode.NextItem(item=ITEM),
    mode.SlotsNextItem(item=ITEM),
    mode.Merge(item=ITEM),
    mode.Arm(item=ITEM),
    mode.Undraft(item=ITEM),
    mode.PinsReview(item=ITEM),
)
QUIET: Sequence[mode.Mode] = (
    mode.DispatchNext(want="", options={}),
    mode.Sweep(task_list=""),
    mode.OverrideAct(item=ITEM, stop="s", reason="r"),
    mode.MechanicalPush(arguments=["origin"]),
    mode.Other(command="clean"),
)
NO_WORK = answer.Decided(answer=answer.NotEnoughWork(), by_item={})


class TestEachConstructor(unittest.TestCase):
    """Plan 6.1: one constructor for each command, action and item form."""

    def test_6_1_the_constructors_are_the_mode(self) -> None:
        """``NAMES`` lists every constructor of ``Mode`` once."""
        every = [type(each).__name__ for each in (*LISTS, *NAMES, *QUIET)]
        assert_that(sorted(mode.NAMES), equal_to(sorted(every)))

    def test_6_1_a_list_form_lists_and_an_item_form_reads_its_item(self) -> None:
        """Each list form lists and reads no item; each item form reads its item."""
        found = [
            (
                mode.question_of(each).answers,
                mode.item_of(each),
                modeextent.extent_of(each),
            )
            for each in (*LISTS, *NAMES)
        ]
        listed = (mode.Answers.LIST, "", readextent.naming([]))
        named = (mode.Answers.ITEM, ITEM, readextent.naming([ITEM]))
        assert_that(found, equal_to([listed] * len(LISTS) + [named] * len(NAMES)))

    def test_6_1_the_other_modes_read_what_they_ask(self) -> None:
        """Dispatch and the rest read nothing named; the sweep every PR; a push its."""
        found = [modeextent.extent_of(each) for each in QUIET]
        want = [
            readextent.naming([]),
            readextent.EVERY_PULL,
            readextent.naming([ITEM]),
            readextent.pushing(["origin"]),
            readextent.naming([]),
        ]
        assert_that(found, equal_to(want))

    def test_6_1_each_form_answers_as_its_command(self) -> None:
        """A list form prints the list; an item form the item's; the rest nothing."""
        found = [len(onepath.answered(each, NO_WORK)[0]) for each in (*LISTS, *NAMES)]
        quiet = [onepath.answered(each, NO_WORK) for each in QUIET]
        assert_that((min(found), quiet), equal_to((1, [([], [])] * len(QUIET))))
