#!/usr/bin/env python3
"""Check that the skill's references and pitboss's markers agree, both ways.

Every marker pitboss prints (``pitboss.markers.Marker``) must be explained in
the skill's references, and every marker the references name (a backticked
run of capital words) must be one pitboss prints. Exits non-zero on failure.
"""

import pathlib
import re
import sys

from pitboss import markercheck
from pitboss.markers import SELF_EXPLAINED, Marker

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCES = sorted(ROOT.glob("plugins/*/skills/*/references/*.md"))
NAMED = re.compile(r"`([A-Z][A-Z0-9 -]*[A-Z0-9])`")


def main():
    text = "\n".join(path.read_text() for path in REFERENCES)
    printed = {marker.text for marker in Marker}
    own = {marker.text for marker in SELF_EXPLAINED}
    found = markercheck.errors(printed, own, set(NAMED.findall(text)))
    for error in found:
        print(f"FAIL: {error}")
    if found:
        sys.exit(1)
    print(markercheck.summary(printed, own, len(REFERENCES)))


if __name__ == "__main__":
    main()
