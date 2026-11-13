"""P3 over the World's whole closure (plan 6.1, keyword: one-path)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import proofsource, worldfields

WORLD = (
    "import typing\n"
    "from . import held\n"
    "from .held import Kept\n"
    "Alias = Kept | 'held.Quoted'\n"
    "one, two = 1, 2\n"
    "three = four = 3\n"
    "class World:\n"
    "    first: held.Direct\n"
    "    second: Alias\n"
    "    third: typing.Any\n"
    "    fourth: Kept.Inner\n"
    "    fifth: Missing\n"
    "    sixth: Kept\n"
)
HELD = (
    "from typing import ClassVar\n"
    "class Direct:\n"
    "    count: int = 0\n"
    "    shared: ClassVar[int] = 0\n"
    "class Kept:\n"
    "    name: str = ''\n"
    "class Quoted:\n"
    "    when: str = ''\n"
    "class Unheld:\n"
    "    never: str = ''\n"
)


class TestClosure(unittest.TestCase):
    """Plan 6.1: no record the World holds, however deep, has a default."""

    def test_6_1_every_record_reached_is_read(self) -> None:
        """A module's record, an imported one, an alias and a quoted one count."""
        texts = {"src/pitboss/world.py": WORLD, "src/pitboss/held.py": HELD}
        found = worldfields.defaults(proofsource.of_texts(texts))
        want = [
            "P3: held.Direct.count has a default",
            "P3: held.Kept.name has a default",
            "P3: held.Quoted.when has a default",
        ]
        assert_that(found, equal_to(want))
