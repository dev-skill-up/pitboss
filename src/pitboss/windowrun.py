"""How large a window of tickets ``slots next`` reads (keyword: ticket-window).

``slots next`` prints the PRs and the first tickets of the order, and a brief for
each of the first five. It reads the first ``WINDOW`` tickets, and ``GROWTH``
times as many again while fewer than five items are offered and tickets are left
unread (pitboss#443). The blockers and comments of a ticket are read in the order
of the ranking, only until five items are offered (pitboss#453).
"""

WINDOW = 24
GROWTH = 4
TOP = 5  # the briefs printed (``suggest.TOP``): the items whose blockers are read
UNREAD = (
    "The list ends at its first {count} items: the tickets after them were not"
    " read, so a count of more queued is a lower bound (keyword: ticket-window,"
    " pitboss#443)"
)
