# OneNote Export 工具程式

## 核心工具（保留）

### `extract_all.py` — 主要還原工具 (最終版)

完整的 OneNote 本機快取還原工具，整合所有步驟：

1. 從 FTSI SQLite 載入 587 頁的 Notebook/Section/Page 階層
2. 分類 2,039 個 cache .bin 檔案（IMAGE vs DATA）
3. GUID 位元組匹配：FTSI 頁面 ↔ cache .bin（94.9% 命中率）
4. 循序配置映射：自動歸屬 1,246 張圖片到所屬頁面
5. 提取嵌入 PNG（>100x100）
6. 匯出 .md + 圖片到 Notebook/Section/ 目錄
7. 產生 index.md 目錄索引

```bash
python3 extract_all.py
```

無外部依賴，僅需 Python 3 標準函式庫。

### `export_markdown.py` — 早期版本：純文字匯出

從 FTSI SQLite 匯出 Markdown（不含圖片）。這是 `extract_all.py` 的前身，僅做 Step 1 + 文字匯出。

### `extract_images.py` — 早期版本：暴力圖片提取

掃描所有 .bin 檔的 magic bytes，切割出所有 PNG/JPEG/GIF/PDF/BMP 到 `_attachments/`。不區分圖片歸屬。已被 `extract_all.py` 的循序配置取代。

### `generate_index.py` — 早期版本：索引產生

從已匯出的目錄結構產生 index.md。已整合進 `extract_all.py`。

## 封存工具（archive/）

`archive/` 包含 29 個開發過程中的實驗性程式：

### PDF UI 自動化匯出（失敗）

嘗試透過 AppleScript + Accessibility API 控制 OneNote 自動匯出 PDF：

- `export_pdf.py` — 初版完整自動化（notebook/section 切換失敗）
- `export_pdf_v2.py` ~ `export_pdf_v11.py` — 多次迭代嘗試修復
- `export_pdf_simple.py` — 簡化版（放棄 notebook 切換，僅 Cmd+PageDown）
- `export_pdf_blind.py` — 盲操作版
- `export_pdf_applescript.sh` — 純 AppleScript 版

失敗原因：OneNote Mac 的 sidebar UI 元素路徑在操作後會改變，無法穩定定位。

### UI 偵錯工具

開發 PDF 自動化時用來分析 OneNote 的 Accessibility 樹：

- `inspect_ui.py`, `hunt_ui.py`, `find_ui_lists.py` — 搜尋 UI 元素
- `check_group5.py`, `inspect_child5.py`, `search_every_group.py` — 深度搜尋
- `debug_dialog.py`, `inspect_dialog.py` — Save As 對話框偵錯
- `debug_title.py`, `get_geometry.py` — 視窗標題/位置
- `auto_diagnose.py`, `diagnose_save.py` — 自動診斷
- `test_onenote.py`, `test_click.py`, `trace_test.py` — 操作測試
- `find_page_list.py` — 嘗試定位頁面列表
