#!/usr/bin/env python3
"""
Inspect Save Dialog UI
Opens the 'Save as PDF' dialog and dumps its UI hierarchy to find the filename field.
"""
import subprocess
import time

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set frontmost to true

        -- 1. Open Dialog if not open
        if not (exists window "另存新檔") and not (exists window "Save") then
            try
                click menu item "儲存為 PDF" of menu 1 of menu bar item "檔案" of menu bar 1
            on error
                try
                    click menu item "Save as PDF..." of menu 1 of menu bar item "File" of menu bar 1
                end try
            end try
            delay 2.0
        end if

        -- 2. Find Window
        set targetWin to missing value
        if exists window "另存新檔" then
            set targetWin to window "另存新檔"
        else if exists window "Save" then
            set targetWin to window "Save"
        end if

        if targetWin is missing value then
            return "Error: Save dialog not found."
        end if

        -- 3. Recursive Dump
        set output to "Window: " & (name of targetWin) & "\\n"

        -- Helper to dump children
        -- Cannot use true recursion easily in vanilla AS without handlers,
        -- so we just do 2 levels deep manual dump which is usually enough for Save Dialogs

        set l1 to UI elements of targetWin
        repeat with i1 in l1
            set iType to class of i1 as string
            set iRole to role description of i1
            set iName to name of i1
            if iName is missing value then set iName to "<noname>"

            set iVal to "<noval>"
            try
                set iVal to value of i1
            end try

            set output to output & "  L1: " & iType & " (" & iName & ") Role:" & iRole & " Value:" & iVal & "\\n"

            -- Level 2
            try
                set l2 to UI elements of i1
                repeat with i2 in l2
                    set iType2 to class of i2 as string
                    set iName2 to name of i2
                    if iName2 is missing value then set iName2 to "<noname>"
                     set iVal2 to "<noval>"
                    try
                        set iVal2 to value of i2
                    end try

                    set output to output & "    L2: " & iType2 & " (" & iName2 & ") Value:" & iVal2 & "\\n"

                     -- Level 3
                    try
                        set l3 to UI elements of i2
                        repeat with i3 in l3
                            set iType3 to class of i3 as string
                            set iName3 to name of i3
                             set iVal3 to "<noval>"
                            try
                                set iVal3 to value of i3
                            end try
                             set output to output & "      L3: " & iType3 & " (" & iName3 & ") Value:" & iVal3 & "\\n"
                        end repeat
                    end try
                end repeat
            end try
        end repeat

        -- Close Dialog
        try
             click button "取消" of targetWin
        on error
             keystroke "." using {command down}
        end try

        return output

    end tell
end tell
'''

print("Inspecting Save Dialog...")
print(osa(script))
