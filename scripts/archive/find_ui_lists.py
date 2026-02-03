#!/usr/bin/env python3
"""
Find UI Lists
遍歷所有 Scroll Areas 和 Groups 來找到 Notebook/Section/Page 列表。
該腳本不依賴特定索引，而是輸出所有可能的候選表格。
"""
import subprocess

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set frontmost to true
        activate
        delay 0.5

        set win to window 1
        set logOutput to ""

        try
            set sg1 to splitter group 1 of win
            set mainG to group 1 of sg1

            -- Level 3: Children of Main Group (Pane Containers)
            set children to UI elements of mainG
            repeat with i from 1 to count of children
                set child to item i of children
                set cType to class of child as string
                set logOutput to logOutput & "G" & i & " (" & cType & ")\\n"

                -- Level 4: Inside Pane (Scroll Area usually)
                if cType is "group" or cType is "scroll area" then
                     try
                        set gChildren to UI elements of child
                        repeat with j from 1 to count of gChildren
                            set gChild to item j of gChildren
                            set gType to class of gChild as string
                            set logOutput to logOutput & "  -> Inner " & j & " (" & gType & ")\\n"

                            -- CHECK FOR TABLE/OUTLINE
                            if gType is "table" then
                                set r to count of rows of gChild
                                set logOutput to logOutput & "     *** TABLE FOUND: G" & i & " > Inner " & j & " | Rows: " & r & " ***\\n"
                            end if
                            if gType is "outline" then
                                set r to count of rows of gChild
                                set logOutput to logOutput & "     *** OUTLINE FOUND: G" & i & " > Inner " & j & " | Rows: " & r & " ***\\n"
                            end if

                            -- Level 5: Inside Scroll Area (Table usually here)
                            if gType is "scroll area" or gType is "group" then
                                 try
                                    set fChildren to UI elements of gChild
                                    repeat with k from 1 to count of fChildren
                                        set fChild to item k of fChildren
                                        set fType to class of fChild as string

                                        if fType is "table" then
                                            set r to count of rows of fChild
                                            set logOutput to logOutput & "       *** TABLE FOUND: G" & i & " > Inner " & j & " > Item " & k & " | Rows: " & r & " ***\\n"
                                        end if
                                        if fType is "outline" then
                                            set r to count of rows of fChild
                                            set logOutput to logOutput & "       *** OUTLINE FOUND: G" & i & " > Inner " & j & " > Item " & k & " | Rows: " & r & " ***\\n"
                                        end if
                                    end repeat
                                 end try
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

print("Scanning for UI Lists...")
print(osa(script))
