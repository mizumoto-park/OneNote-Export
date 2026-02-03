#!/usr/bin/env python3
"""
Find Page List by Row Count
遍歷所有 UI 元件尋找 row count > 0 的 table/outline，藉此鎖定頁面列表的位置。
"""

import subprocess

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set win to window 1
        set candidate_list to {}

        -- Helper to check an element for tables/outlines
        -- 由於 AppleScript 限制，我們只能展開幾層

        try
            set sg1 to splitter group 1 of win

            -- Level 1: Groups in Splitter Group
            set level1_groups to groups of sg1
            repeat with i from 1 to count of level1_groups
                set g1 to item i of level1_groups

                -- Level 2: Groups/ScrollAreas inside Level 1
                -- Check Scroll Areas direct child
                set sas to scroll areas of g1
                repeat with j from 1 to count of sas
                    set sa to item j of sas

                    -- Check Tables
                    set tbs to tables of sa
                    repeat with k from 1 to count of tbs
                        set tb to item k of tbs
                        set rc to count of rows of tb
                        set end of candidate_list to "Path: group " & i & " > scroll area " & j & " > table " & k & " ROWS: " & rc
                    end repeat
                end repeat

                -- Check Groups inside Level 1
                set level2_groups to groups of g1
                repeat with j from 1 to count of level2_groups
                    set g2 to item j of level2_groups

                    -- Level 3: Scroll Areas inside Level 2
                    set sas2 to scroll areas of g2
                    repeat with k from 1 to count of sas2
                        set sa2 to item k of sas2

                        -- Check Tables
                        set tbs2 to tables of sa2
                        repeat with m from 1 to count of tbs2
                            set tb2 to item m of tbs2
                            set rc to count of rows of tb2
                            set end of candidate_list to "Path: group " & i & " > group " & j & " > scroll area " & k & " > table " & m & " ROWS: " & rc
                        end repeat

                         -- Check Outlines
                        set ots2 to outlines of sa2
                        repeat with m from 1 to count of ots2
                            set ot2 to item m of ots2
                            set rc to count of rows of ot2
                            set end of candidate_list to "Path: group " & i & " > group " & j & " > scroll area " & k & " > outline " & m & " ROWS: " & rc
                        end repeat

                    end repeat
                end repeat

            end repeat

        on error errMsg
            set end of candidate_list to "Error: " & errMsg
        end try

        return candidate_list
    end tell
end tell
'''

print("Searching for tables with rows...")
result = osa(script)
print(result)
