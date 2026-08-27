"""Freshness checking for the `nmg2-findings` notes.

A note declares the facts it rests on; `checker` re-derives them and reports
MOVED, UNRESOLVABLE, MALFORMED, OK — or UNPINNED for a note that declared
nothing. `freshness.checker` carries the format and the reasoning.
"""
