#!/usr/bin/env python3
"""
OneNote PDF Exporter v2 — 改良版半自動匯出程式

主要改進：
  1. 使用輪詢機制等待對話框，而非固定延遲
  2. 支援多種翻頁快捷鍵（自動偵測哪個有效）
  3. 增強錯誤處理和重試機制
  4. 改進頁面結束偵測（結合視窗標題變化）
  5. 詳細的除錯輸出

使用方式：
  python3 export_pdf_v2.py                  # 從目前頁面開始匯出
  python3 export_pdf_v2.py --section "AWS"  # 覆蓋節名稱
  python3 export_pdf_v2.py --no-advance     # 只匯出當前頁（不翻頁）
  python3 export_pdf_v2.py --test-nav       # 測試翻頁功能
  python3 export_pdf_v2.py --debug          # 顯示詳細除錯資訊

Prerequisites:
  1. 系統偏好設定 → 安全性與隱私 → 輔助使用 → 允許 Terminal/iTerm
  2. OneNote 必須已開啟並登入
  3. 將 OneNote 導覽到你想開始匯出的頁面
"""

import subprocess
import time
import os
import re
import sys
import sqlite3
import argparse
from datetime import datetime

# ─── 設定 ────────────────────────────────────────────────────────────────

EXPORT_DIR = os.path.expanduser("~/Desktop/OneNote-Export")

FTS_DIR = os.path.expanduser(
    "~/Library/Containers/com.microsoft.onenote.mac/Data/Library/"
    "Application Support/Microsoft User Data/OneNote/"
    "15.0-restore/FullTextSearchIndex"
)

DATABASES = {
    "{3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}.db": "Work",
    "{D62C1D86-38B0-0B4C-9A45-7259DDD20395}{51}.db": "Personal",
    "{D62C1D86-38B0-0B4C-9A45-7259DDD20395}{10}.db": "Morton Rainey 的筆記本",
    "{248E7F28-E3C6-AC43-A45F-8A5936C978E7}{10}.db": "Evernote",
    "{5497DFA7-B4A4-EC49-95F1-9B049B091C4E}{10}.db": "7rendMicro",
}

# 延遲設定（秒）
DELAY_AFTER_SAVE = 2.0
DELAY_AFTER_NAV = 1.0
DIALOG_TIMEOUT = 15  # 等待對話框的最長時間

DEBUG = False


# ─── AppleScript 執行器 ──────────────────────────────────────────────────

def osa(script, timeout=30):
    """執行 AppleScript 並返回結果"""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        if DEBUG:
            if r.returncode != 0 and r.stderr:
                print(f"  [DEBUG] AppleScript error: {r.stderr.strip()}")
        return r.stdout.strip() if r.returncode == 0 else None
    except subprocess.TimeoutExpired:
        print("  [WARN] AppleScript timeout")
        return None


def osa_check(script, timeout=5):
    """執行 AppleScript 但不關心結果，只檢查是否成功"""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


# ─── 頁面標題資料庫 ──────────────────────────────────────────────────────

def build_page_map():
    """從 SQLite 資料庫讀取頁面標題 → (筆記本, 節) 的對應"""
    pm = {}
    for db, nb in DATABASES.items():
        p = os.path.join(FTS_DIR, db)
        if not os.path.exists(p):
            continue
        try:
            conn = sqlite3.connect(p)
            c = conn.cursor()
            c.execute("SELECT GOID, Title FROM Entities WHERE Type=2")
            secs = {r[0]: r[1] for r in c.fetchall()}
            c.execute("SELECT Title, ParentGOID FROM Entities WHERE Type=1")
            for t, pg in c.fetchall():
                if t:
                    pm.setdefault(t.strip(), []).append((nb, secs.get(pg, "Unsorted")))
            conn.close()
        except Exception as e:
            print(f"  [WARN] 無法讀取資料庫 {db}: {e}")
    return pm


# ─── 檔名清理 ────────────────────────────────────────────────────────────

