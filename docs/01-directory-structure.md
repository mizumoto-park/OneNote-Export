# OneNote macOS Local Cache Directory Structure

## Container Path

As a macOS sandboxed app, OneNote stores all data in:

```
~/Library/Containers/com.microsoft.onenote.mac/Data/Library/
```

## Application Support Structure

```
Application Support/Microsoft User Data/OneNote/
├── 15.0/                                ← Main data directory
│   ├── cache/                           ← Binary cache (740 MB)
│   │   ├── header                       ← 72 bytes cache metadata
│   │   ├── 00000000.bin                 ← Allocation Table (380 KB)
│   │   ├── 00000001.bin                 ← Object Directory (380 KB)
│   │   ├── 00000002.bin                 ← Section-level revision store (1.9 MB)
│   │   ├── 00000003.bin ~ 0000069L.bin  ← Page data + images (2,036 files)
│   │   └── (2,039 .bin files total)
│   │
│   ├── FullTextSearchIndex/             ← Full-text search index
│   │   ├── {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}.db   ← Work (7,984 KB)
│   │   ├── {D62C1D86-38B0-0B4C-9A45-7259DDD20395}{51}.db   ← Personal (3,100 KB)
│   │   ├── {D62C1D86-38B0-0B4C-9A45-7259DDD20395}{10}.db   ← Morton Rainey (352 KB)
│   │   ├── {248E7F28-E3C6-AC43-A45F-8A5936C978E7}{10}.db   ← Evernote (216 KB)
│   │   └── {5497DFA7-B4A4-EC49-95F1-9B049B091C4E}{10}.db   ← 7rendMicro (164 KB)
│   │
│   ├── AccessibilityCheckerIndex/       ← Accessibility checker index
│   │   └── (same 5 .db files, matching GUIDs)
│   │
│   ├── ServerListings/                  ← Server cache
│   │   ├── 68A22224B54C82C4F80647B75C7EC6A4.onesrvcache
│   │   └── E337680823748F7C1DE79811CCC57B24.onesrvcache
│   │
│   └── Preferences.dat                  ← Tag definitions (84 KB, binary)
│
├── 15.0-ori/                            ← Original backup
│   └── (4 items)
│
└── 15.0-restore/                        ← Restore backup
    └── (9 items, same structure as 15.0/)
```

## Other Related Directories

```
~/Library/Containers/com.microsoft.onenote.mac/Data/Library/
├── Preferences/
│   └── com.microsoft.onenote.mac.plist  ← App preferences (binary plist)
│
├── Caches/
│   ├── Notifications/ONSharingNotifications/
│   │   └── settings.plist               ← Sharing notification settings (XML plist)
│   └── (other: WebKit cache, telemetry)
│
├── Application Support/
│   ├── com.microsoft.Office.ServiceV2/  ← Office service
│   │   └── OfficeFileCache/
│   │       └── CentralTable.db          ← Empty (0 MasterFile rows)
│   │
│   ├── FileUIKit/
│   │   └── FileUIKit.sqlite             ← CoreData: 3 NavigationTargets
│   │
│   └── com.microsoft.Office.Telemetry/
│       └── AriaStorage.db               ← Telemetry data (5,277 events)
│
└── Saved Application State/             ← Window state
```

## cache/ Directory Naming Convention

The .bin files in the cache directory use **base-36 sequential numbering**:

```
Character set: 0-9, A-Z (36 characters total)

Examples:
  00000000.bin  →  file ID 0
  00000009.bin  →  file ID 9
  0000000A.bin  →  file ID 10
  0000000Z.bin  →  file ID 35
  00000010.bin  →  file ID 36
  000004LC.bin  →  file ID 5952
  0000069L.bin  →  max file ID (~8,000+)
```

New files are assigned incrementing IDs. This property is the foundation of the sequential allocation model (image attribution).

## Special Files

| File | Size | Purpose |
|------|------|---------|
| `header` | 72 bytes | Cache version, counters, and other metadata |
| `00000000.bin` | 380 KB | Allocation Table: tracks which file IDs are in use, contains some image file IDs |
| `00000001.bin` | 380 KB | Object Directory: GUID → file ID mapping table |
| `00000002.bin` | 1.9 MB | Section-level revision store, contains all page titles and GUIDs |
| `Preferences.dat` | 84 KB | Defines OneNote tags (To Do, Important, Question, etc.) |
