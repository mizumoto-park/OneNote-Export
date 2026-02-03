# OneNote Export 專案開發規範

## 環境設置（開發起手式）

### Python：使用 uv isolated environment

所有 Python 腳本必須在 uv 管理的虛擬環境中執行，不污染系統 Python。

```bash
# 專案初始化（只需一次）
cd /Volumes/myData-2T/Code/my-dev/OneNote-Export
uv init --python 3.12
uv venv

# 安裝依賴
uv add <package>

# 執行腳本（weasyprint 需要 DYLD_FALLBACK_LIBRARY_PATH）
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python scripts/extract_all.py

# 或先啟用 venv 再執行
source .venv/bin/activate
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
python scripts/extract_all.py
```

### Node.js：使用 nvm

所有 Node.js 操作必須先載入 nvm，使用專案指定版本。

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
nvm use 22   # 或 nvm use default

# 已安裝版本：v18.16.0, v20.19.6, v20.20.0, v22.21.1
```

如果專案需要鎖定 Node 版本，在專案根目錄建立 `.nvmrc`。

## 專案結構

```
OneNote-Export/
├── CLAUDE.md          # 本檔案：開發規範
├── scripts/           # 核心工具腳本
│   ├── extract_all.py # 主要匯出管線（FTSI → Markdown + 圖片）
│   └── archive/       # 歷史實驗腳本（29 個）
├── docs/              # OneNote cache 結構文件 + SVG 圖表
└── exported/          # 匯出的個人筆記（.gitignore 排除）
    ├── index.md       # 匯出總索引
    ├── Work/          # 413 頁
    ├── Personal/      # 160 頁
    ├── Evernote/      # 5 頁
    ├── Morton Rainey/   # 8 頁
    └── 7rendMicro/    # 1 頁
```

## 資料來源（唯讀）

- **FTSI SQLite**: `~/Library/Containers/com.microsoft.onenote.mac/Data/Library/Application Support/Microsoft User Data/OneNote/15.0-restore/FullTextSearchIndex/`
- **Cache .bin**: `~/Library/Containers/com.microsoft.onenote.mac/Data/Library/Application Support/Microsoft User Data/OneNote/15.0/cache/`

這些是 OneNote 本機快取，只能讀取不能修改。

## 慣例

- Python 標準版本：3.12（via uv）
- 新增 Python 依賴一律用 `uv add`，不用 `pip install`
- 腳本用 `uv run` 執行，確保在正確的虛擬環境中
- 匯出產物寫到 `exported/` 目錄下（已 .gitignore）
- 不寫到 ~/Desktop 或 /tmp
