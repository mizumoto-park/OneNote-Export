# 📓 OneNote-Export

Recover notes from the OneNote for Mac local cache when cloud sync is broken.

## 💡 Why This Exists

OneNote for Mac stopped syncing properly — notebooks became inaccessible through the app. Fortunately, the local cache on disk still contained all the data: 587 pages across 5 notebooks, complete with text, images, and attachments.

This project reverse-engineers the OneNote macOS local cache format and extracts everything into:

- 📝 **Markdown + images** (`exported_md/`) — for use in [Obsidian](https://obsidian.md/) or any Markdown-based note system
- 📄 **Styled PDFs** (`exported_pdf/`) — for direct reading and archiving

## 📊 What It Recovers

| Item | Count |
|------|-------|
| 📄 Pages | 587 |
| 🖼️ Images (sequential allocation) | 1,246 |
| 🔍 Embedded images (extracted from binary) | 15 |
| 📓 Notebooks | 5 |
| 📁 Sections | 56 |

## ⚙️ How It Works

OneNote stores two complementary data sources in its local cache:

1. 🗄️ **FTSI SQLite databases** — structured metadata: page hierarchy (Notebook/Section/Page), text content, image alt-text, attachment filenames
2. 📦 **Cache .bin files** — binary data: page content and image files using base-36 sequential numbering

The extraction pipeline:

1. Load page hierarchy from FTSI databases
2. Classify 2,039 cache .bin files by magic bytes (IMAGE vs DATA)
3. 🔗 Match FTSI pages to .bin files via GUID byte search (94.9% match rate)
4. 🧩 Attribute images to pages using sequential allocation pattern
5. Extract embedded PNGs from page binary data
6. Export Markdown + images, then optionally convert to PDF

See [docs/](docs/) for detailed technical documentation on the cache format, GUID matching, and sequential allocation model.

## 🚀 Usage

### Export Markdown

```bash
uv run python scripts/extract_md.py
```

No external dependencies — Python 3 standard library only.

### Export PDF

```bash
# Install dependencies
uv add weasyprint
brew install --cask font-noto-sans-cjk-tc

# Export
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python scripts/export_pdf.py

# Export a single page (for testing)
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python scripts/export_pdf.py --page "page name"
```

## 📂 Output Structure

```
exported_md/                    exported_pdf/
├── Work/                       ├── Work/
│   ├── AWS/                    │   ├── AWS/
│   │   ├── page.md             │   │   └── page.pdf
│   │   └── page_images/        │   └── ...
│   │       ├── image_001.png   ├── Personal/
│   │       └── image_002.jpg   └── ...
│   └── ...
├── Personal/
└── index.md
```

## 📚 Documentation

- [00-overview.md](docs/00-overview.md) — Cache structure overview
- [01-directory-structure.md](docs/01-directory-structure.md) — Full directory layout
- [02-ftsi-database-schema.md](docs/02-ftsi-database-schema.md) — FTSI SQLite schema
- [03-cache-bin-format.md](docs/03-cache-bin-format.md) — Binary cache file format
- [04-guid-matching.md](docs/04-guid-matching.md) — GUID byte matching mechanism
- [05-sequential-allocation.md](docs/05-sequential-allocation.md) — Image attribution model
- [06-recovery-methodology.md](docs/06-recovery-methodology.md) — Complete recovery methodology
- [07-ftsi-hierarchy-deep-dive.md](docs/07-ftsi-hierarchy-deep-dive.md) — FTSI hierarchy deep dive

## ⚠️ Known Limitations

- 29 pages had no local cache (never fully synced) — text-only export from FTSI
- Table/list formatting is lost (FTSI stores flat text)
- Font and rich text styling not preserved
- Image attribution may have minor errors near deleted pages
