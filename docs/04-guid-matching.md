# GUID 位元組匹配機制

## 問題

FTSI 資料庫記錄了每個頁面的 metadata（標題、文字、GOID），但沒有直接記錄「這個頁面對應到 cache 目錄中的哪個 .bin 檔案」。我們需要一個方法來建立這個對應關係。

## 解決方案：GUID 位元組搜尋

每個 FTSI 頁面都有一個唯一的 GUID（如 `{1BDE8095-99F1-44A0-8B67-0438D3A02923}`）。這個 GUID 會以 **mixed-endian 位元組格式** 嵌入在對應的 page .bin 檔案中。

### Mixed-Endian GUID 格式

GUID 的二進位表示採用 Windows 的 mixed-endian 格式：

```
GUID 字串:  {1BDE8095-99F1-44A0-8B67-0438D3A02923}

分組:
  Data1: 1BDE8095  (4 bytes, little-endian)  →  95 80 DE 1B
  Data2: 99F1      (2 bytes, little-endian)  →  F1 99
  Data3: 44A0      (2 bytes, little-endian)  →  A0 44
  Data4: 8B67      (2 bytes, big-endian)     →  8B 67
  Data5: 0438D3A02923 (6 bytes, big-endian)  →  04 38 D3 A0 29 23

最終位元組: 95 80 DE 1B F1 99 A0 44 8B 67 04 38 D3 A0 29 23
```

### Python 實作

```python
import uuid

def guid_to_bytes_le(guid_str):
    """將 GUID 字串轉為 mixed-endian 位元組"""
    g = guid_str.strip('{}')
    return uuid.UUID(g).bytes_le

# 範例
guid = "{1BDE8095-99F1-44A0-8B67-0438D3A02923}"
guid_bytes = guid_to_bytes_le(guid)
# → b'\x95\x80\xde\x1b\xf1\x99\xa0\x44\x8b\x67\x04\x38\xd3\xa0\x29\x23'
```

### 匹配流程

```
對每個 cache .bin 檔案 (已識別為 Page Data):
    讀取整個檔案內容
    對每個 FTSI 頁面的 GUID:
        將 GUID 轉為 16 bytes mixed-endian
        在檔案中搜尋這 16 bytes
        如果找到 → 這個 .bin 就是這個頁面的快取檔案
```

### 匹配結果

| 項目 | 數量 |
|------|------|
| FTSI 頁面總數 | 587 |
| Page .bin 檔案總數 | 592 |
| 成功匹配 | 558 |
| **匹配率** | **94.9%** |
| 未匹配的 FTSI 頁面 | 29 |
| 未匹配的 .bin 檔案 | 34 |

### 未匹配的原因

**29 個未匹配的 FTSI 頁面**：
- 頁面已從快取中清除（過舊或手動清理）
- 頁面從未完整同步到本機

**34 個未匹配的 .bin 檔案**：
- 已刪除頁面的殘留快取
- FTSI 索引尚未更新的新頁面
- 舊版本的頁面快取（OneNote 保留修訂歷史）

### 多重匹配處理

少數頁面（4 個）匹配到多個 .bin 檔案，這是因為：
- OneNote 保留頁面的多個修訂版本
- 同一頁面可能有新舊兩份快取

處理策略：**取 file ID 最大的**（即最新的版本）。

---

## 替代方案比較

我們嘗試過多種匹配方式：

| 方法 | 匹配率 | 說明 |
|------|--------|------|
| **GUID 位元組搜尋** | **94.9%** | 最佳方案 |
| 標題文字匹配 | 65% | CJK 標題辨識不完整，重複標題無法區分 |
| GOID 位元組搜尋 | +0% | GOID 中的 GUID 部分是筆記本/節的，不是頁面的 |
| ContentRID 匹配 | 未測試 | RID 可能因修訂而改變 |
| MD5/SHA 雜湊比對 | 0% | 二進位格式與純文字格式不同，無法直接比對 |

---

## GUID 在 .bin 檔案中的位置

以 "Historical CPB" 頁面為例：

```
Page .bin: 000004LC.bin (167,936 bytes)
Page GUID: {1BDE8095-99F1-44A0-8B67-0438D3A02923}

GUID bytes found at offset 0x0EE0:
  ...64d1329e85b88a567a9dd87de6e3b900
  [9580de1bf199a0448b670438d3a02923]    ← 頁面 GUID (16 bytes)
  74237b021c8e7a00...
```

GUID 通常出現在檔案前半部的 metadata 區域（偏移量 < 0x2000），被其他 GUID 包圍（節 GUID、筆記本 GUID、關聯物件的 GUID）。

---

## 圖片 GOID 的存在

Page .bin 中也包含其所屬圖片的 GOID。例如：

```
Image GOID: {9A7B2374-C314-9F78-86E1-B24FB8C43B61}{87}
  ↓ GUID 部分轉為 mixed-endian
Found at offset 0x0EE0 in 000004LC.bin

也在附近找到內部檔名:
  "Untitled picture.png"  (UTF-16LE)
  "chart2991374945314014811.png"  (UTF-16LE)
```

但是，**圖片 GOID 不直接包含圖片的 file ID**，所以我們需要另一個機制來找到圖片檔案——這就是循序配置模型。
