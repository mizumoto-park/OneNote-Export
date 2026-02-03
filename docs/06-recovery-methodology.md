# Complete Recovery Methodology

## Goal

Recover all notes from the OneNote macOS local cache, producing:

```
exported_md/
├── index.md                     ← Directory index of all notes
├── Work/                        ← Notebook
│   ├── AWS/                     ← Section
│   │   ├── page-title.md        ← Page (text + image references)
│   │   ├── page-title_images/   ← Images for this page
│   │   │   ├── image_001.png
│   │   │   └── image_002.jpg
│   │   └── ...
│   └── ...
├── Personal/
├── Evernote/
├── Morton_Rainey/
└── 7rendMicro/
```

## Seven-Step Recovery Process

### Step 1: Load FTSI Page Hierarchy

Read the Entities table from 5 FTSI SQLite databases:

```python
# Input: 5 FTSI .db files
# Output: Complete hierarchy of 587 pages (Notebook → Section → Page)

for db_file, notebook_name in NOTEBOOKS:
    conn = sqlite3.connect(db_path)

    # Build Section lookup table
    sections = {}
    for goid, title in conn.execute(
        "SELECT GOID, Title FROM Entities WHERE Type = 2"
    ):
        sections[goid] = title

    # Read all pages
    for row in conn.execute(
        "SELECT rowid, GOID, GUID, ParentGOID, Title "
        "FROM Entities WHERE Type = 1"
    ):
        section_name = sections[row[3]]  # ParentGOID → Section Title

        # Read page content elements
        elements = conn.execute(
            "SELECT Text, Jcid FROM PageElements WHERE EntityRowId = ?",
            (row[0],)
        ).fetchall()

        texts       = [t for t, j in elements if j == 393230 and t]
        image_alts  = [t for t, j in elements if j == 393233 and t]
        file_names  = [t for t, j in elements if j == 393269 and t]
```

### Step 2: Classify All Cache .bin Files

Scan 2,039 .bin files and classify using magic bytes:

```python
# Input: All .bin files in cache/ directory
# Output: Type (IMAGE/DATA) + whether it's page data for each file

for fname in os.listdir(CACHE_DIR):
    with open(filepath, 'rb') as f:
        header = f.read(8)

    if header[:4] == b'\x89PNG':       type = 'IMAGE/PNG'
    elif header[:3] == b'\xff\xd8\xff': type = 'IMAGE/JPEG'
    elif header[:4] == b'GIF8':        type = 'IMAGE/GIF'
    elif header[:4] == b'%PDF':        type = 'IMAGE/PDF'
    elif header[:4] == b'PK\x03\x04': type = 'IMAGE/ZIP'
    else:                              type = 'DATA'

    # Among DATA files, those containing "PageTitle" (UTF-16LE) are page data
    if type == 'DATA' and size >= 4096:
        if b'P\x00a\x00g\x00e\x00T\x00i\x00t\x00l\x00e\x00' in data:
            is_page = True
```

Result: 592 page data + 1,313 images + 134 other data

### Step 3: GUID Byte Matching

Map FTSI pages to cache .bin files:

```python
# Input: FTSI page GUIDs + page data .bin files
# Output: Each FTSI page ↔ its corresponding .bin file

for page_bin in page_data_bins:
    data = open(page_bin.filepath, 'rb').read()
    for guid_bytes, page_info in guid_lookup.items():
        if guid_bytes in data:
            page_info['bin_file'] = page_bin
            break
```

Match rate: 94.9% (558/587 pages successfully matched)

### Step 4: Sequential Allocation Mapping

Find the images belonging to each page:

```python
# Rule: Scan forward from page data — all IMAGE files
#       belong to this page until the next DATA (>=4KB) is encountered

for page_bin in matched_pages:
    images = []
    for next_file in files_after(page_bin):
        if next_file.type == 'IMAGE':
            images.append(next_file)
        elif next_file.is_page or (next_file.type == 'DATA' and next_file.size >= 4096):
            break
    page_bin['images'] = images
```

Result: 1,246 images mapped to 160 pages

### Step 5: Extract Embedded PNGs

Extract large embedded images (>100x100 pixels) from page data:

```python
# Search for PNG signature → IEND marker, extract complete PNG data
# Filter out small UI icons (<=100x100)
```

Result: 15 large embedded images

### Step 6: Export

Write all data to the filesystem:

```python
for page in all_pages:
    # Create directory: Notebook/Section/
    os.makedirs(f"{OUTPUT}/{notebook}/{section}/")

    # Write Markdown
    with open(f".../{title}.md", 'w') as f:
        f.write(f"# {page.title}\n\n")
        f.write(f"> **Notebook:** {notebook} / **Section:** {section}\n\n")
        for text in page.texts:
            f.write(text + "\n")
        for img in page.images:
            f.write(f"![image]({title}_images/{img.name})\n")

    # Copy images
    for img in page.images:
        shutil.copy2(img.cache_path, f".../{title}_images/{img.name}")
```

### Step 7: Generate Index

Generate `index.md` containing a directory tree with links for all notebooks, sections, and pages.

---

## Recovery Statistics

| Item | Count |
|------|-------|
| Exported pages | 587 |
| Sequentially mapped images | 1,246 |
| Embedded images | 15 |
| No cache file (text only) | 29 |
| Total export size | 1.4 GB |

### By Notebook

| Notebook | Pages | Sections |
|----------|-------|----------|
| Work | 413 | 22 |
| Personal | 160 | 30 |
| Evernote | 5 | 1 |
| Morton Rainey | 8 | 2 |
| 7rendMicro | 1 | 1 |

---

## Tools

The complete recovery tool is located at:

```
scripts/extract_md.py
```

Usage:
```bash
uv run python scripts/extract_md.py
```

No external packages required — only Python 3 standard library (sqlite3, struct, uuid, shutil).

---

## Known Limitations

1. **29 pages with no cache**: These pages may have never fully synced locally; only FTSI text can be exported
2. **Table formatting lost**: FTSI PageElements are flat text and don't preserve table/list structure
3. **Minor image misattribution possible**: The sequential allocation model may err near deleted pages
4. **Attachments are filename-only**: FTSI only stores attachment filenames (Jcid=393269); actual attachments are in cache .bin but harder to identify
5. **Font/formatting lost**: Although page data contains font info (Calibri, etc.), extracting full rich text formatting requires complete MS-ONESTORE protocol parsing
6. **Revision history not extracted**: Cache may contain historical versions of pages; currently only the latest version is used
