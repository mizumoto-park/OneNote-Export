# Cache .bin File Format

## Overview

OneNote's cache directory contains binary caches of all note pages and media. Files use base-36 sequential naming (`00000000.bin` ~ `0000069L.bin`), totaling 2,039 files and 740 MB.

## File Classification

Files can be classified into two categories using magic bytes (file header signatures):

### IMAGE Type (1,313 files)

| Format | Magic Bytes | Count | Description |
|--------|-------------|-------|-------------|
| PNG | `89 50 4E 47` | 1,041 | Screenshots, charts, photos |
| JPEG | `FF D8 FF` | 214 | Photos, scanned documents |
| GIF | `47 49 46 38` | 32 | Animated GIFs |
| PDF | `25 50 44 46` | 16 | Embedded PDF documents |
| ZIP | `50 4B 03 04` | 10 | Compressed file attachments |

These files can be opened directly after changing the file extension. Content is complete.

### DATA Type (726 files)

Files that don't start with known magic bytes belong to OneNote's proprietary format:

| Subtype | Identification | Count | Description |
|---------|---------------|-------|-------------|
| Page Data | Contains `PageTitle` UTF-16LE marker | 592 | Complete content of note pages |
| Section Store | Large (>1MB) | Few | Section-level revision store |
| Index/Allocation | First 3 special files | 3 | Allocation table, object directory |
| Other Data | Small files between pages | ~131 | Revision metadata, etc. |

---

## Special Files Detail

### header (72 bytes)

Cache metadata file, not in .bin format. Contains version number and counters.

### 00000000.bin — Allocation Table

- Size: ~380 KB
- Tracks used file IDs
- Contains references to some image file IDs
- 359 image file IDs found in our analysis

### 00000001.bin — Object Directory

- Size: ~380 KB
- **GUID → file ID mapping table**
- Stores GUIDs in mixed-endian byte format
- 342 image file IDs found in our analysis
- Some mappings are stale (doesn't include all existing images)

### 00000002.bin — Section-level Revision Store

- Size: ~1.9 MB
- Contains **all page titles and GUIDs** (UTF-16LE encoded)
- Similar to a OneNote Table of Contents
- Can be used to verify completeness of the page list

---

## Page Data File Structure

Page Data uses a simplified version of the MS-ONESTORE format. Key characteristics:

### Identification

- File size >= 4,096 bytes
- Contains the UTF-16LE encoded string `PageTitle`

### Content Structure

```
┌─────────────────────────────────────┐
│  Header / Revision metadata          │  Fixed structure, contains version info
├─────────────────────────────────────┤
│  GUID / GOID reference area         │  GUIDs of the page and associated objects
│  ├── Page GUID (mixed-endian)        │
│  ├── Section GUID                    │
│  └── Image/attachment GOIDs          │
├─────────────────────────────────────┤
│  Text content (UTF-16LE)             │
│  ├── "PageTitle"                     │  Marker
│  ├── Page title                      │
│  ├── "Calibri" / "Calibri Light"     │  Font names
│  ├── "PageDateTime"                  │  Marker
│  ├── Content paragraphs              │
│  └── Table data                      │
├─────────────────────────────────────┤
│  Embedded small PNGs (optional)      │
│  ├── 40x40 icons                     │  UI-related small images
│  └── 80x80 icons                     │
├─────────────────────────────────────┤
│  CID references (optional)           │
│  ├── "cidimage008.png@01D4835C..."   │  Content-ID format image refs
│  └── "Untitled picture.png"          │  Internal image filename
├─────────────────────────────────────┤
│  Original file paths (optional)      │
│  └── "C:\Users\morton_rainey\..."    │  Clipboard source path
└─────────────────────────────────────┘
```

### Size Distribution

| Size Range | Count | Percentage |
|------------|-------|------------|
| 4 - 16 KB | 221 | 37% |
| 16 - 64 KB | 218 | 37% |
| 64 - 256 KB | 256 | 24% |
| > 256 KB | 23 | 2% |

### Embedded PNGs

Some page files contain small embedded PNG icons (typically 40x40 or 80x80 pixels), which can be extracted by searching for the PNG signature (`89 50 4E 47 0D 0A 1A 0A`) and IEND marker (`49 45 4E 44 AE 42 60 82`).

**Note**: Large images are not embedded in page files — they are stored as separate .bin files.

---

## IMAGE Files

Image files are standard image formats stored with a .bin extension.

### Common PNG Dimensions

Observed from the actual cache:

```
40x40     ← Small icons (embedded in page data)
80x80     ← Small icons (embedded in page data)
449x320   ← Thumbnails
681x340   ← Medium charts
730x329   ← Medium charts
1024x543  ← Screenshots
1917x1016 ← Full-screen screenshots
1920x1022 ← Full-screen screenshots
```

### Verification

```python
import struct

with open('somefile.bin', 'rb') as f:
    header = f.read(24)

if header[:8] == b'\x89PNG\r\n\x1a\n':
    width = struct.unpack('>I', header[16:20])[0]
    height = struct.unpack('>I', header[20:24])[0]
    print(f"PNG: {width}x{height}")
elif header[:3] == b'\xff\xd8\xff':
    print("JPEG")
elif header[:4] == b'GIF8':
    print("GIF")
```
