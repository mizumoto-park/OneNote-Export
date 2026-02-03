#!/usr/bin/env python3
"""
Debug Dialog
List menu items to ensure we are clicking the right one.
"""
import subprocess

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set frontmost to true
        activate
        delay 0.5

        try
            set fMenu to UI elements of menu 1 of menu bar item "檔案" of menu bar 1
            set nList to {}
            repeat with i in fMenu
                set end of nList to name of i
            end repeat
            return "File Menu (Traditional Chinese): " & (nList as string)
        on error
             try
                set fMenu to UI elements of menu 1 of menu bar item "File" of menu bar 1
                set nList to {}
                repeat with i in fMenu
                    set end of nList to name of i
                end repeat
                return "File Menu (English): " & (nList as string)
             on error errMsg
                return "Error accessing menu: " & errMsg
             end try
        end try
    end tell
end tell
'''

print(osa(script))
