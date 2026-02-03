#!/usr/bin/env python3
"""
OneNote FTS SQLite → Markdown exporter.

Reads the FullTextSearchIndex databases from OneNote Mac's local cache
and exports each page as a .md file organized by Notebook/Section/page-title.md
"""

import sqlite3
import os
import re
import sys

FTS_DIR = os.path.expanduser(
    "~/Library/Containers/com.microsoft.onenote.mac/Data/Library/"
    "Application Support/Microsoft User Data/OneNote/15.0-restore/FullTextSearchIndex"
)

OUTPUT_DIR = os.path.expanduser("~/Desktop/OneNote-Export")

# Map of db filename → expected notebook (for reference only; we read Title from DB)
DATABASES = [
    "{3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}.db",   # Work (413)
    "{D62C1D86-38B0-0B4C-9A45-7259DDD20395}{51}.db",   # Personal (160)
    "{D62C1D86-38B0-0B4C-9A45-7259DDD20395}{10}.db",   # Morton Rainey 的筆記本 (8)
    "{248E7F28-E3C6-AC43-A45F-8A5936C978E7}{10}.db",   # Evernote (5)
    "{5497DFA7-B4A4-EC49-95F1-9B049B091C4E}{10}.db",   # 7rendMicro (1)
]


def sanitize_filename(name):
    """Make a string safe for use as a file/directory name."""
    if not name:
        return "Untitled"
    # Replace problematic characters
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    # Collapse multiple spaces/underscores
    name = re.sub(r'[\s_]+', ' ', name).strip()
    # Truncate to reasonable length
    if len(name) > 100:
        name = name[:100].strip()
    return name or "Untitled"


def export_db(db_path):
    """Export all pages from one FTS database to Markdown files."""
    if not os.path.exists(db_path):
        print(f"  SKIP: {db_path} not found")
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get notebook name (Type=4)
    cur.execute("SELECT GOID, Title FROM Entities WHERE Type=4 LIMIT 1")
    nb_row = cur.fetchone()
    if not nb_row:
        print(f"  SKIP: No notebook entity found in {os.path.basename(db_path)}")
        conn.close()
        return 0

    notebook_name = sanitize_filename(nb_row["Title"])
    notebook_goid = nb_row["GOID"]
    print(f"\n  Notebook: {notebook_name}")

    # Get sections (Type=2)
    cur.execute("SELECT rowid, GOID, Title FROM Entities WHERE Type=2 ORDER BY rowid")
    sections = {row["GOID"]: sanitize_filename(row["Title"]) for row in cur.fetchall()}
    print(f"  Sections: {len(sections)}")

    # Get pages (Type=1) with their parent section
    cur.execute("""
        SELECT rowid, GOID, Title, ParentGOID
        FROM Entities
        WHERE Type=1
        ORDER BY rowid
    """)
    pages = cur.fetchall()
    print(f"  Pages: {len(pages)}")

    exported = 0
    for page in pages:
        page_rowid = page["rowid"]
        page_title = page["Title"] or "Untitled"
        parent_goid = page["ParentGOID"]

        # Determine section name
        section_name = sections.get(parent_goid, "Unsorted")

        # Get page elements (text content)
        cur.execute("""
            SELECT Text FROM PageElements
            WHERE EntityRowId = ?
            ORDER BY rowid
        """, (page_rowid,))
        elements = cur.fetchall()

        if not elements:
            # Skip pages with no text content
            continue

        # Build markdown content
        lines = [f"# {page_title}\n"]
        for elem in elements:
            text = elem["Text"]
            if text:
                lines.append(text)

        md_content = "\n\n".join(lines) + "\n"

        # Create directory structure
        safe_title = sanitize_filename(page_title)
        dir_path = os.path.join(OUTPUT_DIR, notebook_name, section_name)
        os.makedirs(dir_path, exist_ok=True)

        # Handle duplicate filenames
        md_path = os.path.join(dir_path, f"{safe_title}.md")
        if os.path.exists(md_path):
            i = 2
            while os.path.exists(os.path.join(dir_path, f"{safe_title} ({i}).md")):
                i += 1
            md_path = os.path.join(dir_path, f"{safe_title} ({i}).md")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        exported += 1

    conn.close()
    return exported


def main():
    total = 0
    print(f"FTS directory: {FTS_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")

    for db_name in DATABASES:
        db_path = os.path.join(FTS_DIR, db_name)
        print(f"\nProcessing: {db_name}")
        count = export_db(db_path)
        print(f"  Exported: {count} pages")
        total += count

    print(f"\n{'='*50}")
    print(f"Total exported: {total} pages")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
