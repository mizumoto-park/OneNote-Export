# OneNote macOS 本機快取目錄結構

## Container 路徑

OneNote 作為 macOS sandboxed app，所有資料存放在：

```
~/Library/Containers/com.microsoft.onenote.mac/Data/Library/
```

## Application Support 結構

```
Application Support/Microsoft User Data/OneNote/
├── 15.0/                                ← 主要資料目錄
│   ├── cache/                           ← 二進位快取 (740 MB)
│   │   ├── header                       ← 72 bytes 快取元資料
│   │   ├── 00000000.bin                 ← 配置表 (380 KB)
│   │   ├── 00000001.bin                 ← 物件目錄 (380 KB)
│   │   ├── 00000002.bin                 ← Section-level 修訂存放區 (1.9 MB)
│   │   ├── 00000003.bin ~ 0000069L.bin  ← 頁面資料 + 圖片 (2,036 files)
│   │   └── (共 2,039 個 .bin 檔)
│   │
│   ├── FullTextSearchIndex/             ← 全文搜尋索引
│   │   ├── {3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}.db   ← Work (7,984 KB)
│   │   ├── {D62C1D86-38B0-0B4C-9A45-7259DDD20395}{51}.db   ← Personal (3,100 KB)
│   │   ├── {D62C1D86-38B0-0B4C-9A45-7259DDD20395}{10}.db   ← Morton Rainey (352 KB)
│   │   ├── {248E7F28-E3C6-AC43-A45F-8A5936C978E7}{10}.db   ← Evernote (216 KB)
│   │   └── {5497DFA7-B4A4-EC49-95F1-9B049B091C4E}{10}.db   ← 7rendMicro (164 KB)
│   │
│   ├── AccessibilityCheckerIndex/       ← 無障礙檢查索引
│   │   └── (同樣 5 個 .db 檔，GUID 相同)
│   │
│   ├── ServerListings/                  ← 伺服器快取
│   │   ├── 68A22224B54C82C4F80647B75C7EC6A4.onesrvcache
│   │   └── E337680823748F7C1DE79811CCC57B24.onesrvcache
│   │
│   └── Preferences.dat                  ← 標籤定義 (84 KB, binary)
│
├── 15.0-ori/                            ← 原始備份
│   └── (4 items)
│
└── 15.0-restore/                        ← 還原備份
    └── (9 items，結構同 15.0/)
```

## 其他相關目錄

```
~/Library/Containers/com.microsoft.onenote.mac/Data/Library/
├── Preferences/
│   └── com.microsoft.onenote.mac.plist  ← App 偏好設定 (binary plist)
│
├── Caches/
│   ├── Notifications/ONSharingNotifications/
│   │   └── settings.plist               ← 分享通知設定 (XML plist)
│   └── (其他: WebKit cache, telemetry)
│
├── Application Support/
│   ├── com.microsoft.Office.ServiceV2/  ← Office 服務
│   │   └── OfficeFileCache/
│   │       └── CentralTable.db          ← 空的 (0 MasterFile rows)
│   │
│   ├── FileUIKit/
│   │   └── FileUIKit.sqlite             ← CoreData: 3 NavigationTargets
│   │
│   └── com.microsoft.Office.Telemetry/
│       └── AriaStorage.db               ← 遙測資料 (5,277 events)
│
└── Saved Application State/             ← 視窗狀態
```

## cache/ 目錄命名規則

cache 目錄中的 .bin 檔案使用 **base-36 循序編號**：

```
字元集: 0-9, A-Z (共 36 個字元)

範例:
  00000000.bin  →  file ID 0
  00000009.bin  →  file ID 9
  0000000A.bin  →  file ID 10
  0000000Z.bin  →  file ID 35
  00000010.bin  →  file ID 36
  000004LC.bin  →  file ID 5952
  0000069L.bin  →  file ID 最大值 (約 8,000+)
```

新檔案按順序遞增分配 ID。這個特性是循序配置模型（圖片歸屬）的基礎。

## 特殊檔案說明

| 檔案 | 大小 | 用途 |
|------|------|------|
| `header` | 72 bytes | 快取版本、計數器等元資料 |
| `00000000.bin` | 380 KB | 配置表：追蹤哪些 file ID 已使用，包含部分圖片 file ID |
| `00000001.bin` | 380 KB | 物件目錄：GUID → file ID 的映射表 |
| `00000002.bin` | 1.9 MB | Section-level 修訂存放區，包含所有頁面標題與 GUID |
| `Preferences.dat` | 84 KB | 定義 OneNote 標籤 (To Do, Important, Question, etc.) |
