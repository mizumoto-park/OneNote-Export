#!/usr/bin/env python3
"""
Test Click and Navigate
測試點擊指定座標並發送 Down Arrow，檢查頁面標題是否改變。
測試點：G5 右側 (Page List 假設位置)
"""
import subprocess
import time

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return f"Command failed: {r.stderr.strip()}"
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

# Window Geometry: Pos=1920,30 Size=1920,988
# G5 Scroll Area: Pos=2522,182 Size=1318,836
# Target Click: Right side of G5
# X = 2522 + 1318 - 80 = 3760
# Y = 182 + 100 = 282 (Relative to screen, G5 Y is 182)

click_x = 3760
click_y = 282

script = f'''
tell application "System Events"
    tell process "Microsoft OneNote"
        set frontmost to true
        activate
        delay 0.5


        -- Helper function to get filename
        -- Embedded directly

        -- STEP 1: Open Save Dialog
        try
            click menu item "儲存為 PDF" of menu 1 of menu bar item "檔案" of menu bar 1
        on error
            try
                click menu item "Save as PDF..." of menu 1 of menu bar item "File" of menu bar 1
            end try
        end try
        delay 2.0

        -- DEBUG: Check windows
        set allWins to name of every window
        set title1 to "Unknown"

        -- Try to match known dialogs
        if exists window "另存新檔" then
             set win to window "另存新檔"
             try
                  set title1 to value of text field 1 of win
                  if title1 is missing value then
                      set title1 to value of text field "儲存為：" of splitter group 1 of win
                  end if
             on error
                  set title1 to "Error reading field"
             end try

             -- Close
             try
                click button "取消" of win
             on error
                keystroke "." using {{command down}}
             end try

        else if exists window "Save" then
             set win to window "Save"
             try
                  set title1 to value of text field 1 of win
             on error
                  set title1 to "Error reading field"
             end try

             -- Close
             try
                click button "Cancel" of win
             on error
                keystroke "." using {{command down}}
             end try
        else
             -- Return debug info
             return "Dialog not found. Windows: " & (allWins as string)
        end if

        delay 0.5

        -- STEP 2: Navigate
        -- Click Page List (Right side guess)
        -- X=1820, Y=400
        click at {{1820, 400}}
        delay 0.5

        -- Down Arrow
        key code 125
        delay 1.0

        return "First Title: " & title1 & " | Navigation done. Please check OneNote."
    end tell
end tell
'''

print("Testing Blind Navigation...")
print(osa(script))
