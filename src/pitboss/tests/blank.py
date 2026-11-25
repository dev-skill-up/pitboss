"""Records with every field written out, which a test changes with ``replace``.

The records of the World's closure have no field default (plan 6.1, P3), so a
test that sets a few fields starts from one of these (keyword: one-path).
"""

from .. import blankrecords

GRADED = blankrecords.GRADED
CHECK_RUN = blankrecords.CHECK_RUN
COMMENT = blankrecords.COMMENT
member_comment = blankrecords.member_comment
