# FTSI 階層結構深度解析

## ParentGOID：三層樹狀結構的黏合劑

FTSI 資料庫用一張 `Entities` 表同時存放三種不同層級的實體——筆記本、節、頁面。這三者透過 `ParentGOID` 欄位串起，形成完整的樹狀結構。

### 結構關係

```
Entities 表（同一張表，Type 區分層級）

┌─────────────────────────────────────────────────────────┐
│ Type=4  Notebook "Work"                                  │
│ GOID: {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}        │
│ ParentGOID: NULL                     ← 最頂層，沒有 parent│
└──────────────────────┬──────────────────────────────────┘
                       │
        ParentGOID 指向 Notebook 的 GOID
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
┌──────────┐   ┌──────────┐   ┌───────────────┐
│ Type=2   │   │ Type=2   │   │ Type=2        │
│ "AWS"    │   │ "ELK"    │   │ "7rendMicro"  │
│ GOID:    │   │ GOID:    │   │ GOID:         │
│ ...{15}  │   │ ...{17}  │   │ ...{21}       │
└─────┬────┘   └────┬─────┘   └──────┬────────┘
      │              │                │
      │     ParentGOID 指向 Section 的 GOID
      │              │                │
   ┌──┴──┐     ┌─────┴───┐    ┌──────┴───────────┐
   ▼     ▼     ▼         ▼    ▼                  ▼
 Page  Page  Page      Page  "Historical CPB"  "2018 前進福岡"
 Type=1      Type=1          Type=1             Type=1
```

### 具體範例：從 Notebook 到 PageElement

以下是一條完整的鏈路，用真實資料說明每一層如何指向上一層：

```
                    ┌──── Entities (rowid=851) ────┐
NOTEBOOK (Type=4)   │ Title: "Work"                │
                    │ GOID:  {3DBD86EA-...}{19}    │
                    │ ParentGOID: NULL              │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
SECTION (Type=2)    │ Title: "7rendMicro"          │
                    │ GOID:  {3DBD86EA-...}{21}    │
                    │ ParentGOID: {3DBD86EA-...}{19}│ ← 指向 Work
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
PAGE (Type=1)       │ Title: "Historical CPB"      │
(rowid=781)         │ GOID:  {8D8463AD-...}{10}    │
                    │ GUID:  {1BDE8095-...}        │
                    │ ParentGOID: {3DBD86EA-...}{21}│ ← 指向 7rendMicro
                    │ GrandparentGOIDs:             │
                    │   {3DBD86EA-...}{19}          │ ← 快捷指向 Work
                    └──────────────┬───────────────┘
                                   │
                    EntityRowId = 781（rowid 關聯）
                                   │
                    ┌──────────────┴───────────────┐
PAGE ELEMENTS       │ 151 筆記錄                    │
                    │                              │
                    │ [Jcid 393230] 文字 ×150       │
                    │   "Historical CPB"            │
                    │   "股海冥燈"                   │
                    │   "Month" "NTD per share"     │
                    │   "2020 10" "1768" "6398"     │
                    │   ...                         │
                    │                              │
                    │ [Jcid 393233] 圖片 ×1         │
                    │   Alt: "1,750 1,500 1,250..." │
                    │   (OCR 辨識的股價圖文字)        │
                    └──────────────────────────────┘
```

---

## ParentGOID 查詢模式

### 從頁面反查到筆記本（由下而上）

```sql
-- 1. 找到頁面
SELECT GOID, Title, ParentGOID FROM Entities
WHERE Type = 1 AND Title = 'Historical CPB';
-- → ParentGOID = {3DBD86EA-...}{21}

-- 2. 用 ParentGOID 找到節
SELECT GOID, Title, ParentGOID FROM Entities
WHERE GOID = '{3DBD86EA-...}{21}';
-- → Title = '7rendMicro', ParentGOID = {3DBD86EA-...}{19}

-- 3. 用 ParentGOID 找到筆記本
SELECT Title FROM Entities
WHERE GOID = '{3DBD86EA-...}{19}';
-- → Title = 'Work'
```

