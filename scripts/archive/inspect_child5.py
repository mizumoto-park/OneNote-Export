#!/usr/bin/env python3
"""
Inspect Child 5
檢查 group 5 > scroll area 1 的內部
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
        set win to window 1

        try
            set sg1 to splitter group 1 of win
            set g1 to group 1 of sg1
            set child5 to group 5 of g1
            set sa1 to scroll area 1 of child5

            set info to "Scroll Area 1 in Child 5 contains:\\n"

            set ui_elems to UI elements of sa1
            repeat with i from 1 to count of ui_elems
                set el to item i of ui_elems
                set elType to class of el as string
                set info to info & "  Element " & i & ": " & elType & "\\n"

                if elType is "table" then
                     set r to count of rows of el
                     set info to info & "    -> TABLE FOUND! Rows: " & r & "\\n"
                end if

                if elType is "outline" then
                     set r to count of rows of el
                     set info to info & "    -> OUTLINE FOUND! Rows: " & r & "\\n"
                end if

                if elType is "group" then
                     -- One more level deep
                     set sub_ui to UI elements of el
                     repeat with j from 1 to count of sub_ui
                        set sub to item j of sub_ui
                        set subType to class of sub as string
                        set info to info & "    -> Group Child " & j & ": " & subType & "\\n"
                        if subType is "table" then
                             set r to count of rows of sub
                             set info to info & "      -> TABLE FOUND! Rows: " & r & "\\n"
                        end if
                     end repeat
                end if

            end repeat

            return info

        on error errMsg
            return "Error: " & errMsg
        end try
    end tell
end tell
'''

print(osa(script))
