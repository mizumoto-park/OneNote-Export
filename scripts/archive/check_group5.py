#!/usr/bin/env python3
"""
Deep Check Group 5
專門檢查 Group 5 的內部結構，因為它最像是頁面列表
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
        set logOutput to ""

        try
            set sg1 to splitter group 1 of win
            set g5 to group 5 of sg1

            set elems to UI elements of g5
            repeat with i from 1 to count of elems
                set el to item i of elems
                set elClass to class of el as string
                set logOutput to logOutput & "Group 5 > Item " & i & ": " & elClass & "\\n"

                if elClass is "scroll area" then
                    -- Check inside scroll area
                    set sub_elems to UI elements of el
                    repeat with j from 1 to count of sub_elems
                        set sub to item j of sub_elems
                        set subClass to class of sub as string
                        set logOutput to logOutput & "  -> ScrollArea > Item " & j & ": " & subClass & "\\n"

                        if subClass is "table" then
                            set rc to count of rows of sub
                            set logOutput to logOutput & "    *** FOUND TABLE with " & rc & " rows ***\\n"
                        end if
                        if subClass is "outline" then
                            set rc to count of rows of sub
                            set logOutput to logOutput & "    *** FOUND OUTLINE with " & rc & " rows ***\\n"
                        end if
                    end repeat
                end if

                if elClass is "group" then
                     set sub_elems to UI elements of el
                     repeat with j from 1 to count of sub_elems
                        set sub to item j of sub_elems
                        set subClass to class of sub as string
                        set logOutput to logOutput & "  -> Group > Item " & j & ": " & subClass & "\\n"

                        if subClass is "scroll area" then
                             set sa_elems to UI elements of sub
                             repeat with k from 1 to count of sa_elems
                                set sa_item to item k of sa_elems
                                set saClass to class of sa_item as string
                                set logOutput to logOutput & "    -> ScrollArea > Item " & k & ": " & saClass & "\\n"

                                if saClass is "table" then
                                    set rc to count of rows of sa_item
                                    set logOutput to logOutput & "      *** FOUND TABLE with " & rc & " rows ***\\n"
                                end if
                             end repeat
                        end if
                     end repeat
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
