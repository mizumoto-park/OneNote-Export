#!/usr/bin/env python3
"""
Generate index.md for the OneNote export.
Lists all notebooks, sections, and pages with relative links.
"""

import os
from urllib.parse import quote

EXPORT_DIR = os.path.expanduser("~/Desktop/OneNote-Export")
NOTEBOOKS = ["Work", "Personal", "Morton Rainey 的筆記本", "Evernote", "7rendMicro"]


def main():
    lines = ["# OneNote Export Index\n"]

    total_pages = 0
    total_sections = 0

    for notebook in NOTEBOOKS:
        nb_path = os.path.join(EXPORT_DIR, notebook)
        if not os.path.isdir(nb_path):
            continue

        sections = sorted([
            d for d in os.listdir(nb_path)
            if os.path.isdir(os.path.join(nb_path, d))
        ])

        # Count pages
        nb_pages = 0
        for section in sections:
            sec_path = os.path.join(nb_path, section)
            pages = [f for f in os.listdir(sec_path) if f.endswith('.md')]
            nb_pages += len(pages)

        lines.append(f"\n## {notebook} ({nb_pages} pages, {len(sections)} sections)\n")
        total_pages += nb_pages
        total_sections += len(sections)

        for section in sections:
            sec_path = os.path.join(nb_path, section)
            pages = sorted([
                f for f in os.listdir(sec_path) if f.endswith('.md')
            ])

            sec_rel = quote(f"{notebook}/{section}")
            lines.append(f"\n### [{section}]({sec_rel}/) ({len(pages)} pages)\n")

            for page_file in pages:
                page_name = page_file[:-3]  # remove .md
                page_rel = quote(f"{notebook}/{section}/{page_file}")
                lines.append(f"- [{page_name}]({page_rel})")

    # Attachments section
    att_dir = os.path.join(EXPORT_DIR, "_attachments")
    if os.path.isdir(att_dir):
        att_count = len([f for f in os.listdir(att_dir) if f != "index.md"])
        lines.append(f"\n## Attachments ({att_count} files)\n")
        lines.append(f"- [Attachments Index](_attachments/index.md)")

    # Summary at top
    summary = [
        lines[0],
        "",
        f"**Total: {total_pages} pages across {total_sections} sections in {len(NOTEBOOKS)} notebooks**\n",
    ]
    lines = summary + lines[1:]

    index_path = os.path.join(EXPORT_DIR, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Index written: {index_path}")
    print(f"  {total_pages} pages, {total_sections} sections")


if __name__ == "__main__":
    main()
