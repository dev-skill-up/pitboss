"""The comparison of printed markers with the references' (pitboss#369)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import markercheck

PRINTED = {"ALPHA", "BETA", "OWN"}


class TestMarkerCheck(unittest.TestCase):
    """What the check accepts, and the nearest inputs it must still reject."""

    def test_a_printed_marker_outside_the_set_and_unnamed_fails(self) -> None:
        """BETA is printed, not self-explained and named in no reference."""
        found = markercheck.errors(PRINTED, {"OWN"}, {"ALPHA"})
        assert_that(
            found, equal_to(["marker 'BETA' is not explained in the references"])
        )

    def test_a_named_marker_pitboss_never_prints_fails(self) -> None:
        """A reference names GAMMA, which is no marker."""
        found = markercheck.errors(PRINTED, {"OWN"}, {"ALPHA", "BETA", "GAMMA"})
        assert_that(
            found,
            equal_to(["the references name 'GAMMA', which pitboss never prints"]),
        )

    def test_a_self_explained_marker_needs_no_reference(self) -> None:
        """OWN is named nowhere and passes; the count says how many explain."""
        found = markercheck.errors(PRINTED, {"OWN"}, {"ALPHA", "BETA"})
        assert_that(found, equal_to([]))
        said = markercheck.summary(PRINTED, {"OWN"}, 6)
        assert_that(
            said,
            equal_to(
                "all 3 markers: 2 explained in 6 references,"
                " 1 explained by their own line"
            ),
        )
