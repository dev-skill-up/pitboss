"""The standard library's ``Any`` is cast away once (keyword: typed-std, #524)."""

import re
import unittest

from hamcrest import assert_that, contains_exactly, equal_to, is_, none

from .. import typedstd


class TestTypedStd(unittest.TestCase):
    """Each wrapper gives what the standard library gives, typed."""

    def test_a_group_is_its_text_and_empty_when_it_took_no_part(self) -> None:
        """A group is its text and empty when it took no part."""
        found = re.match(r"(a)(b)?", "a")
        assert found
        assert_that(typedstd.group(found, 1), equal_to("a"))
        assert_that(typedstd.group(found, 2), equal_to(""))

    def test_findall_gives_the_group_or_the_whole_match(self) -> None:
        """Findall gives the group or the whole match."""
        assert_that(typedstd.findall(r"a(b)", "ab ab"), contains_exactly("b", "b"))
        both = typedstd.findall(re.compile(r"b+"), "ab bb")
        assert_that(both, contains_exactly("b", "bb"))

    def test_newest_is_the_greatest_and_none_for_none(self) -> None:
        """Newest is the greatest and none for none."""
        assert_that(typedstd.newest(["a", "c", "b"], lambda each: each), equal_to("c"))
        assert_that(typedstd.newest([], lambda each: str(each)), is_(none()))

    def test_memo_runs_once(self) -> None:
        """Memo runs once."""
        calls: list[int] = []

        def make() -> int:
            calls.append(1)
            return len(calls)

        once = typedstd.memo(make)
        assert_that((once(), once(), len(calls)), equal_to((1, 1, 1)))

    def test_split_gives_the_pieces(self) -> None:
        """Split gives the pieces."""
        assert_that(typedstd.split(r"-", "a-b"), contains_exactly("a", "b"))

    def test_loads_reads_any_value(self) -> None:
        """Loads reads any value."""
        assert_that(typedstd.loads('{"a": [1]}'), equal_to({"a": [1]}))

    def test_members_are_a_mapping_of_text_keys_or_none(self) -> None:
        """Members are a mapping of text keys or none."""
        assert_that(typedstd.members({"a": 1}), equal_to({"a": 1}))
        assert_that(typedstd.members([1]), is_(none()))

    def test_items_are_a_list_or_none(self) -> None:
        """Items are a list or none."""
        assert_that(typedstd.items([1, "a"]), equal_to([1, "a"]))
        assert_that(typedstd.items({"a": 1}), is_(none()))

    def test_unique_keeps_the_first_of_each_in_order(self) -> None:
        """Unique keeps the first of each in order."""
        assert_that(typedstd.unique(["b", "a", "b"]), contains_exactly("b", "a"))
