# GUID Byte Matching Mechanism

## Problem

The FTSI database records metadata for each page (title, text, GOID) but does not directly record "which .bin file in the cache directory corresponds to this page." We need a method to establish this mapping.

## Solution: GUID Byte Search

Each FTSI page has a unique GUID (e.g., `{1BDE8095-99F1-44A0-8B67-0438D3A02923}`). This GUID is embedded in the corresponding page .bin file in **mixed-endian byte format**.

### Mixed-Endian GUID Format

The binary representation of a GUID uses Windows' mixed-endian format:

```
GUID string:  {1BDE8095-99F1-44A0-8B67-0438D3A02923}

Groups:
  Data1: 1BDE8095  (4 bytes, little-endian)  →  95 80 DE 1B
  Data2: 99F1      (2 bytes, little-endian)  →  F1 99
  Data3: 44A0      (2 bytes, little-endian)  →  A0 44
  Data4: 8B67      (2 bytes, big-endian)     →  8B 67
  Data5: 0438D3A02923 (6 bytes, big-endian)  →  04 38 D3 A0 29 23

Final bytes: 95 80 DE 1B F1 99 A0 44 8B 67 04 38 D3 A0 29 23
```

### Python Implementation

```python
import uuid

def guid_to_bytes_le(guid_str):
    """Convert GUID string to mixed-endian bytes"""
    g = guid_str.strip('{}')
    return uuid.UUID(g).bytes_le

# Example
guid = "{1BDE8095-99F1-44A0-8B67-0438D3A02923}"
guid_bytes = guid_to_bytes_le(guid)
# → b'\x95\x80\xde\x1b\xf1\x99\xa0\x44\x8b\x67\x04\x38\xd3\xa0\x29\x23'
```

### Matching Process

```
For each cache .bin file (identified as Page Data):
    Read entire file content
    For each FTSI page's GUID:
        Convert GUID to 16-byte mixed-endian format
        Search for these 16 bytes in the file
        If found → this .bin is the cache file for this page
```

### Matching Results

| Item | Count |
|------|-------|
| Total FTSI pages | 587 |
| Total page .bin files | 592 |
| Successfully matched | 558 |
| **Match rate** | **94.9%** |
| Unmatched FTSI pages | 29 |
| Unmatched .bin files | 34 |

### Reasons for Unmatched Items

**29 unmatched FTSI pages**:
- Pages purged from cache (too old or manually cleaned)
- Pages never fully synced to local storage

**34 unmatched .bin files**:
- Residual cache from deleted pages
- New pages not yet indexed by FTSI
- Older versions of page cache (OneNote retains revision history)

### Multiple Match Handling

A few pages (4) matched multiple .bin files because:
- OneNote retains multiple revision versions of pages
- The same page may have both old and new cache copies

Strategy: **use the one with the highest file ID** (i.e., the newest version).

---

## Alternative Approaches Compared

We tried multiple matching methods:

| Method | Match Rate | Notes |
|--------|-----------|-------|
| **GUID byte search** | **94.9%** | Best approach |
| Title text matching | 65% | Incomplete CJK title recognition, can't distinguish duplicate titles |
| GOID byte search | +0% | GUID portion of GOID belongs to notebook/section, not the page |
| ContentRID matching | Not tested | RID may change with revisions |
| MD5/SHA hash comparison | 0% | Binary format differs from plain text, no direct comparison possible |

---

## GUID Location in .bin Files

Using the "Historical CPB" page as an example:

```
Page .bin: 000004LC.bin (167,936 bytes)
Page GUID: {1BDE8095-99F1-44A0-8B67-0438D3A02923}

GUID bytes found at offset 0x0EE0:
  ...64d1329e85b88a567a9dd87de6e3b900
  [9580de1bf199a0448b670438d3a02923]    ← Page GUID (16 bytes)
  74237b021c8e7a00...
```

The GUID typically appears in the metadata area of the first half of the file (offset < 0x2000), surrounded by other GUIDs (section GUID, notebook GUID, associated object GUIDs).

---

## Image GOIDs in Page Data

Page .bin files also contain the GOIDs of their associated images. For example:

```
Image GOID: {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{87}
  ↓ GUID portion converted to mixed-endian
Found at offset 0x0EE0 in 000004LC.bin

Also found nearby (internal filenames):
  "Untitled picture.png"  (UTF-16LE)
  "chart2991374945314014811.png"  (UTF-16LE)
```

However, **image GOIDs do not directly contain the image's file ID**, so we need another mechanism to locate image files — this is the sequential allocation model.
