# Cache .bin 檔案格式

## 概述

OneNote 的 cache 目錄包含所有筆記頁面和媒體的二進位快取。檔案使用 base-36 循序命名（`00000000.bin` ~ `0000069L.bin`），共 2,039 個檔案，總計 740 MB。

## 檔案分類

透過 magic bytes（檔案開頭的特徵位元組）可以將 .bin 檔分為兩大類：

### IMAGE 類型 (1,313 個)

| 格式 | Magic Bytes | 數量 | 說明 |
|------|-------------|------|------|
| PNG | `89 50 4E 47` | 1,041 | 螢幕截圖、圖表、照片 |
| JPEG | `FF D8 FF` | 214 | 照片、掃描文件 |
| GIF | `47 49 46 38` | 32 | 動畫 GIF |
| PDF | `25 50 44 46` | 16 | 嵌入的 PDF 文件 |
| ZIP | `50 4B 03 04` | 10 | 壓縮檔附件 |

這些檔案可以直接改副檔名後開啟，內容完整。

### DATA 類型 (726 個)

不以已知 magic bytes 開頭的檔案，屬於 OneNote 私有格式：

| 子類型 | 識別方式 | 數量 | 說明 |
|--------|----------|------|------|
| Page Data | 包含 `PageTitle` UTF-16LE 標記 | 592 | 筆記頁面的完整內容 |
| Section Store | 大型 (>1MB) | 少量 | Section 級修訂存放區 |
| Index/Allocation | 前 3 個特殊檔案 | 3 | 配置表、物件目錄 |
| Other Data | 介於頁面之間的小檔案 | ~131 | 修訂元資料、其他 |

---

## 特殊檔案詳解

### header (72 bytes)

快取的元資料檔案，不是 .bin 格式。包含版本號和計數器。

### 00000000.bin — 配置表 (Allocation Table)

- 大小：約 380 KB
- 追蹤已使用的 file ID
- 包含部分圖片 file ID 的參照
- 在我們的分析中找到 359 個圖片 file ID

### 00000001.bin — 物件目錄 (Object Directory)

- 大小：約 380 KB
- **GUID → file ID 的映射表**
- 以 mixed-endian GUID 位元組儲存
- 在我們的分析中找到 342 個圖片 file ID
- 部分映射已過時（不包含所有現存圖片）

### 00000002.bin — Section-level 修訂存放區

- 大小：約 1.9 MB
- 包含 **所有頁面的標題和 GUID**（UTF-16LE 編碼）
- 類似於 OneNote 的 Table of Contents
- 可用來確認頁面清單的完整性

---

## Page Data 檔案結構

Page Data 是 OneNote 的 MS-ONESTORE 格式的簡化版本。主要特徵：

### 識別方式

- 檔案大小 ≥ 4,096 bytes
- 包含 UTF-16LE 編碼的 `PageTitle` 字串

### 內容結構

```
┌─────────────────────────────────────┐
│  Header / Revision metadata          │  固定結構，包含版本資訊
├─────────────────────────────────────┤
│  GUID / GOID 參照區                  │  頁面本身和關聯物件的 GUID
│  ├── 頁面 GUID (mixed-endian)        │
│  ├── 節 GUID                         │
│  └── 圖片/附件 GOID                  │
├─────────────────────────────────────┤
│  文字內容 (UTF-16LE)                 │
│  ├── "PageTitle"                     │  標記
│  ├── 頁面標題                        │
│  ├── "Calibri" / "Calibri Light"     │  字型名稱
│  ├── "PageDateTime"                  │  標記
│  ├── 內容段落                        │
│  └── 表格資料                        │
├─────────────────────────────────────┤
│  嵌入小型 PNG (可選)                  │
│  ├── 40x40 圖示                      │  UI 相關小圖
│  └── 80x80 圖示                      │
├─────────────────────────────────────┤
│  CID 參照 (可選)                     │
│  ├── "cidimage008.png@01D4835C..."   │  Content-ID 格式的圖片參照
│  └── "Untitled picture.png"          │  內部圖片檔名
├─────────────────────────────────────┤
│  原始檔案路徑 (可選)                  │
│  └── "C:\Users\morton_rainey\..."      │  剪貼來源路徑
└─────────────────────────────────────┘
```

### 大小分佈

| 大小範圍 | 數量 | 佔比 |
|----------|------|------|
| 4 - 16 KB | 221 | 37% |
| 16 - 64 KB | 218 | 37% |
| 64 - 256 KB | 256 | 24% |
| > 256 KB | 23 | 2% |

### 嵌入 PNG

部分頁面檔案內嵌小型 PNG 圖示（通常 40x40 或 80x80 像素），可透過搜尋 PNG signature (`89 50 4E 47 0D 0A 1A 0A`) 和 IEND marker (`49 45 4E 44 AE 42 60 82`) 來提取。

**注意**：大型圖片不會嵌入在頁面檔案中，而是作為獨立的 .bin 檔案儲存。

---

## IMAGE 檔案

圖片檔案就是標準的影像格式，直接存為 .bin 副檔名。

### PNG 尺寸範例

從實際快取中觀察到的常見尺寸：

```
40x40     ← 小圖示 (嵌入在 page data 中)
80x80     ← 小圖示 (嵌入在 page data 中)
449x320   ← 縮圖
681x340   ← 中型圖表
730x329   ← 中型圖表
1024x543  ← 螢幕截圖
1917x1016 ← 全螢幕截圖
1920x1022 ← 全螢幕截圖
```

### 確認方式

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
