#!/usr/bin/env python3
"""
OneNote PDF Export — 互動式測試腳本

用途：逐步測試每個核心功能，找出什麼可用、什麼不可用

使用方式：
  python3 test_onenote.py

前置條件：
  1. OneNote 必須已開啟
  2. 導航到任意一個有內容的頁面
  3. Terminal 需有輔助使用權限
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
        if r.returncode != 0:
            return f"[ERROR] {r.stderr.strip()}"
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"

def wait_enter(msg=""):
    input(f"\n{msg}按 Enter 繼續...")

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(success, msg):
    icon = "✅" if success else "❌"
    print(f"  {icon} {msg}")

# ─── 測試項目 ─────────────────────────────────────────────────────────

def test_1_activate():
    """測試 1: 啟動 OneNote"""
    print_header("測試 1: 啟動並聚焦 OneNote")

    result = osa('tell application "Microsoft OneNote" to activate')
    time.sleep(1)

    # 檢查是否在前景
    front = osa('tell application "System Events" to get name of first process whose frontmost is true')

    if "OneNote" in str(front):
        print_result(True, f"OneNote 已在前景")
        return True
    else:
        print_result(False, f"前景程式是: {front}")
        return False


def test_2_window_title():
    """測試 2: 讀取視窗標題"""
    print_header("測試 2: 讀取目前視窗標題")

    title = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return name of window 1
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''')

    if title and "ERROR" not in title:
        print_result(True, f"視窗標題: {title}")
        return True
    else:
        print_result(False, f"無法讀取: {title}")
        return False


def test_3_menu_items():
    """測試 3: 列出檔案選單中的項目"""
    print_header("測試 3: 檢查「檔案」選單項目")

    items = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    set menuItems to name of every menu item of menu "檔案" of menu bar 1
                    set output to ""
                    repeat with i in menuItems
                        if i is not missing value then
                            set output to output & i & ", "
                        end if
                    end repeat
                    return output
                on error
                    -- 嘗試英文
                    try
                        set menuItems to name of every menu item of menu "File" of menu bar 1
                        set output to ""
                        repeat with i in menuItems
                            if i is not missing value then
                                set output to output & i & ", "
                            end if
                        end repeat
                        return "EN:" & output
                    on error errMsg
                        return "ERROR:" & errMsg
                    end try
                end try
            end tell
        end tell
    ''')

    print(f"\n  選單項目: {items[:200]}...")

    if "儲存為 PDF" in str(items):
        print_result(True, "找到「儲存為 PDF」")
        return "儲存為 PDF", "檔案"
    elif "Save as PDF" in str(items):
        print_result(True, "找到「Save as PDF」(英文版)")
        return "Save as PDF", "File"
    elif "列印" in str(items) or "Print" in str(items):
        print_result(False, "沒有「儲存為 PDF」，但有「列印」")
        print("  → 可能需要用 Cmd+P → PDF 下拉選單的方式")
        return None, None
    else:
        print_result(False, f"無法找到匯出選項")
        return None, None


def test_4_open_save_dialog(menu_item, menu_name):
    """測試 4: 開啟儲存對話框"""
    print_header("測試 4: 開啟「儲存為 PDF」對話框")

    if not menu_item:
        print("  跳過（上一步未找到選單項目）")
        return False

    # 先點擊內容區域確保焦點
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

    # 點擊選單
    result = osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click menu item "{menu_item}" of menu "{menu_name}" of menu bar 1
                    return "OK"
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''')

    print(f"  點擊選單結果: {result}")

    # 等待對話框
    print("  等待對話框出現...")
    for i in range(10):
        time.sleep(0.5)
        windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window')
        print(f"    [{i+1}] 視窗: {windows}")
        if "另存新檔" in str(windows) or "Save" in str(windows):
            print_result(True, "對話框已開啟！")
            return True

    print_result(False, "對話框未開啟")
    return False


def test_5_read_dialog_title():
    """測試 5: 讀取對話框中的檔名"""
    print_header("測試 5: 讀取對話框中的檔名")

    # 嘗試繁中
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

    if title:
        print_result(True, f"檔名: {title}")
        return title

    # 嘗試英文
    title = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return value of text field "Save As:" of splitter group 1 of window "Save"
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''')

    if title and "ERROR" not in title:
        print_result(True, f"檔名 (EN): {title}")
        return title

    # 嘗試列出所有 text field
    print("  嘗試列出對話框中的所有 text field...")
    fields = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    set w to window 1
                    set output to ""
                    repeat with i from 1 to (count of every text field of w)
                        set tf to text field i of w
                        set output to output & "TF" & i & ":" & (value of tf) & "; "
                    end repeat
                    return output
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
        end tell
    ''')
    print(f"  Text fields: {fields}")

    print_result(False, "無法讀取檔名")
    return None


def test_6_cancel_dialog():
    """測試 6: 取消對話框"""
    print_header("測試 6: 關閉對話框")

    result = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取消" of splitter group 1 of window "另存新檔"
                    return "OK-TW"
                on error
                    try
                        click button "Cancel" of splitter group 1 of window "Save"
                        return "OK-EN"
                    on error
                        keystroke "." using {command down}
                        return "OK-ESC"
                    end try
                end try
            end tell
        end tell
    ''')

    time.sleep(0.5)
    windows = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window')

    if "另存新檔" not in str(windows) and "Save" not in str(windows):
        print_result(True, f"對話框已關閉 ({result})")
        return True
    else:
        print_result(False, f"對話框仍然存在")
        return False


def test_7_page_navigation():
    """測試 7: 翻頁功能"""
    print_header("測試 7: 頁面導航")

    # 先取得當前視窗標題
    before = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of window 1')
    print(f"  翻頁前: {before}")

    methods = [
        ("Cmd+PageDown (key code 121)", "key code 121 using {command down}"),
        ("Ctrl+Cmd+Down (key code 125)", "key code 125 using {control down, command down}"),
        ("Ctrl+PageDown", "key code 121 using {control down}"),
    ]

    for name, keystroke in methods:
        print(f"\n  測試 {name}...")
        osa(f'tell application "System Events" to tell process "Microsoft OneNote" to {keystroke}')
        time.sleep(1.5)

        after = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of window 1')

        if after != before:
            print_result(True, f"有效！新標題: {after}")
            return name
        else:
            print_result(False, "無變化")

    print("\n  ⚠ 所有翻頁方法都無效")
    print("  請手動測試：在 OneNote 中按什麼鍵可以翻到下一頁？")
    return None


def test_8_save_to_folder():
    """測試 8: 儲存到指定資料夾"""
    print_header("測試 8: 儲存檔案到指定資料夾")

    test_dir = os.path.expanduser("~/Desktop/OneNote-Export/_test")
    test_file = "test_export.pdf"
    test_path = os.path.join(test_dir, test_file)

    # 刪除舊測試檔
    if os.path.exists(test_path):
        os.remove(test_path)

    os.makedirs(test_dir, exist_ok=True)

    print(f"  目標: {test_path}")

    # 設定檔名
    print("  設定檔名...")
    osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    tell splitter group 1 of window "另存新檔"
                        set focused of text field "儲存為：" to true
                        delay 0.2
                        keystroke "a" using {{command down}}
                        delay 0.2
                        keystroke "{test_file}"
                    end tell
                on error
                    tell splitter group 1 of window "Save"
                        set focused of text field "Save As:" to true
                        delay 0.2
                        keystroke "a" using {{command down}}
                        delay 0.2
                        keystroke "{test_file}"
                    end tell
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)

    # 使用 Cmd+Shift+G 前往資料夾
    print("  使用 Cmd+Shift+G 前往資料夾...")
    osa('tell application "System Events" to tell process "Microsoft OneNote" to keystroke "g" using {command down, shift down}')
    time.sleep(1.0)

    # 輸入路徑
    ed = test_dir.replace('\\', '\\\\').replace('"', '\\"')
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

    # 點擊儲存
    print("  點擊儲存...")
    result = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "儲存" of splitter group 1 of window "另存新檔"
                    return "OK-TW"
                on error
                    try
                        click button "Save" of splitter group 1 of window "Save"
                        return "OK-EN"
                    on error errMsg
                        return "ERROR:" & errMsg
                    end try
                end try
            end tell
        end tell
    ''')
    print(f"  儲存按鈕結果: {result}")

    time.sleep(3)

    # 處理可能的覆蓋對話框
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取代" of sheet 1 of window 1
                on error
                    try
                        click button "Replace" of sheet 1 of window 1
                    end try
                end try
            end tell
        end tell
    ''')
    time.sleep(1)

    # 檢查檔案是否存在
    if os.path.exists(test_path):
        size = os.path.getsize(test_path)
        print_result(True, f"檔案已建立！大小: {size} bytes")
        return True
    else:
        print_result(False, "檔案未建立")

        # 列出 test 資料夾內容
        if os.path.exists(test_dir):
            files = os.listdir(test_dir)
            print(f"  資料夾內容: {files}")
        return False


# ─── 主程式 ─────────────────────────────────────────────────────────────

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║       OneNote PDF Export — 互動式功能測試                    ║
╠══════════════════════════════════════════════════════════════╣
║  這個腳本會逐步測試每個功能，幫你找出問題所在                ║
║                                                              ║
║  前置條件：                                                  ║
║    1. OneNote 已開啟並顯示一個有內容的頁面                   ║
║    2. Terminal 有輔助使用權限                                ║
╚══════════════════════════════════════════════════════════════╝
    """)

    wait_enter("準備好了嗎？")

    # 測試 1-2: 基本連接
    if not test_1_activate():
        print("\n⚠ 無法啟動 OneNote，請確認它已經開啟")
        return

    test_2_window_title()

    # 測試 3: 選單
    menu_item, menu_name = test_3_menu_items()

    wait_enter("\n接下來會開啟儲存對話框。")

    # 測試 4-5: 對話框
    if test_4_open_save_dialog(menu_item, menu_name):
        title = test_5_read_dialog_title()

        # 詢問是否要測試儲存
        print("\n" + "-"*60)
        choice = input("  要測試實際儲存嗎？(y/n): ").strip().lower()

        if choice == 'y':
            test_8_save_to_folder()
        else:
            test_6_cancel_dialog()

    wait_enter("\n接下來測試翻頁功能。")

    # 測試 7: 翻頁
    working_nav = test_7_page_navigation()

    # 總結
    print_header("測試總結")
    print(f"""
  選單項目: {menu_item or '未找到'}
  翻頁方法: {working_nav or '全部失敗'}

  下一步建議：
    如果所有測試通過 → 可以用 export_pdf_v2.py 開始匯出
    如果翻頁失敗 → 請手動找出 OneNote 的翻頁快捷鍵
    如果對話框失敗 → 可能需要調整 UI 元素路徑
    """)

if __name__ == "__main__":
    main()
