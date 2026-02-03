#!/usr/bin/env python3
"""
Debug Title Reader
Purpose: Find the EXACT AppleScript path to the filename in the Save Dialog.
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
        set frontmost to true

        -- Check if dialog exists
        set win to missing value
        if exists window "另存新檔" then
            set win to window "另存新檔"
        else if exists window "Save" then
            set win to window "Save"
        end if

        if win is missing value then
            return "Dialog Not Found. Please Open 'Save as PDF' dialog manually first!"
        end if

        set logStr to "Dialog Found: " & (name of win) & "\\n"

        -- TEST 1: Text Field 1 of Window
        try
            set v to value of text field 1 of win
            set logStr to logStr & "[Path 1] text field 1 of window: " & v & "\\n"
        on error
            set logStr to logStr & "[Path 1] Error\\n"
        end try

        -- TEST 2: Text Field 1 of Splitter Group 1
        try
            set v to value of text field 1 of splitter group 1 of win
            set logStr to logStr & "[Path 2] text field 1 of splitter group 1: " & v & "\\n"
        on error
            set logStr to logStr & "[Path 2] Error\\n"
        end try

        -- TEST 3: Loop Splitter Group Elements
        try
            set uiList to UI elements of splitter group 1 of win
            set logStr to logStr & "[Path 3] Iterating Splitter Group:\\n"
            repeat with i from 1 to count of uiList
                set uiItem to item i of uiList
                if class of uiItem is text field then
                    set logStr to logStr & "  - Item " & i & " (Text Field): " & (value of uiItem) & "\\n"
                end if
            end repeat
        on error
             set logStr to logStr & "[Path 3] Error iterating splitter group\\n"
        end try

        return logStr

    end tell
end tell
'''

print("--- DEBUGGING TITLE READ ---")
print("Please manually open the 'Save as PDF' dialog in OneNote.")
print("Running probe...")
print(osa(script))
