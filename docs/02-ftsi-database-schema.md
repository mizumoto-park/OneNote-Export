# FTSI Database Schema (FullTextSearchIndex)

## Overview

Each notebook corresponds to an independent SQLite database located at:
```
15.0/FullTextSearchIndex/{NotebookGOID}.db
```

The database GOID is the notebook's Global Object ID in OneNote.

## Table Summary

| Table | Type | Description | Example Row Count (Work) |
|-------|------|-------------|--------------------------|
| `Entities` | Regular | Notebook/Section/Page hierarchy | 436 |
| `PageElements` | Regular | Content elements for each page | 26,373 |
| `Hashtags` | Regular | Hashtag (#tag) index | 986 |
| `NoteFlags` | Regular | To-do items / flags | 34 |
| `Metadata` | Regular | Schema version | 1 |
| `EntityContents` | FTS4 Virtual | Full-text search: entity titles | 436 |
| `PageElementContents` | FTS4 Virtual | Full-text search: page content | 26,373 |
| `HashtagContents` | FTS4 Virtual | Full-text search: hashtags | 986 |
| `NoteFlagContents` | FTS4 Virtual | Full-text search: flags | 34 |

---

## Entities Table

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

### Type Field Definition

| Type Value | Meaning | Description |
|------------|---------|-------------|
| 1 | **Page** | The leaf-level content unit |
| 2 | **Section** | Container for pages, corresponds to a OneNote "section" |
| 4 | **Notebook** | Top level, one per database |

### GOID Format

GOID (Global Object ID) format is `{GUID}{sequence}`:

```
Notebook: {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}
  Section: {4AEDE97C-6F42-6F4D-82E1-AF5A6E34A06D}{15}
    Page:  {8D8463AD-4DFE-1644-B754-00D458F87468}{10}
```

### Hierarchy Relationship

A three-level hierarchy is established through `ParentGOID`:

```
Notebook (Type=4)
  └── ParentGOID = NULL
      │
      ├── Section (Type=2)
      │   └── ParentGOID = Notebook's GOID
      │       │
      │       ├── Page (Type=1)
      │       │   └── ParentGOID = Section's GOID
      │       ├── Page (Type=1)
      │       └── ...
      │
      ├── Section (Type=2)
      └── ...
```

### GUID Field

Each Entity has a unique GUID in standard UUID format:
```
{1BDE8095-99F1-44A0-8B67-0438D3A02923}
```

**This GUID is the key link between FTSI and cache .bin files.** It is embedded in the corresponding page .bin file in mixed-endian byte format.

### ContentRID Field

Content Revision ID, also in GOID format:
```
{A267CCBF-9567-D6E2-29EC-C07EE63FC0CE}{1}
```
Represents the content revision version of the page.

### LastModifiedTime

Windows FILETIME format (100-nanosecond intervals since 1601-01-01):
```
132531880040000000  →  approximately 2020
```

### Example Data

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

## PageElements Table

### Schema

```sql
CREATE TABLE PageElements (
    GOID         TEXT NOT NULL,
    Text         TEXT,
    Jcid         INTEGER NOT NULL,
    EntityRowId  INTEGER NOT NULL
);
```

### Jcid Type Definition

| Jcid Value | Meaning | Example Count (Work) | Description |
|------------|---------|----------------------|-------------|
| 393230 | **Text content** | 25,922 | Paragraphs, table cells, headings, etc. |
| 393233 | **Image (alt-text)** | 424 | Image alt-text / OCR recognized text |
| 393269 | **File attachment** | 27 | Original filename of embedded files |

### EntityRowId Association

`EntityRowId` corresponds to the `rowid` of the `Entities` table, establishing the "which elements belong to which page" relationship.

### Jcid 393230 — Text Content

```
GOID:        {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{19}
Text:        "Historical CPB"
Jcid:        393230
EntityRowId: 781
```

Each paragraph and table cell is stored as a separate record. The page title is also a 393230 element.

### Jcid 393233 — Image Alt-text

```
GOID:        {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{84}
Text:        "1,750 \n1,500 \n1,250 \n1,000 \n750 \n500 \n250 \n2013-01 ..."
Jcid:        393233
EntityRowId: 781
```

The Text field stores the OCR recognition result or user-defined alt-text for the image. This is an important reference for confirming image content.

### Jcid 393269 — File Attachment

```
GOID:        {6B05D46F-45F1-F242-B1F1-D3BEBBBB7C77}{17}
Text:        "2018 AI Contest_Contestants TWN 1122.xlsx"
Jcid:        393269
EntityRowId: page's rowid
```

The Text field stores the original filename.

---

## Hashtags Table

```sql
CREATE TABLE Hashtags (
    PageElementRowId INTEGER NOT NULL
);
```

Links to PageElements rowid to mark which elements contain #hashtags.

## NoteFlags Table

```sql
CREATE TABLE NoteFlags (
    Shape               INTEGER NOT NULL,
    Status              INTEGER NOT NULL,
    Label               TEXT,
    PageElementRowId    INTEGER NOT NULL
);
```

Tracks the status of To Do, Important, and other flags.

## Metadata Table

```sql
CREATE TABLE Metadata (
    SchemaVersion INTEGER NOT NULL
);
-- Only 1 record, SchemaVersion = 5
```

---

## AccessibilityCheckerIndex (ACI) Database

Also one DB per notebook, with the following schema:

### Entities Table

```sql
CREATE TABLE Entities (
    EntityType       INTEGER NOT NULL,
    EntityGOID       TEXT NOT NULL UNIQUE,
    EntityName       TEXT,
    RootRevGenCount  INTEGER
);
```

Uses the same GOIDs as the FTSI Entities but only retains basic information.

### Violations Table

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

Records accessibility violations (e.g., missing image alt-text). The Work notebook has 8,217 violations.

### ViolationElements Table

```sql
CREATE TABLE ViolationElements (
    ViolationID   INTEGER NOT NULL,
    ElementGOID   TEXT NOT NULL
);
```

Maps violations to specific GOID elements. This table is helpful for finding image GOIDs — every image missing alt-text has a violation record.
