# FTSI 資料庫 Schema (FullTextSearchIndex)

## 概述

每個筆記本對應一個獨立的 SQLite 資料庫，位於：
```
15.0/FullTextSearchIndex/{NotebookGOID}.db
```

資料庫的 GOID 即為該筆記本在 OneNote 中的 Global Object ID。

## 資料表一覽

| 表名 | 類型 | 說明 | 範例行數 (Work) |
|------|------|------|-----------------|
| `Entities` | 一般表 | 筆記本/節/頁面的階層結構 | 436 |
| `PageElements` | 一般表 | 每個頁面的內容元素 | 26,373 |
| `Hashtags` | 一般表 | 標籤 (#tag) 索引 | 986 |
| `NoteFlags` | 一般表 | 待辦事項/旗標 | 34 |
| `Metadata` | 一般表 | Schema 版本 | 1 |
| `EntityContents` | FTS4 虛擬表 | 全文搜尋：實體標題 | 436 |
| `PageElementContents` | FTS4 虛擬表 | 全文搜尋：頁面內容 | 26,373 |
| `HashtagContents` | FTS4 虛擬表 | 全文搜尋：標籤 | 986 |
| `NoteFlagContents` | FTS4 虛擬表 | 全文搜尋：旗標 | 34 |

---

## Entities 表

### Schema

```sql
CREATE TABLE Entities (
    Type              INTEGER NOT NULL,
    GOID              TEXT NOT NULL UNIQUE,
    GUID              TEXT,
    GOSID             TEXT,
    ParentGOID        TEXT,
    GrandparentGOIDs  TEXT,
    ContentRID        TEXT,
    RootRevGenCount   INTEGER,
    LastModifiedTime  INTEGER,
    RecentTime        INTEGER,
    PinTime           INTEGER,
    Color             INTEGER,
    Title             TEXT,
    EnterpriseIdentity TEXT
);
```

### Type 欄位定義

| Type 值 | 意義 | 說明 |
|---------|------|------|
| 1 | **Page** (頁面) | 最末端的內容單位 |
| 2 | **Section** (節) | 頁面的容器，對應 OneNote 的「節」 |
| 4 | **Notebook** (筆記本) | 最上層，每個 DB 只有一個 |

### GOID 格式

GOID (Global Object ID) 格式為 `{GUID}{序號}`：

```
筆記本: {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}
  節:   {4AEDE97C-6F42-6F4D-82E1-AF5A6E34A06D}{15}
  頁面: {8D8463AD-4DFE-1644-B754-00D458F87468}{10}
```

### 階層關係

透過 `ParentGOID` 建立三層階層：

```
Notebook (Type=4)
  └── ParentGOID = NULL
      │
      ├── Section (Type=2)
      │   └── ParentGOID = Notebook 的 GOID
      │       │
      │       ├── Page (Type=1)
      │       │   └── ParentGOID = Section 的 GOID
      │       ├── Page (Type=1)
      │       └── ...
      │
      ├── Section (Type=2)
      └── ...
```

### GUID 欄位

每個 Entity 有獨立的 GUID，格式為標準 UUID：
```
{1BDE8095-99F1-44A0-8B67-0438D3A02923}
```

**這個 GUID 是連結 FTSI 與 cache .bin 檔案的關鍵**。它會以 mixed-endian 位元組形式嵌入在對應的 page .bin 檔案中。

### ContentRID 欄位

Content Revision ID，格式也是 GOID：
```
{A267CCBF-9567-D6E2-29EC-C07EE63FC0CE}{1}
```
代表頁面內容的修訂版本。

### LastModifiedTime

Windows FILETIME 格式（100 奈秒為單位，從 1601-01-01 起算）：
```
132531880040000000  →  約 2020 年
```

### 範例資料

```
Type=4 (Notebook):
  GOID:  {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}
  Title: Work

Type=2 (Section):
  GOID:       {4AEDE97C-6F42-6F4D-82E1-AF5A6E34A06D}{15}
  ParentGOID: {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}
  Title:      AWS

Type=1 (Page):
  GOID:       {8D8463AD-4DFE-1644-B754-00D458F87468}{10}
  GUID:       {1BDE8095-99F1-44A0-8B67-0438D3A02923}
  ParentGOID: {4AEDE97C-6F42-6F4D-82E1-AF5A6E34A06D}{15}
  Title:      Historical CPB
```

---

## PageElements 表

### Schema

```sql
CREATE TABLE PageElements (
    GOID         TEXT NOT NULL,
    Text         TEXT,
    Jcid         INTEGER NOT NULL,
    EntityRowId  INTEGER NOT NULL
);
```

### Jcid 類型定義

| Jcid 值 | 意義 | 範例行數 (Work) | 說明 |
|---------|------|-----------------|------|
| 393230 | **文字內容** | 25,922 | 段落、表格儲存格、標題等純文字 |
| 393233 | **圖片 (alt-text)** | 424 | 圖片的替代文字 / OCR 辨識文字 |
| 393269 | **檔案附件** | 27 | 嵌入檔案的原始檔名 |

### EntityRowId 關聯

`EntityRowId` 對應 `Entities` 表的 `rowid`，用來建立「哪些元素屬於哪個頁面」的關聯。

### Jcid 393230 — 文字內容

```
GOID:        {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{19}
Text:        "Historical CPB"
Jcid:        393230
EntityRowId: 781
```

每個段落、表格儲存格都是獨立的一筆記錄。頁面標題也是一個 393230 元素。

### Jcid 393233 — 圖片 Alt-text

```
GOID:        {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{84}
Text:        "1,750 \n1,500 \n1,250 \n1,000 \n750 \n500 \n250 \n2013-01 ..."
Jcid:        393233
EntityRowId: 781
```

Text 欄位儲存的是圖片的 OCR 辨識結果或使用者手動設定的替代文字。這是確認圖片內容的重要依據。

### Jcid 393269 — 檔案附件

```
GOID:        {6B05D46F-45F1-F242-B1F1-D3BEBBBB7C77}{17}
Text:        "2018 AI Contest_Contestants TWN 1122.xlsx"
Jcid:        393269
EntityRowId: 某頁面的 rowid
```

Text 欄位儲存的是原始檔名。

---

## Hashtags 表

```sql
CREATE TABLE Hashtags (
    PageElementRowId INTEGER NOT NULL
);
```

關聯到 PageElements 的 rowid，用來標記哪些元素包含 #hashtag。

## NoteFlags 表

```sql
CREATE TABLE NoteFlags (
    Shape               INTEGER NOT NULL,
    Status              INTEGER NOT NULL,
    Label               TEXT,
    PageElementRowId    INTEGER NOT NULL
);
```

追蹤 To Do、Important 等旗標的狀態。

## Metadata 表

```sql
CREATE TABLE Metadata (
    SchemaVersion INTEGER NOT NULL
);
-- 只有 1 筆記錄，SchemaVersion = 5
```

---

## AccessibilityCheckerIndex (ACI) 資料庫

同樣每個筆記本一個 DB，Schema 如下：

### Entities 表

```sql
CREATE TABLE Entities (
    EntityType       INTEGER NOT NULL,
    EntityGOID       TEXT NOT NULL UNIQUE,
    EntityName       TEXT,
    RootRevGenCount  INTEGER
);
```

與 FTSI 的 Entities 使用相同的 GOID，但只保留基本資訊。

### Violations 表

```sql
CREATE TABLE Violations (
    EntityID             INTEGER NOT NULL,
    Name                 TEXT NOT NULL,
    Type                 INTEGER NOT NULL,
    Location             TEXT,
    SelectionStartIndex  INTEGER,
    SelectionEndIndex    INTEGER
);
```

記錄無障礙違規項目（如缺少圖片替代文字）。Work 筆記本有 8,217 筆違規。

### ViolationElements 表

```sql
CREATE TABLE ViolationElements (
    ViolationID   INTEGER NOT NULL,
    ElementGOID   TEXT NOT NULL
);
```

將違規項目對應到具體的 GOID 元素。這個表對於找到圖片的 GOID 很有幫助——每個缺少 alt-text 的圖片都有一筆違規記錄。
