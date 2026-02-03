#!/usr/bin/env python3
"""
Extract embedded images from OneNote .bin cache files.

Scans each .bin file for known magic bytes (PNG, JPEG, GIF, PDF, BMP)
and extracts them to _attachments/ directory.
"""

import os
import struct
import sys

CACHE_DIR = os.path.expanduser(
    "~/Library/Containers/com.microsoft.onenote.mac/Data/Library/"
    "Application Support/Microsoft User Data/OneNote/15.0-restore/cache"
)

OUTPUT_DIR = os.path.expanduser("~/Desktop/OneNote-Export/_attachments")

# Magic bytes for image formats
SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': ('png', 'PNG'),
    b'\xff\xd8\xff': ('jpg', 'JPEG'),
    b'GIF87a': ('gif', 'GIF87a'),
    b'GIF89a': ('gif', 'GIF89a'),
    b'%PDF-': ('pdf', 'PDF'),
    b'BM': ('bmp', 'BMP'),
}

# Maximum signature length to check
MAX_SIG_LEN = max(len(s) for s in SIGNATURES)


def find_images_in_data(data):
    """Find all image offsets in binary data."""
    results = []
    i = 0
    while i < len(data) - MAX_SIG_LEN:
        for sig, (ext, fmt) in SIGNATURES.items():
            if data[i:i+len(sig)] == sig:
                # Find the end of this image
                end = find_image_end(data, i, ext)
                if end > i + 16:  # minimum reasonable size
                    results.append((i, end, ext, fmt))
                    i = end  # skip past this image
                    break
        else:
            i += 1
    return results


def find_image_end(data, start, ext):
    """Find the end of an image starting at 'start'."""
    if ext == 'png':
        # PNG ends with IEND chunk: 00 00 00 00 49 45 4E 44 AE 42 60 82
        iend = data.find(b'IEND\xae\x42\x60\x82', start)
        if iend != -1:
            return iend + 8
        # Fallback: search for next magic or EOF
        return min(start + 10_000_000, len(data))

    elif ext == 'jpg':
        # JPEG ends with FFD9
        pos = start + 2
        while pos < len(data) - 1:
            ffd9 = data.find(b'\xff\xd9', pos)
            if ffd9 == -1:
                return len(data)
            return ffd9 + 2
        return len(data)

    elif ext == 'gif':
        # GIF ends with 0x3B (trailer)
        pos = start + 6
        trailer = data.find(b'\x3b', pos)
        if trailer != -1:
            return trailer + 1
        return min(start + 5_000_000, len(data))

    elif ext == 'pdf':
        # PDF ends with %%EOF
        eof = data.find(b'%%EOF', start)
        if eof != -1:
            return eof + 5
        return min(start + 50_000_000, len(data))

    elif ext == 'bmp':
        # BMP: file size is at offset 2 (4 bytes, little-endian)
        if start + 6 <= len(data):
            size = struct.unpack_from('<I', data, start + 2)[0]
            if 16 < size < 50_000_000:
                return start + size
        return min(start + 10_000_000, len(data))

    return len(data)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    bin_files = sorted([
        f for f in os.listdir(CACHE_DIR) if f.endswith('.bin')
    ])
    print(f"Found {len(bin_files)} .bin files in cache")
    print(f"Output: {OUTPUT_DIR}")

    counters = {'png': 0, 'jpg': 0, 'gif': 0, 'pdf': 0, 'bmp': 0}
    total_extracted = 0
    total_bytes = 0
    files_with_images = 0

    for idx, bin_name in enumerate(bin_files):
        bin_path = os.path.join(CACHE_DIR, bin_name)
        try:
            with open(bin_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            print(f"  Error reading {bin_name}: {e}")
            continue

        images = find_images_in_data(data)
        if not images:
            continue

        files_with_images += 1
        for offset, end, ext, fmt in images:
            counters[ext] += 1
            num = counters[ext]
            out_name = f"img_{num:05d}.{ext}"
            out_path = os.path.join(OUTPUT_DIR, out_name)

            img_data = data[offset:end]
            with open(out_path, 'wb') as f:
                f.write(img_data)

            total_extracted += 1
            total_bytes += len(img_data)

        if (idx + 1) % 200 == 0:
            print(f"  Processed {idx+1}/{len(bin_files)} files, "
                  f"extracted {total_extracted} images so far...")

    print(f"\n{'='*50}")
    print(f"Processed {len(bin_files)} .bin files")
    print(f"Files containing images: {files_with_images}")
    print(f"Total images extracted: {total_extracted}")
    print(f"Total size: {total_bytes / (1024*1024):.1f} MB")
    print(f"Breakdown:")
    for ext, count in sorted(counters.items()):
        if count > 0:
            print(f"  {ext.upper()}: {count}")
    print(f"Output: {OUTPUT_DIR}")

    # Generate _attachments/index.md
    index_path = os.path.join(OUTPUT_DIR, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# Extracted Attachments\n\n")
        f.write(f"Total: {total_extracted} files ({total_bytes / (1024*1024):.1f} MB)\n\n")
        for ext, count in sorted(counters.items()):
            if count > 0:
                f.write(f"- **{ext.upper()}**: {count} files\n")
        f.write("\n## Files\n\n")
        for fn in sorted(os.listdir(OUTPUT_DIR)):
            if fn != "index.md":
                f.write(f"- [{fn}]({fn})\n")
    print(f"Index written: {index_path}")


if __name__ == "__main__":
    main()