def sanitize(name):
    """清理檔名，移除非法字元"""
    if not name:
        return "Untitled"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'[\s_]+', ' ', name).strip()
    return (name[:100].strip() if len(name) > 100 else name) or "Untitled"


# ─── 視窗與對話框操作 ────────────────────────────────────────────────────

def get_window_names():
    """取得所有視窗名稱"""
    result = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window')
    return result if result else ""


def get_main_window_title():
    """取得主視窗標題（通常包含目前頁面名稱）"""
    t = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return name of window 1
                on error
                    return ""
                end try
            end tell
        end tell
    ''')
    if t:
        t = t.strip().lstrip('\u200f\u200e')
        # 移除 " - Microsoft OneNote" 後綴
        if " - " in t:
            t = t.rsplit(" - ", 1)[0].strip()
    return t or ""


def activate_onenote():
    """啟動並聚焦 OneNote"""
    osa('tell application "Microsoft OneNote" to activate')
    time.sleep(0.5)


def click_content_area():
    """點擊內容區域以確保焦點在頁面上"""
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                set frontmost to true
                delay 0.3
                set p to position of window 1
                set s to size of window 1
                click at {(item 1 of p) + ((item 1 of s) * 0.7), (item 2 of p) + ((item 2 of s) * 0.5)}
            end tell
        end tell
    ''')
    time.sleep(0.3)


# ─── 儲存對話框操作 ──────────────────────────────────────────────────────

def open_save_dialog():
    """開啟「儲存為 PDF」對話框"""
    click_content_area()

    # 嘗試點擊選單項目
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click menu item "儲存為 PDF" of menu "檔案" of menu bar 1
                on error
                    -- 嘗試英文版
                    try
                        click menu item "Save as PDF" of menu "File" of menu bar 1
                    end try
                end try
            end tell
        end tell
    ''')


def wait_for_dialog(dialog_name, timeout=DIALOG_TIMEOUT):
    """輪詢等待對話框出現"""
    start = time.time()
    while time.time() - start < timeout:
        windows = get_window_names()
        if dialog_name in windows:
            return True
        time.sleep(0.5)
    return False


def dialog_exists(dialog_name="另存新檔"):
    """檢查對話框是否存在"""
    windows = get_window_names()
    return dialog_name in windows


def read_dialog_title():
    """讀取對話框中的檔名"""
    # 嘗試繁體中文
    t = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return value of text field "儲存為：" of splitter group 1 of window "另存新檔"
                on error
                    return ""
                end try
            end tell
        end tell
    ''')

    # 嘗試英文
    if not t:
        t = osa('''
            tell application "System Events"
                tell process "Microsoft OneNote"
                    try
                        return value of text field "Save As:" of splitter group 1 of window "Save"
                    on error
                        return ""
                    end try
                end tell
            end tell
        ''')

    if t and t.lower().endswith(".pdf"):
        t = t[:-4]
    return t


def cancel_dialog():
    """取消對話框"""
    # 嘗試繁體中文
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取消" of splitter group 1 of window "另存新檔"
                on error
                    try
                        click button "Cancel" of splitter group 1 of window "Save"
                    end try
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)


def set_save_path(target_dir, filename):
    """設定儲存路徑和檔名"""
    os.makedirs(target_dir, exist_ok=True)
    ef = filename.replace('\\', '\\\\').replace('"', '\\"')
    ed = target_dir.replace('\\', '\\\\').replace('"', '\\"')

    # 設定檔名
    osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    tell splitter group 1 of window "另存新檔"
                        set focused of text field "儲存為：" to true
                        delay 0.2
                        keystroke "a" using {{command down}}
                        delay 0.2
                        keystroke "{ef}"
                    end tell
                on error
                    -- 嘗試英文版
                    tell splitter group 1 of window "Save"
                        set focused of text field "Save As:" to true
                        delay 0.2
                        keystroke "a" using {{command down}}
                        delay 0.2
                        keystroke "{ef}"
                    end tell
                end try
            end tell
        end tell
    ''')
    time.sleep(0.3)

    # 使用 Cmd+Shift+G 開啟前往目錄
    osa('tell application "System Events" to tell process "Microsoft OneNote" to keystroke "g" using {command down, shift down}')
    time.sleep(1.0)

    # 輸入路徑
    osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                keystroke "{ed}"
                delay 0.5
                keystroke return
            end tell
        end tell
    ''')
    time.sleep(1.5)


