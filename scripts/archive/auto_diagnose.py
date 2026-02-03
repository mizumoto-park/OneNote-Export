#!/usr/bin/env python3
"""
完全自動化診斷腳本 — 不需要任何用戶輸入
直接執行並記錄所有結果

執行: python3 auto_diagnose.py
"""

import subprocess
import time
import os
import json
from datetime import datetime

LOG_FILE = os.path.expanduser("~/Desktop/OneNote-Export/diagnose_log.txt")

def log(msg):
    """寫入日誌"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def osa(script, timeout=15, label=""):
    """執行 AppleScript 並記錄結果"""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        result = {
            "returncode": r.returncode,
            "stdout": r.stdout.strip()[:200] if r.stdout else "",
            "stderr": r.stderr.strip()[:200] if r.stderr else ""
        }
        log(f"  {label}: code={r.returncode}, out='{result['stdout'][:50]}...'")
        return r.stdout.strip() if r.returncode == 0 else None
    except subprocess.TimeoutExpired:
        log(f"  {label}: TIMEOUT")
        return None
    except Exception as e:
        log(f"  {label}: ERROR {e}")
        return None

def set_clipboard(text):
    """設定剪貼簿"""
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    process.communicate(text.encode('utf-8'))

def main():
    # 清空舊日誌
    with open(LOG_FILE, "w") as f:
        f.write(f"=== OneNote 自動診斷 ===\n開始時間: {datetime.now()}\n\n")

    log("【Step 1】啟動 OneNote...")
    osa('tell application "Microsoft OneNote" to activate', label="activate")
    time.sleep(1.5)

    log("【Step 2】取得視窗資訊...")
    windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window', label="windows")
    log(f"  視窗列表: {windows}")

    log("【Step 3】取得視窗標題...")
    title = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                return name of window 1
            end tell
        end tell
    ''', label="title")
    log(f"  視窗標題: {title}")

    log("【Step 4】點擊內容區域...")
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
    ''', label="click_content")
    time.sleep(0.5)

    log("【Step 5】列出檔案選單項目...")
    menu_items = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return name of every menu item of menu "檔案" of menu bar 1
                on error
                    return "ERROR"
                end try
            end tell
        end tell
    ''', label="menu_items")
    log(f"  選單項目: {menu_items[:300] if menu_items else 'None'}...")

    log("【Step 6】點擊「儲存為 PDF」...")
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                click menu item "儲存為 PDF" of menu "檔案" of menu bar 1
            end tell
        end tell
    ''', label="click_save_as_pdf")

    log("【Step 7】等待對話框...")
    dialog_found = False
    for i in range(15):
        time.sleep(0.5)
        windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window', label=f"wait_{i}")
        if windows and "另存新檔" in windows:
            log(f"  ✓ 對話框已開啟 (嘗試 {i+1})")
            dialog_found = True
            break

    if not dialog_found:
        log("  ✗ 對話框未開啟，終止")
        return

    log("【Step 8】讀取對話框中的檔名...")
    filename = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return value of text field "儲存為：" of splitter group 1 of window "另存新檔"
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''', label="read_filename")
    log(f"  檔名: {filename}")

    log("【Step 9】探索對話框 UI 結構...")

    # 列出 splitter group 內容
    ui_info = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    set sg to splitter group 1 of window "另存新檔"
                    set output to "Buttons: "
                    repeat with b in (every button of sg)
                        set output to output & (name of b) & ", "
                    end repeat
                    set output to output & " | TextFields: "
                    repeat with tf in (every text field of sg)
                        try
                            set output to output & (description of tf) & ", "
                        end try
                    end repeat
                    return output
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''', label="ui_structure")
    log(f"  UI 結構: {ui_info}")

    log("【Step 10】使用剪貼簿設定檔名...")
    test_filename = "AUTO_TEST.pdf"
    set_clipboard(test_filename)

    # 聚焦 + 全選 + 貼上
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    set focused of text field "儲存為：" of splitter group 1 of window "另存新檔" to true
                    delay 0.2
                    keystroke "a" using {command down}
                    delay 0.2
                    keystroke "v" using {command down}
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''', label="set_filename")
    time.sleep(0.5)

    # 驗證
    new_filename = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return value of text field "儲存為：" of splitter group 1 of window "另存新檔"
                on error
                    return ""
                end try
            end tell
        end tell
    ''', label="verify_filename")
    log(f"  新檔名: {new_filename}")

    if test_filename in str(new_filename):
        log("  ✓ 檔名設定成功")
    else:
        log("  ✗ 檔名設定失敗")

    log("【Step 11】開啟前往資料夾 (Cmd+Shift+G)...")
    osa('tell application "System Events" to keystroke "g" using {command down, shift down}', label="goto_folder")
    time.sleep(1.5)

    log("【Step 12】貼上路徑...")
    test_dir = os.path.expanduser("~/Desktop/OneNote-Export/_auto_test")
    os.makedirs(test_dir, exist_ok=True)
    set_clipboard(test_dir)

    osa('''
        tell application "System Events"
            keystroke "a" using {command down}
            delay 0.2
            keystroke "v" using {command down}
            delay 0.5
        end tell
    ''', label="paste_path")
    time.sleep(0.5)

    log("【Step 13】按 Return 確認路徑...")
    osa('tell application "System Events" to keystroke return', label="confirm_path")
    time.sleep(2)

    log("【Step 14】檢查當前路徑...")
    # 嘗試讀取路徑欄位或 popup
    current_path = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    -- 嘗試讀取路徑 popup
                    set sg to splitter group 1 of window "另存新檔"
                    set pops to every pop up button of sg
                    if (count of pops) > 0 then
                        return value of (item 1 of pops)
                    else
                        return "no popup"
                    end if
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''', label="check_path")
    log(f"  當前路徑: {current_path}")

    log("【Step 15】點擊儲存按鈕...")
    test_path = os.path.join(test_dir, test_filename)
    if os.path.exists(test_path):
        os.remove(test_path)

    save_result = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "儲存" of splitter group 1 of window "另存新檔"
                    return "OK"
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''', label="click_save")
    log(f"  儲存按鈕結果: {save_result}")

    time.sleep(3)

    log("【Step 16】處理可能的覆蓋確認...")
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取代" of sheet 1 of window 1
                on error
                    -- ignore
                end try
            end tell
        end tell
    ''', label="replace_confirm")
    time.sleep(1)

    log("【Step 17】檢查檔案...")
    if os.path.exists(test_path):
        size = os.path.getsize(test_path)
        log(f"  ✓ 成功！檔案已建立: {test_path}")
        log(f"  ✓ 檔案大小: {size} bytes")
    else:
        log(f"  ✗ 檔案未建立: {test_path}")
        if os.path.exists(test_dir):
            files = os.listdir(test_dir)
            log(f"  目錄內容: {files}")
        else:
            log(f"  目錄不存在")

    log("\n=== 診斷完成 ===")
    log(f"日誌已儲存到: {LOG_FILE}")

if __name__ == "__main__":
    main()
