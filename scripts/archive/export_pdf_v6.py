#!/usr/bin/env python3
"""
OneNote PDF Exporter v6 — 使用 select 屬性選取文字

關鍵修正：不使用 Cmd+A，改用 AppleScript 的 select 功能
"""

import subprocess
import time
import os
import re
import sqlite3
import argparse
from datetime import datetime

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

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def osa(script, timeout=20):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except:
        return None

def set_clipboard(text):
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    process.communicate(text.encode('utf-8'))

def ensure_onenote():
    osa('tell application "Microsoft OneNote" to activate')
    time.sleep(0.5)
    title = osa('tell application "System Events" to tell process "Microsoft OneNote" to name of window 1')
    return bool(title)

def open_save_dialog():
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                set frontmost to true
                delay 0.3
                set p to position of window 1
                set s to size of window 1
                click at {(item 1 of p) + ((item 1 of s) * 0.6), (item 2 of p) + ((item 2 of s) * 0.5)}
            end tell
        end tell
    ''')
    time.sleep(0.5)

    osa('tell application "System Events" to tell process "Microsoft OneNote" to click menu item "儲存為 PDF" of menu "檔案" of menu bar 1')

    for _ in range(20):
        time.sleep(0.5)
        windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to name of every window')
        if windows and "另存新檔" in windows:
            return True
    return False

def read_title():
    title = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                return value of text field "儲存為：" of splitter group 1 of window "另存新檔"
            end tell
        end tell
    ''')
    if title and title.lower().endswith(".pdf"):
        title = title[:-4]
    return title

def cancel_dialog():
    osa('tell application "System Events" to tell process "Microsoft OneNote" to click button "取消" of splitter group 1 of window "另存新檔"')
    time.sleep(0.5)

