"""Discover OneNote for Mac local-cache data sources at runtime.

No user-specific values are hardcoded: the data directory is located
inside the standard app container (or via $ONENOTE_BASE), and the
notebook list is derived from the FTSI databases themselves.

All database access is read-only; the OneNote cache must never be
modified.
"""

import os
import sqlite3
from urllib.parse import quote

CONTAINER = (
    "~/Library/Containers/com.microsoft.onenote.mac/Data/Library/"
    "Application Support/Microsoft User Data/OneNote"
)


def connect_ro(db_path):
    """Open a SQLite database in read-only mode."""
    uri = "file:" + quote(os.path.abspath(db_path)) + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def find_onenote_base():
    """Return the OneNote data dir containing FullTextSearchIndex/ and cache/.

    Honors $ONENOTE_BASE, then the standard container path. When several
    version dirs qualify, prefers the live data over *-restore snapshots.
    """
    override = os.environ.get("ONENOTE_BASE")
    if override:
        if not (os.path.isdir(os.path.join(override, "FullTextSearchIndex"))
                and os.path.isdir(os.path.join(override, "cache"))):
            raise SystemExit(
                f"ONENOTE_BASE={override} has no FullTextSearchIndex/ or cache/"
            )
        return override

    container = os.path.expanduser(CONTAINER)
    qualifying = [
        d for d in os.listdir(container)
        if os.path.isdir(os.path.join(container, d, "FullTextSearchIndex"))
        and os.path.isdir(os.path.join(container, d, "cache"))
    ] if os.path.isdir(container) else []

    live = sorted(d for d in qualifying if not d.endswith("-restore"))
    if live:
        return os.path.join(container, live[-1])
    if qualifying:
        return os.path.join(container, sorted(qualifying)[-1])

    raise SystemExit(
        f"OneNote data not found under {container}\n"
        "Set ONENOTE_BASE to a directory containing FullTextSearchIndex/ and cache/"
    )


def discover_notebooks(db_dir):
    """Return [(db_filename, notebook_title)] for every notebook DB in db_dir.

    A notebook DB is a database whose Entities table holds a notebook
    entity (Type = 4); the title comes from that row, falling back to
    the DB filename. Anything else in db_dir is skipped.
    """
    notebooks = []
    for fname in sorted(os.listdir(db_dir)):
        if not fname.endswith(".db"):
            continue
        db_path = os.path.join(db_dir, fname)
        try:
            conn = connect_ro(db_path)
            row = conn.execute(
                "SELECT Title FROM Entities WHERE Type = 4 LIMIT 1"
            ).fetchone()
            conn.close()
        except sqlite3.Error:
            continue  # not an Entities database
        if row is None:
            continue  # no notebook entity
        title = (row[0] or "").strip() or fname[:-3]
        notebooks.append((fname, title))
    return notebooks
