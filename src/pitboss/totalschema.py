"""The PR object's documented fields and their types (keyword: total-verdict).

Read from ``enumeration/pull-fields.tsv`` (GitHub's 201 schema of "Create a pull
request"), with the two fields every real response has that the extraction lost,
and ``auto_merge`` as the docs give it: a nullable object.
"""

import functools
from typing import Mapping

from . import enumeration, schematypes

AUTO_MERGE = "required, object or null (docs: Auto merge, nullable)"
EXTRA = {
    "assignee": "object or null (Simple User)",
    "merge_commit_sha": "string or null",
}


@functools.cache
def schema() -> Mapping[str, str]:
    """Every documented field of a PR, with its declaration.

    Returns:
        The declaration of each field (``required, integer``, ``string or null``).
    """
    found = {
        line.split("\t")[0]: line.split("\t")[1]
        for line in enumeration.lines_of(enumeration.shipped(enumeration.PULL_FIELDS))
    }
    return {**found, "auto_merge": AUTO_MERGE, **EXTRA}


head_of = schematypes.head_of
required = schematypes.required
typed = schematypes.typed
