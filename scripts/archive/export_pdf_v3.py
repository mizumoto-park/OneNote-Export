#!/usr/bin/env python3
"""
OneNote PDF Exporter v3 — 使用剪貼簿的穩定版本

解決問題：
  1. 使用剪貼簿貼上路徑（避免 keystroke 編碼問題）
  2. 翻頁改為手動（腳本等待用戶手動翻頁）

使用方式：
  python3 export_pdf_v3.py                  # 標準模式
  python3 export_pdf_v3.py --auto-advance   # 嘗試自動翻頁（可能失敗）
  python3 export_pdf_v3.py --count 10       # 只匯出 10 頁

流程：
  1. 腳本開啟儲存對話框並儲存 PDF
  2. 提示「請手動翻到下一頁，然後按 Enter」
  3. 重複直到你按 Ctrl+C 或完成指定數量
"""

import subprocess
import time
import os
import re
import sys
import sqlite3
import argparse

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

# ─── 剪貼簿操作 ──────────────────────────────────────────────────────────

def set_clipboard(text):
    """使用 pbcopy 設定剪貼簿內容"""
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    process.communicate(text.encode('utf-8'))

def get_clipboard():
    """使用 pbpaste 取得剪貼簿內容"""
    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
    return result.stdout

# ─── AppleScript ────────────────────────────────────────────────────────

def osa(script, timeout=30):
    """執行 AppleScript"""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except subprocess.TimeoutExpired:
        return None

def activate_onenote():
    """啟動 OneNote"""
    osa('tell application "Microsoft OneNote" to activate')
    time.sleep(0.5)

def get_window_title():
    """取得視窗標題"""
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
    return t or ""

def click_content():
    """點擊內容區域"""
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

# ─── 資料庫 ──────────────────────────────────────────────────────────────

def build_page_map():
    """建立標題 → (筆記本, 節) 對照"""
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
        except Exception:
            pass
    return pm

def sanitize(name):
    """清理檔名"""
    if not name:
        return "Untitled"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'[\s_]+', ' ', name).strip()
    return (name[:100].strip() if len(name) > 100 else name) or "Untitled"

# ─── 儲存對話框操作（使用剪貼簿）──────────────────────────────────────────

def open_save_dialog():
    """開啟儲存為 PDF 對話框"""
    click_content()
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                click menu item "儲存為 PDF" of menu "檔案" of menu bar 1
            end tell
        end tell
    ''')

    # 等待對話框
    for _ in range(20):
        time.sleep(0.5)
        windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window')
        if windows and "另存新檔" in windows:
            return True
    return False

def read_dialog_title():
    """讀取對話框中的檔名"""
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
    if t and t.lower().endswith(".pdf"):
        t = t[:-4]
    return t

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

def save_pdf_with_clipboard(target_dir, filename):
    """
    使用剪貼簿設定路徑並儲存
    """
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)

    # 1. 設定檔名：選取全部 → 用剪貼簿貼上
    set_clipboard(filename)
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                tell splitter group 1 of window "另存新檔"
                    set focused of text field "儲存為：" to true
                    delay 0.2
                    keystroke "a" using {command down}
                    delay 0.2
                    keystroke "v" using {command down}
                end tell
            end tell
        end tell
    ''')
    time.sleep(0.5)

    # 2. 開啟前往資料夾對話框
    osa('tell application "System Events" to keystroke "g" using {command down, shift down}')
    time.sleep(1.0)

    # 3. 用剪貼簿貼上路徑
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
    time.sleep(1.5)

    # 4. 點擊儲存
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
    time.sleep(2.5)

    # 5. 處理覆蓋對話框
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取代" of sheet 1 of window 1
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)

    return result == "OK" and os.path.exists(full_path)

# ─── 主程式 ──────────────────────────────────────────────────────────────

def export_one_page(page_map, title_seen, section_override=None):
    """
    匯出當前頁面
    Returns: (title, success, skip_reason)
    """
    if not open_save_dialog():
        return None, False, "對話框開啟失敗"

    title = read_dialog_title()
    if not title:
        cancel_dialog()
        return None, False, "無法讀取標題"

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
        return title, False, "已存在"

    # 儲存
    if save_pdf_with_clipboard(target_dir, pdf_fn):
        return title, True, None
    else:
        return title, False, "儲存失敗"

def main():
    parser = argparse.ArgumentParser(description="OneNote PDF Exporter v3")
    parser.add_argument("--section", help="覆蓋節名稱")
    parser.add_argument("--count", type=int, default=0, help="匯出頁數限制（0=無限）")
    parser.add_argument("--auto-advance", action="store_true", help="嘗試自動翻頁（可能失敗）")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════╗
║       OneNote PDF Exporter v3                                ║
║       使用剪貼簿的穩定版本                                   ║
╠══════════════════════════════════════════════════════════════╣
║  此版本需要你手動翻頁：                                      ║
║    1. 腳本會自動儲存當前頁面的 PDF                           ║
║    2. 儲存後會提示「請翻到下一頁」                           ║
║    3. 你在 OneNote 中翻頁後，按 Enter 繼續                   ║
║    4. 按 Ctrl+C 或 輸入 q 停止                               ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 載入資料
    page_map = build_page_map()
    print(f"頁面資料庫: {len(page_map)} 筆")
    print(f"輸出目錄: {EXPORT_DIR}")
    if args.section:
        print(f"節名覆蓋: {args.section}")
    if args.count:
        print(f"最多匯出: {args.count} 頁")
    print()

    input("準備好後按 Enter 開始...")

    activate_onenote()
    time.sleep(0.5)

    exported = 0
    skipped = 0
    errors = 0
    title_seen = {}

    try:
        page_num = 0
        while True:
            page_num += 1

            if args.count and page_num > args.count:
                print(f"\n已達到限制 ({args.count} 頁)")
                break

            print(f"\n--- 頁面 {page_num} ---")

            title, success, reason = export_one_page(page_map, title_seen, args.section)

            if title is None:
                print(f"  ❌ {reason}")
                errors += 1
                if errors > 3:
                    print("太多錯誤，停止")
                    break
            elif success:
                print(f"  ✅ 已儲存: {title}")
                exported += 1
            else:
                if reason == "已存在":
                    print(f"  ⏭ 跳過（已存在）: {title}")
                    skipped += 1
                else:
                    print(f"  ❌ {reason}: {title}")
                    errors += 1

            # 翻頁
            if args.auto_advance:
                print("  嘗試自動翻頁...")
                osa('tell application "System Events" to tell process "Microsoft OneNote" to key code 121 using {command down}')
                time.sleep(1.0)
            else:
                print()
                user_input = input("  👉 請在 OneNote 中翻到下一頁，然後按 Enter（輸入 q 停止）: ")
                if user_input.lower() == 'q':
                    break
                activate_onenote()
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\n已停止")

    print(f"""
{'='*60}
  完成！
  ✅ 儲存: {exported}
  ⏭ 跳過: {skipped}
  ❌ 錯誤: {errors}
  輸出: {EXPORT_DIR}
{'='*60}
    """)

if __name__ == "__main__":
    main()
