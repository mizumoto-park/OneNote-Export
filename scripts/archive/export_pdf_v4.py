#!/usr/bin/env python3
"""
OneNote PDF Exporter v4 — 最穩定版本

改進：
1. 強制 OneNote 視窗可見並置前
2. 使用鍵盤快捷鍵開啟儲存對話框
3. 更長的等待時間
4. 完整的錯誤處理
"""

import subprocess
import time
import os
import re
import sqlite3
import argparse
from datetime import datetime

EXPORT_DIR = os.path.expanduser("~/Desktop/OneNote-Export")
LOG_FILE = os.path.join(EXPORT_DIR, "export_log.txt")

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

def log(msg, print_it=True):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    if print_it:
        print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def osa(script, timeout=20):
    """執行 AppleScript"""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except:
        return None

def set_clipboard(text):
    """設定剪貼簿"""
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    process.communicate(text.encode('utf-8'))

def ensure_onenote_visible():
    """確保 OneNote 視窗可見並在前景"""
    # 啟動應用程式
    osa('tell application "Microsoft OneNote" to activate')
    time.sleep(0.5)

    # 確保視窗不是最小化的
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    -- 取消最小化
                    set miniaturized of every window to false
                    -- 設為前景
                    set frontmost to true
                    -- 確保有視窗
                    if (count of windows) = 0 then
                        -- 嘗試開啟新視窗
                        keystroke "n" using {command down}
                    end if
                end try
            end tell
        end tell
    ''')
    time.sleep(1)

    # 驗證
    title = osa('''
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

    return title and len(title) > 0

def open_save_dialog_via_menu():
    """透過選單開啟儲存對話框"""
    # 點擊內容區確保焦點
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                set frontmost to true
                delay 0.5
                try
                    set p to position of window 1
                    set s to size of window 1
                    click at {(item 1 of p) + ((item 1 of s) * 0.6), (item 2 of p) + ((item 2 of s) * 0.5)}
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)

    # 透過選單開啟
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click menu item "儲存為 PDF" of menu "檔案" of menu bar 1
                end try
            end tell
        end tell
    ''')

    # 等待對話框
    for i in range(20):
        time.sleep(0.5)
        windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to name of every window')
        if windows and "另存新檔" in windows:
            return True
    return False

def read_title_from_dialog():
    """從對話框讀取標題"""
    title = osa('''
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
    if title and title.lower().endswith(".pdf"):
        title = title[:-4]
    return title

def cancel_dialog():
    """取消對話框"""
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取消" of splitter group 1 of window "另存新檔"
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)

def save_with_path(target_dir, filename):
    """使用剪貼簿設定路徑並儲存"""
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)

    # 設定檔名（使用剪貼簿）
    set_clipboard(filename)
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    tell splitter group 1 of window "另存新檔"
                        set focused of text field "儲存為：" to true
                        delay 0.3
                    end tell
                    keystroke "a" using {command down}
                    delay 0.2
                    keystroke "v" using {command down}
                    delay 0.3
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)

    # 開啟「前往資料夾」對話框
    osa('tell application "System Events" to keystroke "g" using {command down, shift down}')
    time.sleep(1.5)

    # 貼上路徑
    set_clipboard(target_dir)
    osa('''
        tell application "System Events"
            keystroke "a" using {command down}
            delay 0.2
            keystroke "v" using {command down}
            delay 0.5
            keystroke return
        end tell
    ''')
    time.sleep(2)

    # 點擊儲存
    result = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "儲存" of splitter group 1 of window "另存新檔"
                    return "OK"
                on error
                    return "ERR"
                end try
            end tell
        end tell
    ''')
    time.sleep(3)

    # 處理覆蓋確認
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取代" of sheet 1 of window 1
                end try
            end tell
        end tell
    ''')
    time.sleep(1)

    return os.path.exists(full_path)

def build_page_map():
    """建立頁面標題對照表"""
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
        except:
            pass
    return pm

def sanitize(name):
    """清理檔名"""
    if not name:
        return "Untitled"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'[\s_]+', ' ', name).strip()
    return (name[:100].strip() if len(name) > 100 else name) or "Untitled"

def export_one_page(page_map, title_seen, section_override=None):
    """匯出一頁"""
    log("開啟儲存對話框...")
    if not open_save_dialog_via_menu():
        log("  ❌ 對話框開啟失敗")
        return None, False, "對話框失敗"

    title = read_title_from_dialog()
    if not title:
        cancel_dialog()
        log("  ❌ 無法讀取標題")
        return None, False, "無法讀取標題"

    log(f"  標題: {title}")

    # 查找路徑
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
        log(f"  ⏭ 已存在")
        return title, False, "已存在"

    log(f"  目標: {pdf_path}")

    # 儲存
    if save_with_path(target_dir, pdf_fn):
        log(f"  ✅ 成功")
        return title, True, None
    else:
        log(f"  ❌ 儲存失敗")
        return title, False, "儲存失敗"

def main():
    parser = argparse.ArgumentParser(description="OneNote PDF Exporter v4")
    parser.add_argument("--section", help="覆蓋節名稱")
    parser.add_argument("--count", type=int, default=0, help="匯出頁數限制")
    args = parser.parse_args()

    # 初始化日誌
    with open(LOG_FILE, "w") as f:
        f.write(f"=== OneNote PDF Exporter v4 ===\n")
        f.write(f"開始時間: {datetime.now()}\n\n")

    print("""
╔══════════════════════════════════════════════════════════════╗
║       OneNote PDF Exporter v4                                ║
║       穩定版 — 每頁需手動翻頁                                ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 確保 OneNote 可見
    log("確保 OneNote 視窗可見...")
    if not ensure_onenote_visible():
        log("❌ 無法找到 OneNote 視窗！請確認 OneNote 已開啟並顯示內容。")
        return

    log("✅ OneNote 視窗已確認")

    # 載入資料
    page_map = build_page_map()
    log(f"頁面資料庫: {len(page_map)} 筆")

    if args.section:
        log(f"節名覆蓋: {args.section}")
    if args.count:
        log(f"最多匯出: {args.count} 頁")

    print("\n" + "="*60)
    print("  流程：腳本儲存 → 你手動翻頁 → 按 Enter → 重複")
    print("  按 Ctrl+C 或輸入 q 停止")
    print("="*60 + "\n")

    input("準備好後按 Enter 開始...")

    exported = 0
    skipped = 0
    errors = 0
    title_seen = {}

    try:
        page_num = 0
        while True:
            page_num += 1

            if args.count and page_num > args.count:
                log(f"\n已達到限制 ({args.count} 頁)")
                break

            print(f"\n--- 頁面 {page_num} ---")

            # 確保 OneNote 在前景
            ensure_onenote_visible()
            time.sleep(0.5)

            title, success, reason = export_one_page(page_map, title_seen, args.section)

            if success:
                exported += 1
            elif reason == "已存在":
                skipped += 1
            else:
                errors += 1
                if errors > 5:
                    log("太多錯誤，停止")
                    break

            # 提示翻頁
            print()
            user = input("  👉 請在 OneNote 中翻到下一頁，然後按 Enter（q 停止）: ")
            if user.lower() == 'q':
                break

    except KeyboardInterrupt:
        print("\n已停止")

    print(f"""
{'='*60}
  完成！
  ✅ 儲存: {exported}
  ⏭ 跳過: {skipped}
  ❌ 錯誤: {errors}
  日誌: {LOG_FILE}
{'='*60}
    """)

if __name__ == "__main__":
    main()
