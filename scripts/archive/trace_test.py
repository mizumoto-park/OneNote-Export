#!/usr/bin/env python3
"""
精簡測試腳本 — 追蹤 'a' 字元來源
"""

import subprocess
import time
import os

def osa(script, timeout=15):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        print(f"  [OSA] code={r.returncode}")
        if r.stderr.strip():
            print(f"  [OSA] stderr: {r.stderr.strip()[:100]}")
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception as e:
        print(f"  [OSA] error: {e}")
        return None

def set_clipboard(text):
    p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    p.communicate(text.encode('utf-8'))

# 測試目錄
test_dir = os.path.expanduser("~/Desktop/OneNote-Export/_trace_test")
test_filename = "TRACE_TEST.pdf"
os.makedirs(test_dir, exist_ok=True)

# 清理
test_path = os.path.join(test_dir, test_filename)
if os.path.exists(test_path):
    os.remove(test_path)

print("\n=== 追蹤 'a' 字元來源 ===\n")

print("【1】啟動 OneNote...")
osa('tell application "Microsoft OneNote" to activate')
time.sleep(1)

print("\n【2】開啟儲存對話框...")
osa('tell application "System Events" to tell process "Microsoft OneNote" to click menu item "儲存為 PDF" of menu "檔案" of menu bar 1')
time.sleep(2)

# 等待對話框
for i in range(10):
    time.sleep(0.5)
    windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to name of every window')
    if "另存新檔" in str(windows):
        print("  ✓ 對話框開啟")
        break

print("\n【3】讀取原始檔名...")
orig = osa('tell application "System Events" to tell process "Microsoft OneNote" to value of text field "儲存為：" of splitter group 1 of window "另存新檔"')
print(f"  原始檔名: {orig}")

print("\n【4】直接設定檔名（不使用任何快捷鍵）...")
osa(f'''
    tell application "System Events"
        tell process "Microsoft OneNote"
            set value of text field "儲存為：" of splitter group 1 of window "另存新檔" to "{test_filename}"
        end tell
    end tell
''')
time.sleep(0.5)

new_name = osa('tell application "System Events" to tell process "Microsoft OneNote" to value of text field "儲存為：" of splitter group 1 of window "另存新檔"')
print(f"  新檔名: {new_name}")

print("\n【5】開啟前往資料夾 (Cmd+Shift+G)...")
osa('tell application "System Events" to keystroke "g" using {command down, shift down}')
time.sleep(2)

print("\n【6】直接設定路徑（不使用任何快捷鍵）...")
# 嘗試直接設定 combo box 或 text field
path_set = osa(f'''
    tell application "System Events"
        try
            set value of combo box 1 of sheet 1 of window "另存新檔" of process "Microsoft OneNote" to "{test_dir}"
            return "COMBO"
        on error
            try
                set value of text field 1 of sheet 1 of window "另存新檔" of process "Microsoft OneNote" to "{test_dir}"
                return "TEXTFIELD"
            on error
                return "FAILED"
            end try
        end try
    end tell
''')
print(f"  路徑設定結果: {path_set}")

if path_set == "FAILED":
    print("  使用剪貼簿備用方案...")
    set_clipboard(test_dir)
    time.sleep(0.2)
    # Cmd+Shift+G 後，欄位通常已被選取，直接貼上
    osa('tell application "System Events" to keystroke "v" using {command down}')
    time.sleep(0.5)

print("\n【7】確認路徑（按 Return）...")
osa('tell application "System Events" to keystroke return')
time.sleep(2)

print("\n【7.5】再次檢查檔名欄位...")
final_name = osa('tell application "System Events" to tell process "Microsoft OneNote" to value of text field "儲存為：" of splitter group 1 of window "另存新檔"')
print(f"  儲存前的檔名: {final_name}")

print("\n【8】點擊儲存...")
osa('tell application "System Events" to tell process "Microsoft OneNote" to click button "儲存" of splitter group 1 of window "另存新檔"')
time.sleep(3)

# 處理可能的覆蓋
osa('tell application "System Events" to tell process "Microsoft OneNote" to try\nclick button "取代" of sheet 1 of window 1\nend try')
time.sleep(1)

print("\n【9】檢查結果...")
# 列出目錄內容
files = os.listdir(test_dir)
print(f"  目錄內容: {files}")

if test_filename in files:
    print(f"  ✅ 成功！檔名正確")
elif any('TRACE_TEST' in f for f in files):
    actual = [f for f in files if 'TRACE_TEST' in f][0]
    print(f"  ⚠ 檔名被修改: {test_filename} → {actual}")
    # 分析差異
    if actual != test_filename:
        print(f"  差異分析:")
        for i, (c1, c2) in enumerate(zip(test_filename.ljust(len(actual)), actual)):
            if c1 != c2:
                print(f"    位置 {i}: 期望 '{c1}' 實際 '{c2}'")
else:
    print(f"  ❌ 檔案未建立")

print("\n=== 測試完成 ===")
