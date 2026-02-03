# FTSI Hierarchy Structure Deep Dive

## ParentGOID: The Glue for the Three-Level Tree

The FTSI database uses a single `Entities` table to store three different levels of entities — notebooks, sections, and pages. These three are linked through the `ParentGOID` field to form a complete tree structure.

### Structural Relationships

```
Entities table (single table, differentiated by Type)

┌─────────────────────────────────────────────────────────┐
│ Type=4  Notebook "Work"                                  │
│ GOID: {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}        │
│ ParentGOID: NULL                     ← Top level, no parent│
└──────────────────────┬──────────────────────────────────┘
                       │
        ParentGOID points to Notebook's GOID
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
      │     ParentGOID points to Section's GOID
      │              │                │
   ┌──┴──┐     ┌─────┴───┐    ┌──────┴───────────┐
   ▼     ▼     ▼         ▼    ▼                  ▼
 Page  Page  Page      Page  "Historical CPB"  "2018 Fukuoka"
 Type=1      Type=1          Type=1             Type=1
```

### Concrete Example: From Notebook to PageElement

Here is a complete chain using real data to illustrate how each level points to the one above:

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
                    │ ParentGOID: {3DBD86EA-...}{19}│ ← Points to Work
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
PAGE (Type=1)       │ Title: "Historical CPB"      │
(rowid=781)         │ GOID:  {8D8463AD-...}{10}    │
                    │ GUID:  {1BDE8095-...}        │
                    │ ParentGOID: {3DBD86EA-...}{21}│ ← Points to 7rendMicro
                    │ GrandparentGOIDs:             │
                    │   {3DBD86EA-...}{19}          │ ← Shortcut to Work
                    └──────────────┬───────────────┘
                                   │
                    EntityRowId = 781 (rowid association)
                                   │
                    ┌──────────────┴───────────────┐
PAGE ELEMENTS       │ 151 records                   │
                    │                              │
                    │ [Jcid 393230] Text ×150       │
                    │   "Historical CPB"            │
                    │   "Stock Price"               │
                    │   "Month" "NTD per share"     │
                    │   "2020 10" "1768" "6398"     │
                    │   ...                         │
                    │                              │
                    │ [Jcid 393233] Image ×1        │
                    │   Alt: "1,750 1,500 1,250..." │
                    │   (OCR text from stock chart)  │
                    └──────────────────────────────┘
```

---

## ParentGOID Query Patterns

### From Page Up to Notebook (Bottom-Up)

```sql
-- 1. Find the page
SELECT GOID, Title, ParentGOID FROM Entities
WHERE Type = 1 AND Title = 'Historical CPB';
-- → ParentGOID = {3DBD86EA-...}{21}

-- 2. Use ParentGOID to find the section
SELECT GOID, Title, ParentGOID FROM Entities
WHERE GOID = '{3DBD86EA-...}{21}';
-- → Title = '7rendMicro', ParentGOID = {3DBD86EA-...}{19}

-- 3. Use ParentGOID to find the notebook
SELECT Title FROM Entities
WHERE GOID = '{3DBD86EA-...}{19}';
-- → Title = 'Work'
```

### From Notebook Down to All Pages (Top-Down)

```sql
-- Find all sections under a notebook
SELECT GOID, Title FROM Entities
WHERE Type = 2 AND ParentGOID = '{3DBD86EA-...}{19}';
-- → 22 sections

-- Find all pages under a specific section
SELECT GOID, Title FROM Entities
WHERE Type = 1 AND ParentGOID = '{3DBD86EA-...}{21}';
-- → 14 pages (7rendMicro section)
```

### GrandparentGOIDs Shortcut

Pages have both `ParentGOID` (pointing to section) and `GrandparentGOIDs` (pointing directly to notebook). This is a precomputed shortcut by OneNote to speed up queries, avoiding the need to traverse two levels each time.

```
Page.ParentGOID         → Section
Page.GrandparentGOIDs   → Notebook (skips Section)
```

---

## PageElements: Flat Index of Page Content

### EntityRowId Association

`PageElements` links to `Entities` via `EntityRowId` corresponding to `rowid`:

```sql
-- Find all content elements for a specific page
SELECT * FROM PageElements WHERE EntityRowId = 781;
-- → 151 records
```

### Three Jcid Types and Their Data

| Jcid | Type | Text Field Content | Example |
|------|------|-------------------|---------|
| 393230 | Text | Plain text of paragraphs/cells | `"2020 10"`, `"1768"`, `"0.27632"` |
| 393233 | Image | OCR recognized text or alt-text | `"1,750 1,500 1,250 1,000 750..."` |
| 393269 | Attachment | Original filename | `"2018 AI Contest_Contestants TWN 1122.xlsx"` |

### Complete Example: "2018 Fukuoka Trip" Page

This page has 82 PageElements, demonstrating all three Jcid types coexisting:

```
PageElements (EntityRowId = 11, 82 records total)
├── Jcid 393230 (Text) × 73
│   ├── "2018 Fukuoka Trip"           ← Title
│   ├── "Morton Rainey (Author)"       ← Author
│   ├── "Day 1 - Hakata"              ← Content paragraph
│   ├── "Ippudo Ramen"                ← Content paragraph
│   └── ...
│
├── Jcid 393233 (Image) × 6
│   ├── Alt: "Fukuoka Castle ruins..."  ← OCR text from photo
│   ├── Alt: "Ippudo..."
│   └── ...
│
└── Jcid 393269 (Attachment) × 3
    ├── "2018 AI Contest_Contestants TWN 1122.xlsx"
    ├── "report.docx"
    └── "slides.pdf"
```

### Dual Role of GOIDs

Each PageElement also has its own GOID:

```sql
SELECT GOID FROM PageElements WHERE EntityRowId = 781 AND Jcid = 393233;
-- → {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{84}
```

This GOID also exists in the cache .bin page file (in mixed-endian byte form). It represents "the unique identifier of this image object in the OneNote revision store."

---

## Cross-Table Relationship Overview

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
PageElements                          ← Text/Image/Attachment
    │
    │ rowid ←─── PageElementRowId
    ▼
┌───────────┬──────────┐
│ Hashtags  │ NoteFlags│              ← #Tags / To Do flags
└───────────┴──────────┘
```

Five tables, four levels of association, all using rowid / GOID as foreign keys.