def click_save_button():
    """點擊儲存按鈕"""
    result = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "儲存" of splitter group 1 of window "另存新檔"
                    return "OK"
                on error
                    try
                        click button "Save" of splitter group 1 of window "Save"
                        return "OK"
                    on error errMsg
                        return "ERR:" & errMsg
                    end try
                end try
            end tell
        end tell
    ''')
    time.sleep(DELAY_AFTER_SAVE)

    # 處理覆蓋確認對話框
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取代" of sheet 1 of window 1
                on error
                    try
                        click button "Replace" of sheet 1 of window 1
                    on error
                        try
                            if exists button "取代" of window 1 then click button "取代" of window 1
                        end try
                    end try
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)

    return result is not None and "OK" in result


# ─── 頁面導覽 ────────────────────────────────────────────────────────────

# 各種可能的「下一頁」快捷鍵
NAV_METHODS = [
    # (名稱, key_code, modifiers)
    ("Cmd+PageDown", "key code 121 using {command down}"),
    ("Ctrl+Cmd+Down", "key code 125 using {control down, command down}"),
    ("Ctrl+PageDown", "key code 121 using {control down}"),
]

_working_nav_method = None


def test_navigation():
    """測試哪種翻頁方法有效"""
    global _working_nav_method

    print("\n測試翻頁功能...")
    print("請觀察 OneNote 是否翻到下一頁\n")

    activate_onenote()
    time.sleep(0.5)

    initial_title = get_main_window_title()
    print(f"目前頁面: {initial_title}\n")

    for name, keystroke in NAV_METHODS:
        print(f"  測試 {name}...")
        osa(f'tell application "System Events" to tell process "Microsoft OneNote" to {keystroke}')
        time.sleep(1.5)

        new_title = get_main_window_title()
        if new_title != initial_title:
            print(f"  ✓ {name} 有效！翻到: {new_title}")
            _working_nav_method = (name, keystroke)
            return True
        else:
            print(f"  ✗ {name} 無效")

    print("\n⚠ 所有翻頁方法都無效！請手動測試 OneNote 的翻頁快捷鍵。")
    return False


def advance_page():
    """翻到下一頁"""
    global _working_nav_method

    if _working_nav_method is None:
        # 預設使用 Cmd+PageDown
        keystroke = "key code 121 using {command down}"
    else:
        keystroke = _working_nav_method[1]

    osa(f'tell application "System Events" to tell process "Microsoft OneNote" to {keystroke}')
    time.sleep(DELAY_AFTER_NAV)


# ─── 匯出一個頁面 ────────────────────────────────────────────────────────

def export_current_page(page_map, title_seen, section_override=None, max_retries=3):
    """
    匯出當前頁面為 PDF

    Returns:
        (title, result) 其中 result 可能是:
        - True: 成功儲存
        - "SKIP": 已存在，跳過
        - False: 失敗
        - None: 對話框錯誤（title 也會是 None）
    """
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"    重試 {attempt}/{max_retries-1}...")
            activate_onenote()
            time.sleep(1)

        # 開啟儲存對話框
        open_save_dialog()

        # 等待對話框出現
        if not wait_for_dialog("另存新檔") and not wait_for_dialog("Save"):
            if attempt < max_retries - 1:
                continue
            return None, False

        # 讀取標題
        title = read_dialog_title()
        if not title:
            cancel_dialog()
            if attempt < max_retries - 1:
                continue
            return None, False

        break  # 成功開啟對話框並讀取標題
    else:
        return None, False

    # 找出對應的筆記本和節
    key = title.strip()
    title_seen[key] = title_seen.get(key, 0) + 1
    occ = title_seen[key]

    if section_override:
        nb_name = "Override"
        sec_name = section_override
        if key in page_map:
            nb_name = page_map[key][0][0]
    elif key in page_map:
        matches = page_map[key]
        idx = min(occ - 1, len(matches) - 1)
        nb_name, sec_name = matches[idx]
    else:
        nb_name = "Unknown"
        sec_name = "Unsorted"

    # 建立路徑
    safe_nb = sanitize(nb_name)
    safe_sec = sanitize(sec_name)
    safe_t = sanitize(title)
    target_dir = os.path.join(EXPORT_DIR, safe_nb, safe_sec)
    pdf_fn = f"{safe_t}.pdf"
    pdf_path = os.path.join(target_dir, pdf_fn)

    # 檢查是否已存在
    if os.path.exists(pdf_path):
        cancel_dialog()
        return title, "SKIP"

    # 設定路徑並儲存
    set_save_path(target_dir, pdf_fn)

    if click_save_button():
        return title, True
    else:
        return title, False


# ─── 主程式 ──────────────────────────────────────────────────────────────

def main():
    global DEBUG

    parser = argparse.ArgumentParser(description="OneNote PDF Exporter v2")
    parser.add_argument("--section", help="覆蓋節名稱")
    parser.add_argument("--no-advance", action="store_true", help="只匯出當前頁面，不翻頁")
    parser.add_argument("--test-nav", action="store_true", help="測試翻頁功能")
    parser.add_argument("--debug", action="store_true", help="顯示除錯資訊")
    parser.add_argument("--max-pages", type=int, default=500, help="最多匯出幾頁（預設 500）")
    args = parser.parse_args()

    DEBUG = args.debug

    print("=" * 60)
    print("  OneNote PDF Exporter v2")
    print("=" * 60)
    print()

    # 測試翻頁
    if args.test_nav:
        test_navigation()
        return

    # 載入頁面資料庫
    page_map = build_page_map()
    print(f"頁面資料庫: {len(page_map)} 筆標題")
    print(f"輸出目錄: {EXPORT_DIR}")

    if args.section:
        print(f"節名覆蓋: {args.section}")

    if args.no_advance:
        print("模式: 單頁（不自動翻頁）")
    else:
        print("模式: 連續匯出 + Cmd+PageDown 翻頁")

    print()
    print("按 Ctrl+C 停止")
    print("-" * 60)
    print()

    # 啟動 OneNote
    activate_onenote()
    time.sleep(1)

    # 統計
    exported = 0
    skipped = 0
    errors = 0
    title_seen = {}
    last_title = None
    last_window = None
    consec = 0

    try:
        for i in range(args.max_pages):
            # 取得目前視窗標題以輔助判斷
            current_window = get_main_window_title()

            title, result = export_current_page(page_map, title_seen, args.section)

            if title is None:
                print(f"  [{i+1}] ❌ 對話框錯誤")
                errors += 1
                if errors > 5:
                    print("\n太多錯誤，停止執行。")
                    break
                if not args.no_advance:
                    advance_page()
                continue

            # 檢查是否循環回到同一頁
            if title == last_title and current_window == last_window:
                consec += 1
                if consec >= 2:
                    print(f"  [{i+1}] 🔄 偵測到結束（重複: {title}）")
                    break
            else:
                consec = 0

            last_title = title
            last_window = current_window

            # 輸出結果
            if result == "SKIP":
                print(f"  [{i+1}] ⏭ 跳過 {title}")
                skipped += 1
            elif result:
                print(f"  [{i+1}] ✅ 儲存 {title}")
                exported += 1
            else:
                print(f"  [{i+1}] ❌ 失敗 {title}")
                errors += 1

            if args.no_advance:
                break

            advance_page()

    except KeyboardInterrupt:
        print("\n\n已停止。")

    # 最終統計
    print()
    print("=" * 60)
    print(f"  完成！")
    print(f"  ✅ 儲存: {exported}")
    print(f"  ⏭ 跳過: {skipped}")
    print(f"  ❌ 錯誤: {errors}")
    print(f"  輸出: {EXPORT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
