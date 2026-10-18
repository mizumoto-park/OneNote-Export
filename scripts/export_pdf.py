#!/usr/bin/env python3
"""
OneNote Exported Markdown → PDF Converter (Plan B: Flow Layout)

Reads the already-exported Markdown + images from exported_md/ and converts
each page to a styled PDF using HTML as an intermediate format.

Text order is the order stored in the FTSI database (by the markdown export).
Images are inserted between text blocks at evenly spaced positions.

Dependencies: weasyprint (install via: uv add weasyprint)
Run: DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python scripts/export_pdf.py
"""

import os
import re
from pathlib import Path
from html import escape

# Lazy import weasyprint (needs DYLD_FALLBACK_LIBRARY_PATH on macOS)
weasyprint = None

# === Configuration ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXPORTED_DIR = os.path.join(PROJECT_DIR, "exported_md")

# CSS for PDF rendering
PAGE_CSS = """
@page {
    size: A4;
    margin: 2cm 1.8cm;
}

body {
    font-family: "Noto Sans CJK TC", "Heiti TC", "Arial Unicode MS",
                 "Helvetica Neue", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
}

h1.page-title {
    font-size: 20pt;
    font-weight: 600;
    color: #2b2b5e;
    border-bottom: 2px solid #5b5fc7;
    padding-bottom: 6pt;
    margin-bottom: 12pt;
}

.breadcrumb {
    font-size: 9pt;
    color: #666;
    margin-bottom: 16pt;
}

.text-block {
    margin-bottom: 4pt;
}

.text-block.heading {
    font-size: 14pt;
    font-weight: 600;
    margin-top: 14pt;
    margin-bottom: 6pt;
    color: #2b2b5e;
}

.image-block {
    margin: 12pt 0;
    text-align: center;
}

.image-block img {
    max-width: 100%;
    max-height: 500pt;
    border: 1px solid #ddd;
    border-radius: 4pt;
}

.image-caption {
    font-size: 8pt;
    color: #888;
    margin-top: 4pt;
    text-align: center;
}

table {
    border-collapse: collapse;
    margin: 10pt 0;
    width: 100%;
}

table td, table th {
    border: 1px solid #ccc;
    padding: 4pt 8pt;
    font-size: 10pt;
}

table th {
    background-color: #f0f0f5;
    font-weight: 600;
}

.attachment {
    font-size: 9pt;
    color: #555;
    padding: 4pt 8pt;
    background: #f8f8f8;
    border-left: 3px solid #5b5fc7;
    margin: 4pt 0;
}

.footer-meta {
    margin-top: 24pt;
    padding-top: 8pt;
    border-top: 1px solid #ddd;
    font-size: 8pt;
    color: #999;
}
"""


def texts_to_html_blocks(texts, title):
    """
    Convert ordered text segments into HTML blocks.
    Detects: title (skip duplicate), headings (short bold-like), paragraphs.
    """
    blocks = []
    seen_title = False

    for text in texts:
        if not text or not text.strip():
            continue
        t = text.strip()

        # Skip if it's the page title repeated
        if not seen_title and t == title:
            seen_title = True
            continue

        # Heuristic: short lines that look like headings
        if len(t) < 60 and not any(c.isdigit() for c in t[:5]) and len(t) > 2:
            # Could be a heading if it's standalone and not a data value
            is_number = False
            try:
                float(t.replace(',', '').replace(' ', ''))
                is_number = True
            except:
                pass

            if not is_number and len(blocks) > 0:
                # Check if previous block was also very short (table-like data)
                pass

        blocks.append(f'<div class="text-block">{escape(t)}</div>')

    return blocks


def build_page_html(title, notebook, section, texts, image_paths, file_names):
    """Build complete HTML for a single page."""
    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<style>{PAGE_CSS}</style>
