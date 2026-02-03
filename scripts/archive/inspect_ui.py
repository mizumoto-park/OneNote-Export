#!/usr/bin/env python3
"""
OneNote UI Inspector
用來找尋頁面列表(Page List)的 UI 元素結構，以便透過 AppleScript 直接點擊/選取下一頁。
"""

import subprocess
import time

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

print("請確保 OneNote 視窗在最上層，並顯示頁面列表...")
time.sleep(2)

script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set frontmost to true
        activate
        delay 0.5

        -- 取得主視窗
        set win to window 1
        set winName to name of win

        -- 嘗試列出所有 splitter groups, scroll areas, outlines, tables
        -- 我們要找的是包含 "Page List" 或類似結構的元素

        set structure to {}

        tell win
            -- Level 1: Splitter Groups
            set sgs to splitter groups
            repeat with sg in sgs
                set cls to class of sg as string
                set ui_elems to UI elements of sg
                set elem_desc to {}
                repeat with elem in ui_elems
                    set end of elem_desc to (class of elem as string)
                end repeat
                set end of structure to "SplitterGroup: " & (description of sg) & " contains: " & (elem_desc as string)
            end repeat

            -- Level 1: Groups
            set gs to groups
            repeat with g in gs
                set end of structure to "Group: " & (description of g)
            end repeat

            -- Level 1: Scroll Areas (可能包含 Table/Outline)
            set sas to scroll areas
            repeat with sa in sas
                set end of structure to "ScrollArea: " & (description of sa)
            end repeat
        end tell

        return {winName, structure}
    end tell
end tell
'''

result = osa(script)
print(f"UI Inspection Result:\n{result}")

print("\n--- Deep Dive into Scroll Areas ---")
# 深入檢查 Scroll Areas，通常列表都在這裡
deep_script = '''
tell application "System Events"
    tell process "Microsoft OneNote"
        set win to window 1

        -- 定義地規函數來探索 UI 元素
        -- AppleScript 本身沒有很好的遞迴支援，我們用展開的方式探測 Splitter Group 1 內部

        set logOutput to ""

        try
            set sg1 to splitter group 1 of win
            set logOutput to logOutput & "Splitter Group 1 found. Elements: " & (count of UI elements of sg1) & "\\n"

            -- 探測 Splitter Group 1 的子元素
            set sub_elems to UI elements of sg1
            repeat with i from 1 to count of sub_elems
                set elem to item i of sub_elems
                set elemClass to class of elem as string
                set logOutput to logOutput & "  [" & i & "] " & elemClass & "\\n"

                if elemClass is "group" then
                    -- 深入 Group
                    set grand_elems to UI elements of elem
                    repeat with j from 1 to count of grand_elems
                        set grand to item j of grand_elems
                        set grandClass to class of grand as string
                        set logOutput to logOutput & "    [" & i & "." & j & "] " & grandClass & "\\n"

                        -- 繼續深入找 Scroll Area
                        if grandClass is "scroll area" then
                            set sa_elems to UI elements of grand
                            repeat with k from 1 to count of sa_elems
                                set sa_item to item k of sa_elems
                                set saClass to class of sa_item as string
                                set logOutput to logOutput & "      [" & i & "." & j & "." & k & "] " & saClass & "\\n"

                                if saClass is "table" then
                                    set rowCount to count of rows of sa_item
                                    set logOutput to logOutput & "        *** FOUND TABLE with " & rowCount & " rows ***\\n"
                                end if
                                if saClass is "outline" then
                                    set rowCount to count of rows of sa_item
                                    set logOutput to logOutput & "        *** FOUND OUTLINE with " & rowCount & " rows ***\\n"
                                end if
                            end repeat

                        -- Splitter Group 內可能還有 Splitter Group (筆記本列表 vs 節列表 vs 頁面列表)
                        else if grandClass is "splitter group" then
                             set sp_elems to UI elements of grand
                             repeat with k from 1 to count of sp_elems
                                set sp_item to item k of sp_elems
                                set spClass to class of sp_item as string
                                set logOutput to logOutput & "      [" & i & "." & j & "." & k & "] " & spClass & "\\n"

                                -- 再深入一層... OneNote 結構可能很深
                                if spClass is "group" then
                                    set sp_sub to UI elements of sp_item
                                    repeat with m from 1 to count of sp_sub
                                        set sp_sub_item to item m of sp_sub
                                        set spSubClass to class of sp_sub_item as string
                                        set logOutput to logOutput & "        [" & i & "." & j & "." & k & "." & m & "] " & spSubClass & "\\n"

                                        if spSubClass is "scroll area" then
                                            set final_elems to UI elements of sp_sub_item
                                            repeat with n from 1 to count of final_elems
                                                set f_item to item n of final_elems
                                                set fClass to class of f_item as string
                                                set logOutput to logOutput & "          [" & i & "." & j & "." & k & "." & m & "." & n & "] " & fClass & "\\n"
                                                if fClass is "table" then
                                                    set rowCount to count of rows of f_item
                                                    set logOutput to logOutput & "            *** FOUND TABLE with " & rowCount & " rows ***\\n"
                                                end if
                                            end repeat
                                        end if
                                    end repeat
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

deep_result = osa(deep_script)
print(f"Deep Dive Result:\n{deep_result}")
