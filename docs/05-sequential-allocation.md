# 循序配置模型 — 圖片歸屬

## 問題

知道了「頁面 → page .bin」的對應之後，下一個問題是：「這個頁面的圖片存在哪些 .bin 檔案裡？」

OneNote 沒有明確的索引表來記錄「page X 的圖片是 file A, B, C」。我們需要從 cache 的配置模式中推導。

## 發現：循序配置

透過分析 2,039 個 .bin 檔案的排列順序，我們發現一個關鍵模式：

**OneNote 在寫入快取時，會將一個頁面和它的所有圖片連續配置在相鄰的 file ID 上。**

```
file ID 順序:
  ┌─────────────┐
  │ Page A data  │  000004LC.bin (DATA, 168KB)
  ├─────────────┤
  │ (gap)        │  000004LD.bin, 000004LE.bin 不存在或小型 data
  ├─────────────┤
  │ Image 1      │  000004LF.bin (PNG, 730x329, 14KB)
  ├─────────────┤
  │ Image 2      │  000004LG.bin (PNG, 681x340, 14KB)
  ├─────────────┤
  │ Page B data  │  000004LH.bin (DATA, 20KB) ← 下一個頁面的開始
  ├─────────────┤
  │ ...          │
  └─────────────┘
```

**規則**：從一個 page data 檔案往後掃描，遇到的所有 IMAGE 類型檔案（PNG/JPEG/GIF/PDF/ZIP）都屬於這個頁面，直到遇到下一個 DATA 檔案（≥4KB）為止。

## 驗證

### 案例 1: Historical CPB (2 張圖表)

```
000004LC.bin  →  Page Data (168 KB) — "Historical CPB"
000004LF.bin  →  PNG 730x329 — NTD per share 股價折線圖 ✓
000004LG.bin  →  PNG 681x340 — 獎金百分比柱狀圖 ✓
000004LH.bin  →  Page Data (20 KB) — "Black Duck Integration" (下一頁)
```

FTSI 紀錄了 1 張圖片（Jcid=393233，有 alt-text），但實際上有 2 張。FTSI 只索引有 alt-text 的圖片。

### 案例 2: 高圖片數頁面

```
Training/7rendMicro-ACE-202:   195 張圖片 (投影片截圖)
Training/When_parquet_meet_spark_sql: 120 張圖片
Training/7rendMicro-ACE-203:   82 張圖片
Training/7rendMicro-ACE-201:   80 張圖片
```

這些是訓練課程頁面，每張投影片都截圖嵌入，圖片數量合理。

## 統計結果

### 每頁圖片數分佈

| 圖片數 | 頁面數 | 說明 |
|--------|--------|------|
| 0 | 430 | 純文字頁面 |
| 1-2 | 81 | 有少量圖片的頁面 |
| 3-7 | 50 | 中等圖片數 |
| 8-19 | 16 | 較多圖片 |
| 20+ | 6 | 投影片/截圖密集頁面 |
| **合計** | **583** | |

### 匯總

| 項目 | 數量 |
|------|------|
| 循序映射的圖片總數 | 1,246 |
| 嵌入在 page data 中的大型 PNG | 15 |
| 有圖片的頁面 | 160 |
| FTSI 索引的圖片元素 | 879 |

循序映射（1,246）> FTSI 索引（879）的原因：
1. FTSI 只索引有 alt-text/OCR 文字的圖片
2. 快取中可能保留已刪除圖片
3. 縮圖/預覽圖也被計入

## 演算法

```python
def build_image_map(file_index, page_bins):
    """為每個頁面建立其所屬圖片的清單"""

    # 所有檔案按 file ID 排序
    all_sorted = sorted(file_index, key=lambda x: x['fid'])

    for page_bin in page_bins:
        if not page_bin['matched_page']:
            continue

        # 從這個頁面的 file ID 往後掃描
        idx = find_index(all_sorted, page_bin['fid'])

        images = []
        for j in range(idx + 1, len(all_sorted)):
            next_file = all_sorted[j]

            if next_file['type'] == 'IMAGE':
                # 圖片 → 歸屬於這個頁面
                images.append(next_file)
            elif next_file['is_page'] or (next_file['type'] == 'DATA' and next_file['size'] >= 4096):
                # 遇到下一個頁面或大型 data → 停止
                break

        page_bin['images'] = images
```

## 嵌入 PNG 的額外提取

部分頁面在 page data 中直接嵌入小型 PNG（通常是 UI 圖示）。我們額外提取大於 100x100 的嵌入 PNG：

```python
def extract_embedded_pngs(page_data):
    """從頁面二進位資料中提取嵌入的 PNG"""
    PNG_SIG = b'\x89PNG\r\n\x1a\n'
    PNG_END = b'IEND\xaeB\x60\x82'

    pngs = []
    idx = 0
    while True:
        pos = page_data.find(PNG_SIG, idx)
        if pos < 0:
            break
        end = page_data.find(PNG_END, pos)
        if end < 0:
            break
        end += 8  # 包含 IEND chunk
        png_data = page_data[pos:end]
        # 讀取 PNG 尺寸 (IHDR chunk)
        width = struct.unpack('>I', png_data[16:20])[0]
        height = struct.unpack('>I', png_data[20:24])[0]
        pngs.append({'data': png_data, 'width': width, 'height': height})
        idx = end

    # 只保留大型圖片 (排除 UI 圖示)
    return [p for p in pngs if p['width'] > 100 or p['height'] > 100]
```

## 限制與已知問題

1. **間隙中的小型 DATA 檔案**：頁面和圖片之間偶爾有小型（<4KB）的 data 檔案（修訂元資料），我們的演算法會跳過它們
2. **已刪除頁面的殘留圖片**：可能被錯誤歸屬給相鄰頁面
3. **共享圖片**：極少數情況下多個頁面引用同一張圖片，但在快取中只存一份
4. **修訂歷史**：同一頁面可能有多份快取，各自帶有不同版本的圖片
