#!/usr/bin/env python3
"""
詳細診斷腳本 — 逐步測試儲存對話框的每個操作
"""

import subprocess
import time
import os

def osa(script, timeout=15):
    """執行 AppleScript"""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout
        )
        print(f"  [OSA] returncode={r.returncode}")
        if r.stdout.strip():
            print(f"  [OSA] stdout: {r.stdout.strip()[:100]}")
        if r.stderr.strip():
            print(f"  [OSA] stderr: {r.stderr.strip()[:100]}")
        return r.stdout.strip() if r.returncode == 0 else None
    except subprocess.TimeoutExpired:
        print("  [OSA] TIMEOUT")
        return None

def set_clipboard(text):
    """設定剪貼簿"""
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    process.communicate(text.encode('utf-8'))
    print(f"  [CLIPBOARD] 已設定: {text}")

def get_clipboard():
    """取得剪貼簿"""
    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
    return result.stdout

def wait_enter(msg="按 Enter 繼續..."):
    input(f"\n{msg}")

print("""
╔══════════════════════════════════════════════════════════════╗
║       儲存對話框詳細診斷                                     ║
╚══════════════════════════════════════════════════════════════╝
""")

# Step 1: 啟動 OneNote
print("【步驟 1】啟動 OneNote...")
osa('tell application "Microsoft OneNote" to activate')
time.sleep(1)

# Step 2: 點擊內容區域
print("\n【步驟 2】點擊內容區域...")
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
time.sleep(0.5)

wait_enter("確認 OneNote 在前景。按 Enter 開啟儲存對話框...")

# Step 3: 開啟儲存對話框
print("\n【步驟 3】點擊「檔案 → 儲存為 PDF」...")
osa('''
    tell application "System Events"
        tell process "Microsoft OneNote"
            click menu item "儲存為 PDF" of menu "檔案" of menu bar 1
        end tell
    end tell
''')

print("  等待對話框...")
for i in range(15):
    time.sleep(0.5)
    windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window')
    if windows:
        print(f"  [{i+1}] 視窗: {windows}")
    if windows and "另存新檔" in windows:
        print("  ✓ 對話框已開啟")
        break
else:
    print("  ✗ 對話框未開啟，終止")
    exit(1)

# Step 4: 讀取檔名
print("\n【步驟 4】讀取對話框中的檔名...")
title = osa('''
    tell application "System Events"
        tell process "Microsoft OneNote"
            try
                return value of text field "儲存為：" of splitter group 1 of window "另存新檔"
            on error errMsg
                return "ERROR:" & errMsg
            end try
        end tell
    end tell
''')
print(f"  讀取到的檔名: {title}")

wait_enter("繼續測試設定檔名和路徑...")

# Step 5: 使用剪貼簿設定檔名
test_filename = "diagnostic_test.pdf"
print(f"\n【步驟 5】使用剪貼簿設定檔名為: {test_filename}")

set_clipboard(test_filename)
print("  聚焦檔名欄位...")
osa('''
    tell application "System Events"
        tell process "Microsoft OneNote"
            tell splitter group 1 of window "另存新檔"
                set focused of text field "儲存為：" to true
            end tell
        end tell
    end tell
''')
time.sleep(0.3)

print("  全選 (Cmd+A)...")
osa('''
    tell application "System Events"
        tell process "Microsoft OneNote"
            keystroke "a" using {command down}
        end tell
    end tell
''')
time.sleep(0.3)

print("  貼上 (Cmd+V)...")
osa('''
    tell application "System Events"
        tell process "Microsoft OneNote"
            keystroke "v" using {command down}
        end tell
    end tell
''')
time.sleep(0.5)

# 驗證
new_title = osa('''
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
print(f"  新檔名: {new_title}")
if test_filename in str(new_title):
    print("  ✓ 檔名設定成功！")
else:
    print("  ✗ 檔名設定失敗")

wait_enter("繼續測試前往資料夾...")

# Step 6: Cmd+Shift+G 前往資料夾
print("\n【步驟 6】開啟『前往資料夾』對話框 (Cmd+Shift+G)...")
osa('tell application "System Events" to keystroke "g" using {command down, shift down}')
time.sleep(1.5)

# 檢查是否有新的文字輸入欄位
print("  檢查『前往』對話框...")
# 嘗試列出 sheet
sheets = osa('''
    tell application "System Events"
        tell process "Microsoft OneNote"
            try
                return description of every sheet of window "另存新檔"
            on error
                return "no sheets"
            end try
        end tell
    end tell
''')
print(f"  Sheets: {sheets}")

# Step 7: 貼上路徑
test_dir = os.path.expanduser("~/Desktop/OneNote-Export/_diag_test")
print(f"\n【步驟 7】使用剪貼簿貼上路徑: {test_dir}")
set_clipboard(test_dir)

print("  全選 (Cmd+A)...")
osa('tell application "System Events" to keystroke "a" using {command down}')
time.sleep(0.2)

print("  貼上 (Cmd+V)...")
osa('tell application "System Events" to keystroke "v" using {command down}')
time.sleep(0.5)

wait_enter("請觀察對話框中的路徑是否正確，然後按 Enter...")

print("  按 Return 確認...")
osa('tell application "System Events" to keystroke return')
time.sleep(2)

# Step 8: 點擊儲存
print("\n【步驟 8】點擊儲存按鈕...")
os.makedirs(test_dir, exist_ok=True)
test_path = os.path.join(test_dir, test_filename)

# 移除舊檔
if os.path.exists(test_path):
    os.remove(test_path)

result = osa('''
    tell application "System Events"
        tell process "Microsoft OneNote"
            try
                click button "儲存" of splitter group 1 of window "另存新檔"
                return "clicked"
            on error errMsg
                return "error:" & errMsg
            end try
        end tell
    end tell
''')
print(f"  結果: {result}")

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

# Step 9: 檢查檔案
print("\n【步驟 9】檢查檔案是否建立...")
if os.path.exists(test_path):
    size = os.path.getsize(test_path)
    print(f"  ✓ 成功！檔案已建立: {test_path}")
    print(f"  ✓ 檔案大小: {size} bytes")
else:
    print(f"  ✗ 檔案未建立")
    print(f"  目錄內容: {os.listdir(test_dir) if os.path.exists(test_dir) else '目錄不存在'}")

print("\n" + "="*60)
print("診斷完成")
print("="*60)