### 從筆記本展開所有頁面（由上而下）

```sql
-- 找到筆記本下所有節
SELECT GOID, Title FROM Entities
WHERE Type = 2 AND ParentGOID = '{3DBD86EA-...}{19}';
-- → 22 個節

-- 找到某個節下所有頁面
SELECT GOID, Title FROM Entities
WHERE Type = 1 AND ParentGOID = '{3DBD86EA-...}{21}';
-- → 14 頁 (7rendMicro 節)
```

### GrandparentGOIDs 捷徑

頁面除了 `ParentGOID`（指向節），還有 `GrandparentGOIDs`（直接指向筆記本）。這是 OneNote 為了加速查詢預先計算的捷徑，避免每次都要跳兩層。

```
Page.ParentGOID         → Section
Page.GrandparentGOIDs   → Notebook（跳過 Section）
```

---

## PageElements：頁面內容的平面索引

### EntityRowId 關聯

`PageElements` 透過 `EntityRowId` 關聯到 `Entities` 的 `rowid`：

```sql
-- 找到某頁面的所有內容元素
SELECT * FROM PageElements WHERE EntityRowId = 781;
-- → 151 筆記錄
```

### 三種 Jcid 與資料內容

| Jcid | 類型 | Text 欄位內容 | 範例 |
|------|------|--------------|------|
| 393230 | 文字 | 段落/儲存格的純文字 | `"2020 10"`, `"1768"`, `"0.27632"` |
| 393233 | 圖片 | OCR 辨識文字 或 alt-text | `"1,750 1,500 1,250 1,000 750..."` |
| 393269 | 附件 | 原始檔名 | `"2018 AI Contest_Contestants TWN 1122.xlsx"` |

### 完整範例：「2018 前進福岡」頁面

這個頁面有 82 個 PageElements，展示了三種 Jcid 並存：

```
PageElements (EntityRowId = 11, 共 82 筆)
├── Jcid 393230 (文字) × 73
│   ├── "2018 前進福岡"              ← 標題
│   ├── "Morton Rainey (Author)"       ← 作者
│   ├── "Day 1 - 博多"              ← 內容段落
│   ├── "一風堂拉麵"                 ← 內容段落
│   └── ...
│
├── Jcid 393233 (圖片) × 6
│   ├── Alt: "福岡城跡..."           ← 照片的 OCR 文字
│   ├── Alt: "一風堂..."
│   └── ...
│
└── Jcid 393269 (附件) × 3
    ├── "2018 AI Contest_Contestants TWN 1122.xlsx"
    ├── "report.docx"
    └── "slides.pdf"
```

### GOID 的雙重角色

每個 PageElement 也有自己的 GOID：

```sql
SELECT GOID FROM PageElements WHERE EntityRowId = 781 AND Jcid = 393233;
-- → {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{84}
```

這個 GOID 在 cache .bin 的頁面檔案中也存在（以 mixed-endian 位元組形式）。它代表「這個圖片物件在 OneNote 修訂存放區中的唯一識別碼」。

---

## 跨表關聯總覽

```
Entities (Type=4)                     ← Notebook
    │
    │ GOID ←──── ParentGOID
    ▼
Entities (Type=2)                     ← Section
    │
    │ GOID ←──── ParentGOID
    ▼
Entities (Type=1)                     ← Page
    │
    │ rowid ←─── EntityRowId
    ▼
PageElements                          ← 文字/圖片/附件
    │
    │ rowid ←─── PageElementRowId
    ▼
┌───────────┬──────────┐
│ Hashtags  │ NoteFlags│              ← #標籤 / To Do 旗標
└───────────┴──────────┘
```

五張表，四層關聯，全部用 rowid / GOID 作為外鍵。
