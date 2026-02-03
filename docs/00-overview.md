# OneNote macOS Local Cache Structure Overview

## Background

OneNote for Mac caches all notebook data locally within a sandboxed container. Even if the cloud account is signed out or sync is interrupted, the local cache retains complete note content, images, and attachments. This document describes how to recover complete notes from this cache.

## Cache Root Directory

```
~/Library/Containers/com.microsoft.onenote.mac/
└── Data/Library/Application Support/Microsoft User Data/OneNote/
    ├── 15.0/                    ← Currently active data
    ├── 15.0-ori/                ← Original backup (4 items)
    └── 15.0-restore/            ← Restore backup (9 items)
```

## 15.0/ Main Subdirectories

```
15.0/
├── cache/                       ← Core: binary cache for all note pages + images
│   ├── header                   ← 72 bytes, cache metadata
│   ├── 00000000.bin             ← Allocation Table
│   ├── 00000001.bin             ← Object Directory
│   ├── 00000002.bin ~ ...       ← Note pages + images, 2,039 .bin files total
│   └── (total: 740 MB)
│
├── FullTextSearchIndex/         ← Full-text search index SQLite databases
│   ├── {GUID}{N}.db             ← One DB per notebook, 5 total
│   └── MasterIndex/Master.db    ← Index version tracking (may not exist)
│
├── AccessibilityCheckerIndex/   ← Accessibility checker index
│   └── {GUID}{N}.db             ← One DB per notebook, 5 total
│
├── ServerListings/              ← Server connection cache (.onesrvcache)
├── Preferences.dat              ← Tag definitions (To Do, Important, etc.)
└── (other: telemetry, UI state)
```

## Data Relationship Overview

```
┌──────────────────────────┐
│   FTSI SQLite Databases   │  ← Structured data: hierarchy, text, search index
│   (FullTextSearchIndex)   │
│                          │
│  Entities table ────────┐│
│  (Notebook/Section/Page)││
│          │              ││
│          ▼              ││
│  PageElements table     ││
│  (text/image alt/files) ││
└──────────┬───────────────┘
           │ GUID byte matching
           ▼
┌──────────────────────────┐
│   Cache .bin Files        │  ← Binary data: page content, embedded images, attachments
│                          │
│  Page Data (.bin)        │
│  ├── UTF-16LE text       │
│  ├── GUID/GOID refs      │
│  └── Small embedded PNGs │
│                          │
│  Image Files (.bin)      │
│  ├── PNG / JPEG / GIF    │  ← Immediately after Page Data (sequential allocation)
│  └── PDF / ZIP attachments│
└──────────────────────────┘
```

## Five Notebooks Overview

| Notebook | Pages | Sections | FTSI DB Size | Images (FTSI) | Attachments |
|----------|-------|----------|-------------|---------------|-------------|
| Work | 413 | 22 | 7,984 KB | 424 | 27 |
| Personal | 160 | 30 | 3,100 KB | 431 | 8 |
| Evernote | 5 | 1 | 216 KB | — | — |
| Morton Rainey's Notebook | 8 | 2 | 352 KB | — | — |
| 7rendMicro | 1 | 1 | 164 KB | — | — |
| **Total** | **587** | **56** | | | |

## Related Documents

- [01-directory-structure.md](01-directory-structure.md) — Full directory structure
- [02-ftsi-database-schema.md](02-ftsi-database-schema.md) — FTSI database schema
- [03-cache-bin-format.md](03-cache-bin-format.md) — Cache .bin file format
- [04-guid-matching.md](04-guid-matching.md) — GUID byte matching mechanism
- [05-sequential-allocation.md](05-sequential-allocation.md) — Sequential allocation and image attribution
- [06-recovery-methodology.md](06-recovery-methodology.md) — Complete recovery methodology
