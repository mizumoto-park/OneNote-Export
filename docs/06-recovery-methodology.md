# 完整還原方法論

## 目標

從 OneNote macOS 本機快取中還原所有筆記，產出：

```
~/Desktop/OneNote-Export/
├── index.md                     ← 全部筆記的目錄索引
├── Work/                        ← 筆記本
│   ├── AWS/                     ← 節
│   │   ├── page-title.md        ← 頁面 (文字 + 圖片參照)
│   │   ├── page-title_images/   ← 該頁面的圖片
│   │   │   ├── image_001.png
│   │   │   └── image_002.jpg
│   │   └── ...
│   └── ...
├── Personal/
├── Evernote/
├── Morton Rainey/
└── 7rendMicro/
```

## 七步還原流程

### Step 1: 載入 FTSI 頁面階層

從 5 個 FTSI SQLite 資料庫讀取 Entities 表：

```python
# 輸入: 5 個 FTSI .db 檔案
# 輸出: 587 頁的完整階層 (Notebook → Section → Page)

for db_file, notebook_name in NOTEBOOKS:
    conn = sqlite3.connect(db_path)

    # 建立 Section 查詢表
    sections = {}
    for goid, title in conn.execute(
        "SELECT GOID, Title FROM Entities WHERE Type = 2"
    ):
        sections[goid] = title

    # 讀取所有頁面
    for row in conn.execute(
        "SELECT rowid, GOID, GUID, ParentGOID, Title "
        "FROM Entities WHERE Type = 1"
    ):
        section_name = sections[row[3]]  # ParentGOID → Section Title

        # 讀取頁面內容元素
        elements = conn.execute(
            "SELECT Text, Jcid FROM PageElements WHERE EntityRowId = ?",
            (row[0],)
        ).fetchall()

        texts       = [t for t, j in elements if j == 393230 and t]
        image_alts  = [t for t, j in elements if j == 393233 and t]
        file_names  = [t for t, j in elements if j == 393269 and t]
```

### Step 2: 分類所有 Cache .bin 檔案

掃描 2,039 個 .bin 檔，用 magic bytes 分類：

```python
# 輸入: cache/ 目錄中所有 .bin 檔案
# 輸出: 每個檔案的類型 (IMAGE/DATA) + 是否為 page data

for fname in os.listdir(CACHE_DIR):
    with open(filepath, 'rb') as f:
        header = f.read(8)

    if header[:4] == b'\x89PNG':       type = 'IMAGE/PNG'
    elif header[:3] == b'\xff\xd8\xff': type = 'IMAGE/JPEG'
    elif header[:4] == b'GIF8':        type = 'IMAGE/GIF'
    elif header[:4] == b'%PDF':        type = 'IMAGE/PDF'
    elif header[:4] == b'PK\x03\x04': type = 'IMAGE/ZIP'
    else:                              type = 'DATA'

    # DATA 檔案中，包含 "PageTitle" (UTF-16LE) 的是 page data
    if type == 'DATA' and size >= 4096:
        if b'P\x00a\x00g\x00e\x00T\x00i\x00t\x00l\x00e\x00' in data:
            is_page = True
```

結果：592 個 page data + 1,313 個 image + 134 個 other data

### Step 3: GUID 位元組匹配

將 FTSI 頁面對應到 cache .bin 檔案：

```python
# 輸入: FTSI 頁面的 GUID + page data .bin 檔案
# 輸出: 每個 FTSI 頁面 ↔ 其對應的 .bin 檔案

for page_bin in page_data_bins:
    data = open(page_bin.filepath, 'rb').read()
    for guid_bytes, page_info in guid_lookup.items():
        if guid_bytes in data:
            page_info['bin_file'] = page_bin
            break
```

匹配率：94.9%（558/587 頁面成功匹配）

### Step 4: 循序配置映射

為每個頁面找到其所屬的圖片：

```python
# 規則: 從 page data 往後掃描，所有 IMAGE 檔案
#       都屬於這個頁面，直到遇到下一個 DATA (≥4KB)

for page_bin in matched_pages:
    images = []
    for next_file in files_after(page_bin):
        if next_file.type == 'IMAGE':
            images.append(next_file)
        elif next_file.is_page or (next_file.type == 'DATA' and next_file.size >= 4096):
            break
    page_bin['images'] = images
```

結果：1,246 張圖片映射到 160 個頁面

### Step 5: 提取嵌入 PNG

從 page data 中提取大型嵌入圖片（>100x100 像素）：

```python
# 搜尋 PNG signature → IEND marker，提取完整 PNG 資料
# 過濾掉小型 UI 圖示 (≤100x100)
```

結果：15 張大型嵌入圖片

### Step 6: 匯出

將所有資料寫入檔案系統：

```python
for page in all_pages:
    # 建立目錄: Notebook/Section/
    os.makedirs(f"{OUTPUT}/{notebook}/{section}/")

    # 寫入 Markdown
    with open(f".../{title}.md", 'w') as f:
        f.write(f"# {page.title}\n\n")
        f.write(f"> **Notebook:** {notebook} / **Section:** {section}\n\n")
        for text in page.texts:
            f.write(text + "\n")
        for img in page.images:
            f.write(f"![image]({title}_images/{img.name})\n")

    # 複製圖片
    for img in page.images:
        shutil.copy2(img.cache_path, f".../{title}_images/{img.name}")
```

### Step 7: 生成索引

產生 `index.md`，包含所有筆記本、節、頁面的目錄樹與連結。

---

## 還原結果統計

| 項目 | 數量 |
|------|------|
| 匯出頁面 | 587 |
| 循序映射圖片 | 1,246 |
| 嵌入圖片 | 15 |
| 無快取檔案（僅文字） | 29 |
| 匯出總大小 | 1.4 GB |

### 按筆記本

| 筆記本 | 頁數 | 節數 |
|--------|------|------|
| Work | 413 | 22 |
| Personal | 160 | 30 |
| Evernote | 5 | 1 |
| Morton Rainey | 8 | 2 |
| 7rendMicro | 1 | 1 |

---

## 工具

完整的還原工具位於：

```
~/Desktop/OneNote-Export/extract_all.py
```

執行方式：
```bash
cd ~/Desktop/OneNote-Export
python3 extract_all.py
```

無需安裝額外套件，只依賴 Python 3 標準函式庫（sqlite3, struct, uuid, shutil）。

---

## 已知限制

1. **29 個頁面無快取**：這些頁面可能從未完整同步到本機，只能匯出 FTSI 中的文字
2. **表格格式遺失**：FTSI 的 PageElements 是平面文字，不保留表格/列表的結構
3. **圖片可能有少量錯誤歸屬**：循序配置模型在已刪除頁面附近可能出錯
4. **附件僅記錄檔名**：FTSI 只存附件的檔名（Jcid=393269），實際附件在 cache .bin 中但識別較困難
5. **字型/格式遺失**：雖然 page data 中包含字型資訊（Calibri 等），但提取完整的 rich text 格式需要完整解析 MS-ONESTORE 協議
6. **修訂歷史未提取**：快取中可能包含頁面的歷史版本，目前只取最新版本
