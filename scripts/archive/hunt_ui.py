#!/usr/bin/env python3
"""
OneNote Page List Hunter
測試特定的 UI 路徑來尋找頁面列表 Table
"""

import subprocess

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

paths_to_test = [
    'table 1 of scroll area 1 of group 1 of splitter group 1 of window 1',
    'table 1 of scroll area 1 of group 2 of splitter group 1 of window 1',
    'table 1 of scroll area 1 of group 3 of splitter group 1 of window 1',
    'table 1 of scroll area 1 of group 1 of group 1 of splitter group 1 of window 1',
    'table 1 of scroll area 1 of group 2 of group 1 of splitter group 1 of window 1',
    'table 1 of scroll area 1 of group 3 of group 1 of splitter group 1 of window 1',

    # 也可能是 outline
    'outline 1 of scroll area 1 of group 1 of splitter group 1 of window 1',
    'outline 1 of scroll area 1 of group 2 of splitter group 1 of window 1',
    'outline 1 of scroll area 1 of group 3 of splitter group 1 of window 1',
    'outline 1 of scroll area 1 of group 1 of group 1 of splitter group 1 of window 1',
]

print("Hunting for Page List Table...\n")

for path in paths_to_test:
    script = f'''
    tell application "System Events"
        tell process "Microsoft OneNote"
            try
                set t via {path}
                return "FOUND: " & (count of rows of t) & " rows at {path}"
            on error
                return "MISS"
            end try
        end tell
    end tell
    '''
    res = osa(script)
    if not "MISS" in res:
        print(res)
    else:
        print(f"Miss: {path}")

print("\nListing all scroll areas in Group 1:")
list_script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set deep_info to ""
        try
            set g1 to group 1 of splitter group 1 of window 1
            set sas to scroll areas of g1
            repeat with i from 1 to count of sas
                set sa to item i of sas
                set deep_info to deep_info & "ScrollArea " & i & " inside G1 contains: " & (UI elements of sa) & "\\n"
            end repeat

            -- Also check for groups inside G1
            set gps to groups of g1
            repeat with k from 1 to count of gps
                set gp to item k of gps
                set deep_info to deep_info & "Group " & k & " inside G1 contains: " & (count of UI elements of gp) & " elems\\n"

                 -- Check scroll area inside sub-group
                 try
                    set sub_sas to scroll areas of gp
                    repeat with m from 1 to count of sub_sas
                        set sub_sa to item m of sub_sas
                        set tbs to tables of sub_sa
                        if (count of tbs) > 0 then
                             set deep_info to deep_info & "  *** FOUND TABLE inside G1 > G" & k & " > SA" & m & " ***\\n"
                        end if
                    end repeat
                 end try
            end repeat

        on error errMsg
            set deep_info to "Error: " & errMsg
        end try
        return deep_info
    end tell
end tell
'''
print(osa(list_script))
