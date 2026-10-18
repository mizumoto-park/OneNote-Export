#!/usr/bin/env python3
"""
OneNote Local Cache → Markdown + Images Extractor

Extracts all pages from the OneNote macOS local cache into a structured
directory of Markdown files with associated images.

Data sources:
- FTSI SQLite databases: page hierarchy (notebook/section/page) and text content
- Cache .bin files: page binary data and image files
- GUID byte matching: links FTSI pages to their cache bin files (94.9% match rate)
- Sequential allocation: images between consecutive page files belong to the earlier page
"""

import os
import sys
import re
import json
import time
import sqlite3
import struct
import uuid
import shutil
from collections import defaultdict
from pathlib import Path

# === Configuration ===
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "exported_md")

from onenote_source import find_onenote_base, discover_notebooks, connect_ro

ONENOTE_BASE = find_onenote_base()
CACHE_DIR = os.path.join(ONENOTE_BASE, "cache")
DB_DIR = os.path.join(ONENOTE_BASE, "FullTextSearchIndex")

# Notebooks discovered at runtime: every DB in DB_DIR holding a notebook
# entity (Type=4); the display name is read from the database itself.
NOTEBOOKS = discover_notebooks(DB_DIR)

if not NOTEBOOKS:
    raise SystemExit(f"No notebook databases found in {DB_DIR}")

# Image file signatures
IMAGE_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'png',
    b'\xff\xd8\xff': 'jpg',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'%PDF': 'pdf',
    b'PK\x03\x04': 'zip',
}

PAGE_TITLE_MARKER = "PageTitle".encode('utf-16-le')


def base36_to_int(s):
    return int(s, 36)


