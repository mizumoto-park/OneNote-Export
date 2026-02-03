#!/usr/bin/env python3
"""
Get UI Geometry
取得 Group 5 (Page List Pane) 的位置和大小，以便測試點擊。
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
        set allWins to name of every window
        set info to "Windows Found: " & (allWins as string) & "\\n"

        -- Find main window
        set win to missing value
        repeat with w in windows
            if name of w contains "Morton" or name of w contains "筆記本" then
                set win to w
                exit repeat
            end if
        end repeat

        if win is missing value then
             if (count of windows) > 0 then
                  set win to window 1
                  set info to info & "Fallback to Window 1: " & (name of win) & "\\n"
             else
                  return "No windows found!" & "\\n" & info
             end if
        else
             set info to info & "Target Window: " & (name of win) & "\\n"
        end if

        -- Get Window Geometry
        set wPos to position of win
        set wSize to size of win
        set info to info & "Window Geometry: Pos=" & (item 1 of wPos) & "," & (item 2 of wPos) & " Size=" & (item 1 of wSize) & "," & (item 2 of wSize) & "\\n"

        try
            set sg1 to splitter group 1 of win
            set mainG to group 1 of sg1
            set g5 to item 5 of UI elements of mainG

            set children to UI elements of g5
            repeat with i from 1 to count of children
                set child to item i of children
                set cType to class of child as string

                set pos to position of child
                set sz to size of child

                set info to info & "G5 > Child " & i & " (" & cType & ") Pos: " & (item 1 of pos) & "," & (item 2 of pos) & " Size: " & (item 1 of sz) & "," & (item 2 of sz) & "\\n"
            end repeat

            return info

        on error errMsg
            return "Error: " & errMsg
        end try
    end tell
end tell
'''

print(osa(script))