def save_pdf(target_dir, filename):
    """
    儲存 PDF — 直接設定欄位值
    """
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)

    # 方法：直接設定 text field 的 value（最可靠）
    escaped_filename = filename.replace('"', '\\"')
    result = osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    set value of text field "儲存為：" of splitter group 1 of window "另存新檔" to "{escaped_filename}"
                    return "OK"
                on error errMsg
                    return "ERR:" & errMsg
                end try
            end tell
        end tell
    ''')

    if result and "OK" in result:
        log("  ✓ 檔名設定成功（直接設定 value）")
    else:
        # 備用方案：先刪除再貼上
        log(f"  直接設定失敗，使用備用方案: {result}")
        # 聚焦欄位
        osa('''
            tell application "System Events"
                tell process "Microsoft OneNote"
                    set focused of text field "儲存為：" of splitter group 1 of window "另存新檔" to true
                    delay 0.3
                end tell
            end tell
        ''')
        time.sleep(0.3)

        # 按 Home 然後 Shift+End 選取全部（不用 Cmd+A）
        osa('''
            tell application "System Events"
                key code 115 -- Home
                delay 0.2
                key code 119 using {shift down} -- Shift+End
                delay 0.2
            end tell
        ''')
        time.sleep(0.2)

        # 貼上
        set_clipboard(filename)
        time.sleep(0.1)
        osa('tell application "System Events" to keystroke "v" using {command down}')

    time.sleep(0.5)

    # 開啟前往資料夾
    osa('tell application "System Events" to keystroke "g" using {command down, shift down}')
    time.sleep(1.5)

    # 直接設定路徑欄位的值
    escaped_dir = target_dir.replace('"', '\\"')
    path_result = osa(f'''
        tell application "System Events"
            -- 嘗試找到前往資料夾的文字欄位（通常是 combo box 或 text field）
            try
                -- 方法1: 嘗試設定 combo box
                set value of combo box 1 of sheet 1 of window "另存新檔" of process "Microsoft OneNote" to "{escaped_dir}"
                return "COMBO"
            on error
                try
                    -- 方法2: 嘗試設定 text field
                    set value of text field 1 of sheet 1 of window "另存新檔" of process "Microsoft OneNote" to "{escaped_dir}"
                    return "TEXTFIELD"
                on error
                    return "NONE"
                end try
            end try
        end tell
    ''')

    if path_result in ["COMBO", "TEXTFIELD"]:
        log(f"  ✓ 路徑設定成功（{path_result}）")
    else:
        log("  使用剪貼簿設定路徑...")
        set_clipboard(target_dir)
        time.sleep(0.1)
        osa('''
            tell application "System Events"
                key code 115 -- Home
                delay 0.1
                key code 119 using {shift down} -- Shift+End
                delay 0.1
                keystroke "v" using {command down}
            end tell
        ''')

    time.sleep(0.5)
    osa('tell application "System Events" to keystroke return')
    time.sleep(2)

    # 點擊儲存
    osa('tell application "System Events" to tell process "Microsoft OneNote" to click button "儲存" of splitter group 1 of window "另存新檔"')
    time.sleep(3)

    # 處理覆蓋
    osa('tell application "System Events" to tell process "Microsoft OneNote" to try\nclick button "取代" of sheet 1 of window 1\nend try')
    time.sleep(1)

    return os.path.exists(full_path)

def build_page_map():
    pm = {}
    for db, nb in DATABASES.items():
        p = os.path.join(FTS_DIR, db)
        if not os.path.exists(p): continue
        try:
            conn = sqlite3.connect(p)
            c = conn.cursor()
            c.execute("SELECT GOID, Title FROM Entities WHERE Type=2")
            secs = {r[0]: r[1] for r in c.fetchall()}
            c.execute("SELECT Title, ParentGOID FROM Entities WHERE Type=1")
            for t, pg in c.fetchall():
                if t: pm.setdefault(t.strip(), []).append((nb, secs.get(pg, "Unsorted")))
            conn.close()
        except: pass
    return pm

def sanitize(name):
    if not name: return "Untitled"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'[\s_]+', ' ', name).strip()
    return (name[:100].strip() if len(name) > 100 else name) or "Untitled"

def export_one(page_map, title_seen, section_override=None):
    if not open_save_dialog():
        return None, False, "對話框失敗"

    title = read_title()
    if not title:
        cancel_dialog()
        return None, False, "無法讀取標題"

    log(f"  標題: {title}")

    key = title.strip()
    title_seen[key] = title_seen.get(key, 0) + 1
    occ = title_seen[key]

    if section_override:
        nb_name = page_map.get(key, [("Override", section_override)])[0][0]
        sec_name = section_override
    elif key in page_map:
        idx = min(occ - 1, len(page_map[key]) - 1)
        nb_name, sec_name = page_map[key][idx]
    else:
        nb_name, sec_name = "Unknown", "Unsorted"

    target_dir = os.path.join(EXPORT_DIR, sanitize(nb_name), sanitize(sec_name))
    pdf_fn = f"{sanitize(title)}.pdf"
    pdf_path = os.path.join(target_dir, pdf_fn)

    if os.path.exists(pdf_path):
        cancel_dialog()
        return title, False, "已存在"

    log(f"  目標: {pdf_fn}")

    if save_pdf(target_dir, pdf_fn):
        return title, True, None
    return title, False, "儲存失敗"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", help="覆蓋節名稱")
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test: args.count = 1

    print("\n=== OneNote PDF Exporter v6 ===\n")

    if not ensure_onenote():
        log("❌ OneNote 視窗未開啟")
        return

    page_map = build_page_map()
    log(f"頁面資料庫: {len(page_map)} 筆")

    if not args.test:
        input("按 Enter 開始...")

    exported, skipped, errors = 0, 0, 0
    title_seen = {}

    try:
        for i in range(args.count or 999):
            print(f"\n--- 頁面 {i+1} ---")
            ensure_onenote()

            title, ok, reason = export_one(page_map, title_seen, args.section)

            if ok:
                log("  ✅ 已儲存")
                exported += 1
            elif reason == "已存在":
                log("  ⏭ 跳過")
                skipped += 1
            else:
                log(f"  ❌ {reason}")
                errors += 1

            if args.count and i + 1 >= args.count:
                break

            if not args.test:
                if input("\n  翻頁後按 Enter（q 停止）: ").lower() == 'q':
                    break

    except KeyboardInterrupt:
        print("\n停止")

    print(f"\n完成！ 儲存:{exported} 跳過:{skipped} 錯誤:{errors}")

if __name__ == "__main__":
    main()