def int_to_base36(n):
    if n == 0:
        return '0'
    digits = []
    while n:
        digits.append("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[n % 36])
        n //= 36
    return ''.join(reversed(digits)).rjust(8, '0')


def guid_to_bytes_le(guid_str):
    """Convert GUID string to mixed-endian (little-endian) bytes for binary search."""
    g = guid_str.strip('{}')
    return uuid.UUID(g).bytes_le


def classify_bin_file(filepath):
    """Classify a bin file as IMAGE or DATA based on magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
        for sig, ext in IMAGE_SIGNATURES.items():
            if header[:len(sig)] == sig:
                return ('IMAGE', ext)
        return ('DATA', None)
    except:
        return ('ERROR', None)


def sanitize_filename(name):
    """Make a string safe for use as a filename."""
    if not name:
        return "untitled"
    # Replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name).strip()
    name = name.strip('.')
    if not name:
        return "untitled"
    # Limit length
    if len(name) > 100:
        name = name[:100]
    return name


def get_image_dimensions(ext, data):
    """Return (width, height) for PNG/JPEG bytes, else (None, None)."""
    try:
        if ext == 'png' and data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
            return struct.unpack('>II', data[16:24])
        if ext == 'jpg' and data[:3] == b'\xff\xd8\xff':
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack('>HH', data[i + 5:i + 9])
                    return w, h
                if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                seglen = struct.unpack('>H', data[i + 2:i + 4])[0]
                if seglen < 2:
                    return None, None
                i += 2 + seglen
    except Exception:
        pass
    return None, None


# === Step 1: Load FTSI page hierarchy ===
def load_ftsi_pages():
    """Load all pages with their hierarchy from FTSI databases."""
    print("Loading FTSI page hierarchy...")
    pages = []

    for db_file, nb_name in NOTEBOOKS:
        db_path = os.path.join(DB_DIR, db_file)
        if not os.path.exists(db_path):
            print(f"  WARNING: DB not found: {db_file}")
            continue

        conn = connect_ro(db_path)

        # Build section lookup
        sections = {}
        for row in conn.execute("SELECT GOID, Title FROM Entities WHERE Type = 2"):
            sections[row[0]] = row[1]

        # Get pages with their elements
        for row in conn.execute(
            "SELECT rowid, GOID, GUID, ParentGOID, Title, LastModifiedTime "
            "FROM Entities WHERE Type = 1"
        ):
            rowid, goid, guid, parent_goid, title, last_modified = row
            section_name = sections.get(parent_goid, "Unknown")

            # Get text elements
            text_elements = conn.execute(
                "SELECT Text, Jcid FROM PageElements "
                "WHERE EntityRowId = ? ORDER BY rowid",
                (rowid,)
            ).fetchall()

            texts = [t[0] for t in text_elements if t[1] == 393230 and t[0]]
            image_alts = [t[0] for t in text_elements if t[1] == 393233 and t[0]]
            file_names = [t[0] for t in text_elements if t[1] == 393269 and t[0]]
            image_count = sum(1 for t in text_elements if t[1] == 393233)
            file_count = sum(1 for t in text_elements if t[1] == 393269)

            pages.append({
                'notebook': nb_name,
                'section': section_name,
                'title': title or "Untitled",
                'goid': goid,
                'guid': guid,
                'texts': texts,
                'image_alts': image_alts,
                'file_names': file_names,
                'image_count': image_count,
                'file_count': file_count,
                'last_modified': last_modified,
            })

        conn.close()
        print(f"  {nb_name}: {sum(1 for p in pages if p['notebook'] == nb_name)} pages")

    print(f"  Total: {len(pages)} pages")
    return pages


# === Step 2: Classify and index all cache bin files ===
def index_cache_files():
    """Classify all cache bin files and build ordered index."""
    print("Indexing cache bin files...")
    files = sorted(f for f in os.listdir(CACHE_DIR) if f.endswith('.bin'))

    file_index = []
    for fname in files:
        filepath = os.path.join(CACHE_DIR, fname)
        fid = base36_to_int(fname.replace('.bin', ''))
        ftype, ext = classify_bin_file(filepath)
        size = os.path.getsize(filepath)

        is_page = False
        if ftype == 'DATA' and size >= 4096:
            with open(filepath, 'rb') as f:
                data = f.read(min(size, 65536))
            if PAGE_TITLE_MARKER in data:
                is_page = True

        file_index.append({
            'fid': fid,
            'fname': fname,
            'filepath': filepath,
            'type': ftype,
            'ext': ext,
            'size': size,
            'is_page': is_page,
        })

    file_index.sort(key=lambda x: x['fid'])

    page_count = sum(1 for f in file_index if f['is_page'])
    image_count = sum(1 for f in file_index if f['type'] == 'IMAGE')
    print(f"  Total files: {len(file_index)}")
    print(f"  Page files: {page_count}")
    print(f"  Image files: {image_count}")
    return file_index


# === Step 3: Match FTSI pages to cache bin files via GUID bytes ===
def match_pages_to_bins(pages, file_index):
    """Match FTSI pages to their cache bin files using GUID byte search."""
    print("Matching pages to bin files via GUID bytes...")

    # Build GUID lookup
    guid_to_page = {}
    for p in pages:
        try:
            gb = guid_to_bytes_le(p['guid'])
            guid_to_page[gb] = p
        except:
            pass

    # Search each page bin for matching GUIDs
    page_bins = [f for f in file_index if f['is_page']]

    matched = 0
    for pb in page_bins:
        with open(pb['filepath'], 'rb') as f:
            data = f.read()

        pb['matched_page'] = None
        for gb, page in guid_to_page.items():
            if gb in data:
                pb['matched_page'] = page
                page['bin_file'] = pb
                matched += 1
                break

    print(f"  Matched: {matched}/{len(page_bins)} page bins")

    # Count unmatched FTSI pages
    unmatched_ftsi = [p for p in pages if 'bin_file' not in p]
    print(f"  Unmatched FTSI pages: {len(unmatched_ftsi)}")
    return page_bins


# === Step 4: Build sequential image map ===
def build_image_map(file_index, page_bins):
    """Map images to pages using sequential allocation."""
    print("Building sequential image map...")

    page_fids = set(pb['fid'] for pb in page_bins if pb['matched_page'])

    # For each page bin, collect IMAGE files between it and the next DATA file (>=4KB)
    all_sorted = sorted(file_index, key=lambda x: x['fid'])
    fid_to_idx = {f['fid']: i for i, f in enumerate(all_sorted)}

    for pb in page_bins:
        if not pb['matched_page']:
            continue

        idx = fid_to_idx.get(pb['fid'])
        if idx is None:
            pb['images'] = []
            continue

        images = []
        for j in range(idx + 1, len(all_sorted)):
            nf = all_sorted[j]
            if nf['type'] == 'IMAGE':
                images.append(nf)
            elif nf['is_page'] or (nf['type'] == 'DATA' and nf['size'] >= 4096):
                break
        pb['images'] = images

    total_images = sum(len(pb.get('images', [])) for pb in page_bins)
    pages_with_images = sum(1 for pb in page_bins if pb.get('images'))
    print(f"  Total images mapped: {total_images}")
    print(f"  Pages with images: {pages_with_images}")


# === Step 5: Extract embedded PNGs from page binary ===
def extract_embedded_pngs(page_data):
    """Extract small PNG images embedded within the page binary."""
    PNG_SIG = b'\x89PNG\r\n\x1a\n'
    PNG_END = b'IEND\xaeB`\x82'

    pngs = []
    idx = 0
    while True:
        pos = page_data.find(PNG_SIG, idx)
        if pos < 0:
            break
        end_pos = page_data.find(PNG_END, pos)
        if end_pos < 0:
            break
        end_pos += 8
        png_data = page_data[pos:end_pos]
        if len(png_data) >= 24:
            w = struct.unpack('>I', png_data[16:20])[0]
            h = struct.unpack('>I', png_data[20:24])[0]
            pngs.append({'data': png_data, 'width': w, 'height': h})
        idx = end_pos

    return pngs


# === Step 6: Write output ===
def export_pages(pages, page_bins, file_index):
    """Export all matched pages to the output directory."""
    print(f"Exporting to {OUTPUT_DIR}...")

    # Track statistics
    stats = {
        'exported': 0,
        'skipped_no_bin': 0,
        'total_images': 0,
        'total_embedded_pngs': 0,
        'unlinked_images': 0,
        'notebooks': defaultdict(lambda: defaultdict(int)),
    }

    used_image_paths = set()

    # Build page_bins lookup by matched page goid
    bin_lookup = {}
    for pb in page_bins:
        if pb['matched_page']:
            goid = pb['matched_page']['goid']
            # If multiple bins match same page, use the one with the latest fid
            if goid not in bin_lookup or pb['fid'] > bin_lookup[goid]['fid']:
                bin_lookup[goid] = pb

    for page in pages:
        nb = sanitize_filename(page['notebook'])
        sec = sanitize_filename(page['section'])
        title = sanitize_filename(page['title'])

        # Handle duplicate titles within same section
        page_dir = os.path.join(OUTPUT_DIR, nb, sec)
        os.makedirs(page_dir, exist_ok=True)

        # Check if file already exists (duplicate title)
        md_path = os.path.join(page_dir, f"{title}.md")
        if os.path.exists(md_path):
            # Append GOID suffix
            goid_suffix = page['goid'].split('{')[-1].rstrip('}')
            title = f"{title}_{goid_suffix}"
            md_path = os.path.join(page_dir, f"{title}.md")

        pb = bin_lookup.get(page['goid'])
        if not pb:
            stats['skipped_no_bin'] += 1
            # Still write text content from FTSI
            _write_markdown(md_path, page, [], [], title)
            stats['exported'] += 1
            stats['notebooks'][nb][sec] += 1
            continue

        # Get images from sequential allocation
        images = pb.get('images', [])
        image_files = []

        if images:
            img_dir = os.path.join(page_dir, f"{title}_images")
            os.makedirs(img_dir, exist_ok=True)

            for idx, img in enumerate(images, 1):
                ext = img['ext'] or 'bin'
                img_fname = f"image_{idx:03d}.{ext}"
                dst = os.path.join(img_dir, img_fname)
                shutil.copy2(img['filepath'], dst)
                used_image_paths.add(img['filepath'])
                image_files.append(f"{title}_images/{img_fname}")
                stats['total_images'] += 1

        # Extract embedded PNGs from page binary (skip small icons < 100x100)
        embedded_pngs = []
        try:
            with open(pb['filepath'], 'rb') as f:
                page_data = f.read()
            all_embedded = extract_embedded_pngs(page_data)
            # Only include non-icon PNGs (larger than 100x100)
            large_embedded = [p for p in all_embedded if p['width'] > 100 or p['height'] > 100]
            if large_embedded:
                img_dir = os.path.join(page_dir, f"{title}_images")
                os.makedirs(img_dir, exist_ok=True)
                for idx, png in enumerate(large_embedded, len(images) + 1):
                    img_fname = f"embedded_{idx:03d}_{png['width']}x{png['height']}.png"
                    dst = os.path.join(img_dir, img_fname)
                    with open(dst, 'wb') as f:
                        f.write(png['data'])
                    embedded_pngs.append(f"{title}_images/{img_fname}")
                    stats['total_embedded_pngs'] += 1
        except:
            pass

        _write_markdown(md_path, page, image_files, embedded_pngs, title)
        stats['exported'] += 1
        stats['notebooks'][nb][sec] += 1

    # Images the cache could not link to any page. Current OneNote versions
    # bulk-download media after the pages, so sequential cache order no longer
    # identifies the owning page — preserve them in a recoverable pool instead
    # of dropping them.
    unlinked = [f for f in file_index
                if f['type'] == 'IMAGE' and f['filepath'] not in used_image_paths]
    if unlinked:
        pool_dir = os.path.join(OUTPUT_DIR, "_unlinked_images")
        os.makedirs(pool_dir, exist_ok=True)
        manifest = [
            "# Unlinked cache images",
            "",
            "Images found in the OneNote cache that could not be attributed",
            "to a page: this OneNote version downloads media in bulk after the",
            "pages, so cache file order no longer identifies the owner.",
            "",
            "| file | format | dimensions | bytes | cached at |",
            "|---|---|---|---|---|",
        ]
        for img in sorted(unlinked, key=lambda x: x['fid']):
            with open(img['filepath'], 'rb') as f:
                data = f.read()
            w, h = get_image_dimensions(img['ext'], data)
            fname = f"cache_{img['fid']}.{img['ext'] or 'bin'}"
            shutil.copy2(img['filepath'], os.path.join(pool_dir, fname))
            cached_at = time.strftime('%Y-%m-%d %H:%M',
                                      time.localtime(os.path.getmtime(img['filepath'])))
            dims = f"{w}x{h}" if w else "-"
            manifest.append(f"| {fname} | {img['ext'] or '?'} | {dims} | {img['size']:,} | {cached_at} |")
            stats['unlinked_images'] += 1
        with open(os.path.join(pool_dir, "manifest.md"), 'w', encoding='utf-8') as f:
            f.write("\n".join(manifest) + "\n")
        print(f"  Unlinked images: {stats['unlinked_images']} "
              f"(saved to _unlinked_images/, see manifest.md)")

    return stats


def _write_markdown(md_path, page, image_files, embedded_pngs, title):
    """Write a single page's markdown file."""
    lines = []
    lines.append(f"# {page['title']}")
    lines.append("")
    lines.append(f"> **Notebook:** {page['notebook']} / **Section:** {page['section']}")
    if page.get('last_modified'):
        lines.append(f"> **Last modified:** {page['last_modified']}")
    lines.append("")

    # Text content
    if page['texts']:
        for text in page['texts']:
            if text and text.strip():
                lines.append(text.strip())
        lines.append("")

    # Images
    all_images = image_files + embedded_pngs
    if all_images:
        lines.append("---")
        lines.append("")
        lines.append("## Images")
        lines.append("")
        for img_path in all_images:
            lines.append(f"![image]({img_path})")
            lines.append("")

    # File attachments
    if page['file_names']:
        lines.append("## Attachments")
        lines.append("")
        for fname in page['file_names']:
            lines.append(f"- {fname}")
        lines.append("")

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# === Step 7: Generate index ===
def generate_index(pages, stats):
    """Generate index.md with directory tree."""
    print("Generating index.md...")

    lines = []
    lines.append("# OneNote Export Index")
    lines.append("")
    lines.append(f"Exported {stats['exported']} pages, "
                 f"{stats['total_images']} sequential images, "
                 f"{stats['total_embedded_pngs']} embedded images")
    if stats.get('unlinked_images'):
        lines.append(f"({stats['unlinked_images']} cache images could not be linked to a "
                     f"page — saved in [_unlinked_images/](_unlinked_images/), see its manifest.md)")
    if stats['skipped_no_bin']:
        lines.append(f"({stats['skipped_no_bin']} pages had no cache bin file - text only)")
    lines.append("")

    # Build tree
    tree = defaultdict(lambda: defaultdict(list))
    for p in pages:
        tree[p['notebook']][p['section']].append(p['title'])

    for nb in sorted(tree.keys()):
        nb_safe = sanitize_filename(nb)
        lines.append(f"## {nb}")
        lines.append("")
        for sec in sorted(tree[nb].keys()):
            sec_safe = sanitize_filename(sec)
            lines.append(f"### {sec} ({len(tree[nb][sec])} pages)")
            lines.append("")
            for title in sorted(tree[nb][sec]):
                title_safe = sanitize_filename(title)
                lines.append(f"- [{title}]({nb_safe}/{sec_safe}/{title_safe}.md)")
            lines.append("")

    index_path = os.path.join(OUTPUT_DIR, "index.md")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"  Written: {index_path}")


# === Main ===
def main():
    print("=" * 60)
    print("OneNote Local Cache Extractor")
    print("=" * 60)
    print()

    # Step 1
    pages = load_ftsi_pages()
    print()

    # Step 2
    file_index = index_cache_files()
    print()

    # Step 3
    page_bins = match_pages_to_bins(pages, file_index)
    print()

    # Step 4
    build_image_map(file_index, page_bins)
    print()

    # Step 5-6
    stats = export_pages(pages, page_bins, file_index)
    print()

    # Step 7
    generate_index(pages, stats)
    print()

    # Summary
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"  Pages exported:     {stats['exported']}")
    print(f"  Sequential images:  {stats['total_images']}")
    print(f"  Embedded images:    {stats['total_embedded_pngs']}")
    print(f"  Unlinked images:    {stats['unlinked_images']} (_unlinked_images/)")
    print(f"  No cache bin file:  {stats['skipped_no_bin']} (text only)")
    print(f"  Output directory:   {OUTPUT_DIR}")
    print()

    for nb in sorted(stats['notebooks'].keys()):
        total = sum(stats['notebooks'][nb].values())
        print(f"  {nb}: {total} pages across {len(stats['notebooks'][nb])} sections")


if __name__ == '__main__':
    main()
