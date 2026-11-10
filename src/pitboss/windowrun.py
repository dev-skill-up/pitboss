"""How large a window of tickets ``slots next`` reads (keyword: ticket-window).

``slots next`` prints the PRs and the first tickets of the order, and a brief for
each of the first five. It reads the first ``WINDOW`` tickets, and ``GROWTH``
times as many again while fewer than five items are offered and tickets are left
unread (pitboss#443).
"""

WINDOW = 24
GROWTH = 4
UNREAD = (
    "The list ends at its first {count} items: the tickets after them were not"
    " read, so a count of more queued is a lower bound (keyword: ticket-window,"
    " pitboss#443)"
)