</head>
<body>
""")

    # Breadcrumb
    html_parts.append(f'<div class="breadcrumb">{escape(notebook)} / {escape(section)}</div>')

    # Title
    html_parts.append(f'<h1 class="page-title">{escape(title)}</h1>')

    # Interleave text and images
    # Strategy: distribute images evenly among text blocks
    text_blocks = texts_to_html_blocks(texts, title)
    n_texts = len(text_blocks)
    n_images = len(image_paths)

    if n_images == 0:
        # Just text
        html_parts.extend(text_blocks)
    elif n_texts == 0:
        # Just images
        for img_path in image_paths:
            html_parts.append(f'''<div class="image-block">
<img src="{escape(img_path)}">
</div>''')
    else:
        # Interleave: place images at evenly spaced positions within text
        if n_images >= n_texts:
            # More images than text: put one image per text block
            for i, block in enumerate(text_blocks):
                html_parts.append(block)
                if i < n_images:
                    html_parts.append(f'''<div class="image-block">
<img src="{escape(image_paths[i])}">
</div>''')
            # Remaining images at the end
            for j in range(n_texts, n_images):
                html_parts.append(f'''<div class="image-block">
<img src="{escape(image_paths[j])}">
</div>''')
        else:
            # More text than images: space images evenly
            step = n_texts / (n_images + 1)
            image_positions = set()
            for k in range(n_images):
                pos = int(step * (k + 1))
                image_positions.add(min(pos, n_texts - 1))

            img_idx = 0
            for i, block in enumerate(text_blocks):
                html_parts.append(block)
                if i in image_positions and img_idx < n_images:
                    html_parts.append(f'''<div class="image-block">
<img src="{escape(image_paths[img_idx])}">
</div>''')
                    img_idx += 1

    # Attachments
    if file_names:
        html_parts.append('<div style="margin-top: 16pt;">')
        for fname in file_names:
            html_parts.append(f'<div class="attachment">📎 {escape(fname)}</div>')
        html_parts.append('</div>')

    html_parts.append('</body></html>')
    return '\n'.join(html_parts)


def parse_exported_md(md_path):
    """Parse an exported .md file to extract metadata and content."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    title = "Untitled"
    notebook = ""
    section = ""
    texts = []
    image_files = []
    file_names = []

    in_images = False
    in_attachments = False
    in_ocr = False

    for line in lines:
        # Title
        if line.startswith('# ') and title == "Untitled":
            title = line[2:].strip()
            continue

        # Breadcrumb
        m = re.match(r'> \*\*Notebook:\*\* (.+?) / \*\*Section:\*\* (.+)', line)
        if m:
            notebook = m.group(1)
            section = m.group(2)
            continue

        if line.startswith('> **Last modified:**'):
            continue

        # Section headers
        if line == '## Images':
            in_images = True
            in_attachments = False
            in_ocr = False
            continue
        if line == '## Image Descriptions (OCR/Alt-text)':
            in_images = False
            in_attachments = False
            in_ocr = True
            continue
        if line == '## Attachments':
            in_attachments = True
            in_images = False
            in_ocr = False
            continue
        if line == '---':
            continue

        # Skip OCR/alt-text section entirely
        if in_ocr:
            continue

        # Image references
        img_match = re.match(r'!\[image\]\((.+)\)', line)
        if img_match:
            image_files.append(img_match.group(1))
            continue

        # Attachments
        if in_attachments and line.startswith('- '):
            file_names.append(line[2:].strip())
            continue

        # Regular text
        if not in_images and line.strip():
            texts.append(line.strip())

    return {
        'title': title,
        'notebook': notebook,
        'section': section,
        'texts': texts,
        'image_files': image_files,
        'file_names': file_names,
    }


def convert_page_to_pdf(md_path):
    """Convert a single exported page (.md + images) to PDF."""
    global weasyprint
    if weasyprint is None:
        import weasyprint as wp
        weasyprint = wp

    page = parse_exported_md(md_path)
    md_dir = os.path.dirname(md_path)

    # Use FTSI text directly (already clean UTF-8 from SQLite).
    # The bin parser produces too much garbage from metadata bytes.
    # Future improvement: use bin order to reorder FTSI texts.

    # Resolve image paths to absolute
    abs_image_paths = []
    for img_rel in page['image_files']:
        abs_path = os.path.join(md_dir, img_rel)
        if os.path.exists(abs_path):
            abs_image_paths.append(Path(abs_path).as_uri())
        else:
            abs_image_paths.append(img_rel)

    html = build_page_html(
        page['title'], page['notebook'], page['section'],
        page['texts'], abs_image_paths, page['file_names']
    )

    # Output PDF path: same location as .md
    pdf_path = md_path.replace('.md', '.pdf')

    doc = weasyprint.HTML(string=html)
    doc.write_pdf(pdf_path)

    return pdf_path


def find_all_md_files():
    """Find all exported .md files."""
    md_files = []
    for root, dirs, files in os.walk(EXPORTED_DIR):
        # Skip _images directories
        dirs[:] = [d for d in dirs if not d.endswith('_images')]
        for f in files:
            if f.endswith('.md') and f != 'index.md':
                md_files.append(os.path.join(root, f))
    return sorted(md_files)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Convert exported OneNote pages to PDF')
    parser.add_argument('--test', type=int, default=0,
                        help='Only convert first N pages (for testing)')
    parser.add_argument('--page', type=str, default=None,
                        help='Convert a specific page by title substring')
    args = parser.parse_args()

    print("=" * 60)
    print("OneNote Markdown → PDF Converter")
    print("=" * 60)
    print()

    # Find all md files
    md_files = find_all_md_files()
    print(f"Found {len(md_files)} markdown files")

    # Filter if --page specified
    if args.page:
        md_files = [f for f in md_files if args.page.lower() in f.lower()]
        print(f"Filtered to {len(md_files)} files matching '{args.page}'")

    # Limit if --test
    if args.test > 0:
        md_files = md_files[:args.test]
        print(f"Test mode: processing first {len(md_files)} files")

    print()

    success = 0
    failed = 0
    for i, md_path in enumerate(md_files, 1):
        rel_path = os.path.relpath(md_path, EXPORTED_DIR)
        try:
            pdf_path = convert_page_to_pdf(md_path)
            success += 1
            if i <= 5 or i % 50 == 0:
                pdf_size = os.path.getsize(pdf_path)
                print(f"  [{i}/{len(md_files)}] OK: {rel_path} ({pdf_size:,} bytes)")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(md_files)}] FAIL: {rel_path}: {e}")

    print()
    print("=" * 60)
    print(f"Done: {success} succeeded, {failed} failed out of {len(md_files)} pages")
    print("=" * 60)


if __name__ == '__main__':
    main()
