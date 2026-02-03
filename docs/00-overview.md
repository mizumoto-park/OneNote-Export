# OneNote macOS 本機快取結構總覽

## 背景

OneNote for Mac 將所有筆記本資料快取在本機的 sandboxed container 中。即使雲端帳號已登出或同步中斷，本機快取仍然保留完整的筆記內容、圖片、附件。本文件記錄如何從這些快取中還原完整的筆記。

## 快取根目錄

```
~/Library/Containers/com.microsoft.onenote.mac/
└── Data/Library/Application Support/Microsoft User Data/OneNote/
    ├── 15.0/                    ← 目前使用中的資料
    ├── 15.0-ori/                ← 原始備份 (4 items)
    └── 15.0-restore/            ← 還原備份 (9 items)
```

## 15.0/ 主要子目錄

```
15.0/
├── cache/                       ← 核心：所有筆記頁面 + 圖片的二進位快取
│   ├── header                   ← 72 bytes，快取 metadata
│   ├── 00000000.bin             ← 配置表 (Allocation Table)
│   ├── 00000001.bin             ← 物件目錄 (Object Directory)
│   ├── 00000002.bin ~ ...       ← 筆記頁面 + 圖片，共 2,039 個 .bin 檔
│   └── (total: 740 MB)
│
├── FullTextSearchIndex/         ← 全文搜尋索引 SQLite 資料庫
│   ├── {GUID}{N}.db             ← 每個筆記本一個 DB，共 5 個
│   └── MasterIndex/Master.db    ← 索引版本追蹤 (可能不存在)
│
├── AccessibilityCheckerIndex/   ← 無障礙檢查索引
│   └── {GUID}{N}.db             ← 每個筆記本一個 DB，共 5 個
│
├── ServerListings/              ← 伺服器連線快取 (.onesrvcache)
├── Preferences.dat              ← 標籤定義 (To Do, Important 等)
└── (其他: telemetry, UI state)
```

## 資料關係概觀

```
┌──────────────────────────┐
│   FTSI SQLite 資料庫      │  ← 結構化資料：階層、文字、搜尋索引
│   (FullTextSearchIndex)   │
│                          │
│  Entities 表 ──────────┐ │
│  (Notebook/Section/Page)│ │
│          │              │ │
│          ▼              │ │
│  PageElements 表        │ │
│  (文字/圖片alt/附件名)   │ │
└──────────┬───────────────┘
           │ GUID 位元組匹配
           ▼
┌──────────────────────────┐
│   Cache .bin 快取檔案     │  ← 二進位資料：頁面內容、嵌入圖片、附件
│                          │
│  Page Data (.bin)        │
│  ├── UTF-16LE 文字內容    │
│  ├── GUID/GOID 參照      │
│  └── 小型嵌入 PNG 圖示    │
│                          │
│  Image Files (.bin)      │
│  ├── PNG / JPEG / GIF    │  ← 緊接在 Page Data 之後（循序配置）
│  └── PDF / ZIP 附件      │
└──────────────────────────┘
```

## 五本筆記本概覽

| 筆記本 | 頁數 | 節數 | FTSI DB 大小 | 圖片數 (FTSI) | 附件數 |
|--------|------|------|-------------|--------------|--------|
| Work | 413 | 22 | 7,984 KB | 424 | 27 |
| Personal | 160 | 30 | 3,100 KB | 431 | 8 |
| Evernote | 5 | 1 | 216 KB | — | — |
| Morton Rainey 的筆記本 | 8 | 2 | 352 KB | — | — |
| 7rendMicro | 1 | 1 | 164 KB | — | — |
| **合計** | **587** | **56** | | | |

## 相關文件

- [01-directory-structure.md](01-directory-structure.md) — 完整目錄結構
- [02-ftsi-database-schema.md](02-ftsi-database-schema.md) — FTSI 資料庫 Schema
- [03-cache-bin-format.md](03-cache-bin-format.md) — Cache .bin 檔案格式
- [04-guid-matching.md](04-guid-matching.md) — GUID 位元組匹配機制
- [05-sequential-allocation.md](05-sequential-allocation.md) — 循序配置與圖片歸屬
- [06-recovery-methodology.md](06-recovery-methodology.md) — 完整還原方法論
