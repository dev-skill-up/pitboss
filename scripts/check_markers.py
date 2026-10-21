#!/usr/bin/env python3
"""Check that the skill's references and pitboss's markers agree, both ways.

Every marker pitboss prints (``pitboss.markers.Marker``) must be explained in
the skill's references, and every marker the references name (a backticked
run of capital words) must be one pitboss prints. Exits non-zero on failure.
"""

import pathlib
import re
import sys

from pitboss.markers import Marker

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCES = sorted(ROOT.glob("plugins/*/skills/*/references/*.md"))
NAMED = re.compile(r"`([A-Z][A-Z -]*[A-Z])`")


def main():
    text = "\n".join(path.read_text() for path in REFERENCES)
    printed = {marker.text for marker in Marker}
    named = set(NAMED.findall(text))
    errors = [
        *(
            f"marker {name!r} is not explained in the references"
            for name in sorted(printed - named)
        ),
        *(
            f"the references name {name!r}, which pitboss never prints"
            for name in sorted(named - printed)
        ),
    ]
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        sys.exit(1)
    print(f"all {len(printed)} markers explained in {len(REFERENCES)} references")


if __name__ == "__main__":
    main()
