#!/usr/bin/env python3
"""
Search Every Group
不依賴索引，遍歷 Splitter Group 1 的所有 children 尋找 Table。
"""
import subprocess

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=45)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set win to window 1
        set logOutput to ""

        try
            set sg1 to splitter group 1 of win
            set mainGroup to group 1 of sg1 -- The big container

            set sub_ui to UI elements of mainGroup

            repeat with i from 1 to count of sub_ui
                set current_ui to item i of sub_ui
                set uiType to class of current_ui as string

                set logOutput to logOutput & "G1 > Child " & i & " (" & uiType & ")...\\n"

                if uiType is "group" then
                     -- Look inside searching for scroll area -> table
                     try
                        set inner_ui to UI elements of current_ui
                        repeat with j from 1 to count of inner_ui
                            set inner to item j of inner_ui
                            set innerType to class of inner as string

                            set logOutput to logOutput & "  G1 > Child " & i & " > Inner " & j & " (" & innerType & ")\\n"

                            if innerType is "scroll area" then
                                set tablesList to tables of inner
                                if (count of tablesList) > 0 then
                                     set r to count of rows of item 1 of tablesList
                                     set logOutput to logOutput & "    *** FOUND TABLE in G1 > Child " & i & " > Inner " & j & " with " & r & " rows ***\\n"
                                end if

                                set outlinesList to outlines of inner
                                if (count of outlinesList) > 0 then
                                     set r to count of rows of item 1 of outlinesList
                                     set logOutput to logOutput & "    *** FOUND OUTLINE in G1 > Child " & i & " > Inner " & j & " with " & r & " rows ***\\n"
                                end if
                            end if

                        end repeat
                     end try
                end if

            end repeat

        on error errMsg
            set logOutput to logOutput & "Error: " & errMsg
        end try

        return logOutput
    end tell
end tell
'''

print(osa(script))
