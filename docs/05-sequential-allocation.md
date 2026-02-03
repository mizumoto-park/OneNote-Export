# Sequential Allocation Model — Image Attribution

## Problem

After establishing the "page → page .bin" mapping, the next question is: "Which .bin files contain this page's images?"

OneNote has no explicit index table recording "page X's images are files A, B, C." We need to infer this from the cache allocation pattern.

## Discovery: Sequential Allocation

By analyzing the ordering of 2,039 .bin files, we discovered a key pattern:

**When writing to cache, OneNote allocates a page and all its images to consecutive, adjacent file IDs.**

```
File ID order:
  ┌─────────────┐
  │ Page A data  │  000004LC.bin (DATA, 168KB)
  ├─────────────┤
  │ (gap)        │  000004LD.bin, 000004LE.bin don't exist or are small data
  ├─────────────┤
  │ Image 1      │  000004LF.bin (PNG, 730x329, 14KB)
  ├─────────────┤
  │ Image 2      │  000004LG.bin (PNG, 681x340, 14KB)
  ├─────────────┤
  │ Page B data  │  000004LH.bin (DATA, 20KB) ← Start of next page
  ├─────────────┤
  │ ...          │
  └─────────────┘
```

**Rule**: Scan forward from a page data file — all IMAGE-type files (PNG/JPEG/GIF/PDF/ZIP) belong to that page, until the next DATA file (>=4KB) is encountered.

## Verification

### Case 1: Historical CPB (2 charts)

```
000004LC.bin  →  Page Data (168 KB) — "Historical CPB"
000004LF.bin  →  PNG 730x329 — NTD per share stock price chart ✓
000004LG.bin  →  PNG 681x340 — Bonus percentage bar chart ✓
000004LH.bin  →  Page Data (20 KB) — "Black Duck Integration" (next page)
```

FTSI recorded 1 image (Jcid=393233, with alt-text), but there are actually 2. FTSI only indexes images that have alt-text.

### Case 2: High Image Count Pages

```
Training/7rendMicro-ACE-202:   195 images (slide screenshots)
Training/When_parquet_meet_spark_sql: 120 images
Training/7rendMicro-ACE-203:   82 images
Training/7rendMicro-ACE-201:   80 images
```

These are training course pages where each slide is embedded as a screenshot. The image counts are reasonable.

## Statistics

### Images Per Page Distribution

| Image Count | Pages | Description |
|-------------|-------|-------------|
| 0 | 430 | Text-only pages |
| 1-2 | 81 | Pages with few images |
| 3-7 | 50 | Moderate image count |
| 8-19 | 16 | Higher image count |
| 20+ | 6 | Slide/screenshot-heavy pages |
| **Total** | **583** | |

### Summary

| Item | Count |
|------|-------|
| Sequentially mapped images | 1,246 |
| Large PNGs embedded in page data | 15 |
| Pages with images | 160 |
| FTSI-indexed image elements | 879 |

Sequential mapping (1,246) > FTSI index (879) because:
1. FTSI only indexes images with alt-text/OCR text
2. Cache may retain images from deleted pages
3. Thumbnails/previews are also counted

## Algorithm

```python
def build_image_map(file_index, page_bins):
    """Build the list of images belonging to each page"""

    # Sort all files by file ID
    all_sorted = sorted(file_index, key=lambda x: x['fid'])

    for page_bin in page_bins:
        if not page_bin['matched_page']:
            continue

        # Scan forward from this page's file ID
        idx = find_index(all_sorted, page_bin['fid'])

        images = []
        for j in range(idx + 1, len(all_sorted)):
            next_file = all_sorted[j]

            if next_file['type'] == 'IMAGE':
                # Image → belongs to this page
                images.append(next_file)
            elif next_file['is_page'] or (next_file['type'] == 'DATA' and next_file['size'] >= 4096):
                # Encountered next page or large data → stop
                break

        page_bin['images'] = images
```

## Additional Embedded PNG Extraction

Some pages have small PNGs directly embedded in the page data (usually UI icons). We additionally extract embedded PNGs larger than 100x100:

```python
def extract_embedded_pngs(page_data):
    """Extract embedded PNGs from page binary data"""
    PNG_SIG = b'\x89PNG\r\n\x1a\n'
    PNG_END = b'IEND\xaeB\x60\x82'

    pngs = []
    idx = 0
    while True:
        pos = page_data.find(PNG_SIG, idx)
        if pos < 0:
            break
        end = page_data.find(PNG_END, pos)
        if end < 0:
            break
        end += 8  # Include IEND chunk
        png_data = page_data[pos:end]
        # Read PNG dimensions (IHDR chunk)
        width = struct.unpack('>I', png_data[16:20])[0]
        height = struct.unpack('>I', png_data[20:24])[0]
        pngs.append({'data': png_data, 'width': width, 'height': height})
        idx = end

    # Keep only large images (exclude UI icons)
    return [p for p in pngs if p['width'] > 100 or p['height'] > 100]
```

## Limitations and Known Issues

1. **Small DATA files in gaps**: Occasionally small (<4KB) data files (revision metadata) appear between pages and images — our algorithm skips them
2. **Residual images from deleted pages**: May be incorrectly attributed to adjacent pages
3. **Shared images**: In rare cases, multiple pages reference the same image, but only one copy exists in cache
4. **Revision history**: The same page may have multiple cache copies, each with different versions of images
