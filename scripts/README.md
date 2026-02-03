# OneNote Export Scripts

## Core Tools

### `extract_md.py` — Markdown Extractor (Final)

Extracts all pages from the OneNote macOS local cache into structured Markdown files with images:

1. Loads 587 pages from FTSI SQLite databases (Notebook/Section/Page hierarchy)
2. Classifies 2,039 cache .bin files (IMAGE vs DATA)
3. GUID byte matching: FTSI pages to cache .bin files (94.9% match rate)
4. Sequential allocation mapping: assigns 1,246 images to their pages
5. Extracts embedded PNGs (>100x100)
6. Exports .md + images to `exported_md/` (Notebook/Section/ directory structure)
7. Generates index.md directory listing

```bash
uv run python scripts/extract_md.py
```

No external dependencies, only Python 3 standard library.

### `export_pdf.py` — PDF Exporter

Reads the exported Markdown + images from `exported_md/` and converts each page to a styled PDF:

- Uses weasyprint with HTML as intermediate format
- Font: Noto Sans CJK TC (Traditional Chinese)
- Interleaves images among text blocks
- Outputs to `exported_pdf/`, preserving Notebook/Section directory structure

```bash
# Export all pages
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python scripts/export_pdf.py

# Export a specific page
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python scripts/export_pdf.py --page "page name"

# Test with first N pages
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python scripts/export_pdf.py --test 5
```

Dependencies: weasyprint (`uv add weasyprint`), Noto Sans CJK TC font (`brew install --cask font-noto-sans-cjk-tc`)

### Legacy Scripts (kept for reference)

- `export_markdown.py` — Predecessor of `extract_md.py`, text-only export (no images)
- `extract_images.py` — Brute-force image extraction via magic bytes scanning. Superseded by `extract_md.py`'s sequential allocation
- `generate_index.py` — Standalone index generator, now integrated into `extract_md.py`

## Archived Tools (`archive/`)

`archive/` contains 29 experimental scripts from the development process:

### PDF UI Automation Export (Failed)

Attempted to automate OneNote PDF export via AppleScript + Accessibility API:

- `export_pdf.py` — Initial full automation (notebook/section switching failed)
- `export_pdf_v2.py` ~ `export_pdf_v11.py` — Multiple iteration attempts
- `export_pdf_simple.py` — Simplified version (gave up notebook switching, Cmd+PageDown only)
- `export_pdf_blind.py` — Blind operation version
- `export_pdf_applescript.sh` — Pure AppleScript version

Failed because OneNote Mac's sidebar UI element paths change after interaction, making stable targeting impossible.

### UI Debugging Tools

Used to analyze OneNote's Accessibility tree during PDF automation development:

- `inspect_ui.py`, `hunt_ui.py`, `find_ui_lists.py` — UI element search
- `check_group5.py`, `inspect_child5.py`, `search_every_group.py` — Deep search
- `debug_dialog.py`, `inspect_dialog.py` — Save As dialog debugging
- `debug_title.py`, `get_geometry.py` — Window title/position
- `auto_diagnose.py`, `diagnose_save.py` — Auto diagnostics
- `test_onenote.py`, `test_click.py`, `trace_test.py` — Operation tests
- `find_page_list.py` — Page list location attempts
