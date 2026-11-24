"""The input each reader reads, one reader for each input (capability, #524).

A listed module that reads one of the inputs the decision's Observation holds names it
here. Two modules that name the same input are a second read of it (E13): the
Observation is made from one read of each input, so a second reader would let the
decision see two answers to one question. Adding a line is a reviewed change.
"""

from typing import Mapping

INPUTS: Mapping[str, str] = {
    "src/pitboss/ledger.py": "ledger",
    "src/pitboss/ownerrepos.py": "owner-repositories",
    "src/pitboss/pulls.py": "pull-requests",
    "src/pitboss/slotlog.py": "slot-log",
    "src/pitboss/ticketclosed.py": "closed-tickets",
    "src/pitboss/worktrees.py": "worktrees",
}
