#!/usr/bin/env python3
"""
OneNote PDF Exporter v10 - Hybrid Edition
- Strategy: Try to read filename (Find field with ".pdf"), Fallback to sequential.
- Robust Window Detection
- Blind Navigation
"""
import subprocess
import time
import sys
import os
import re

def osa(script):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def get_click_coordinates():
    """Dynamically find optimal click coordinates for Page List (G5) using Largest Window logic."""
    script = '''
    tell application "System Events"
        tell process "Microsoft OneNote"
            set win to missing value
            set maxArea to 0

            -- Find largest window
            set allWins to every window
            repeat with w in allWins
                try
                    set wSize to size of w
                    if wSize is not missing value then
                        set wArea to (item 1 of wSize) * (item 2 of wSize)
                        if wArea > 250000 and wArea > maxArea then
                            set maxArea to wArea
                            set win to w
                        end if
                    end if
                end try
            end repeat

            if win is missing value then
               return "Error"
            end if

            try
                set sg1 to splitter group 1 of win
                set mainG to group 1 of sg1
                set g5 to item 5 of UI elements of mainG
                set pos to position of g5
                set sz to size of g5

                -- Calculate Click Point: Right Edge - 80px, Top + 100px
                set targetX to (item 1 of pos) + (item 1 of sz) - 80
                set targetY to (item 2 of pos) + 100
                return (targetX as string) & "," & (targetY as string)
            on error
                return "Error"
            end try
        end tell
    end tell
    '''
    result = osa(script)
    if not result or "Error" in result:
        return None
    try:
        x, y = map(int, result.split(','))
        return (x, y)
    except:
        return None

def get_filename_heuristic():
    """
    Search for a text field containing '.pdf' in the Save Dialog.
    Returns: Filename (e.g., "MyPage.pdf") or None
    """
    script = '''
    tell application "System Events"
        tell process "Microsoft OneNote"
            set frontmost to true

            -- 1. Open Dialog
            try
                click menu item "儲存為 PDF" of menu 1 of menu bar item "檔案" of menu bar 1
            on error
                try
                    click menu item "Save as PDF..." of menu 1 of menu bar item "File" of menu bar 1
                end try
            end try
            delay 2.0

            set win to missing value
            if exists window "另存新檔" then
                set win to window "另存新檔"
            else if exists window "Save" then
                set win to window "Save"
            end if

            if win is missing value then return "Error: No Dialog"

            set foundName to "Missing"

            -- Strategy: Check all text fields in Splitter Group 1
            try
                set uiList to UI elements of splitter group 1 of win
                repeat with uiItem in uiList
                    if class of uiItem is text field then
                        set val to value of uiItem
                        if val contains ".pdf" then
                            set foundName to val
                            exit repeat
                        end if
                    end if
                end repeat
            end try

            -- Fallback: Check all text fields directly in Window
            if foundName is "Missing" then
               try
                   set uiList to UI elements of win
                   repeat with uiItem in uiList
                       if class of uiItem is text field then
                           set val to value of uiItem
                           if val contains ".pdf" then
                               set foundName to val
                               exit repeat
                           end if
                       end if
                   end repeat
               end try
            end if

            -- Close Dialog
            try
                click button "取消" of win
            on error
                keystroke "." using {command down}
            end try

            return foundName
        end tell
    end tell
    '''
    return osa(script)

def export_page_v10(target_folder, target_filename):
    """Export page with specific filename."""
    # Escape quotes
    clean_fn = target_filename.replace('"', '\\"')

    script = f'''
    tell application "System Events"
        tell process "Microsoft OneNote"
            -- Open Dialog
            try
                click menu item "儲存為 PDF" of menu 1 of menu bar item "檔案" of menu bar 1
            on error
                try
                    click menu item "Save as PDF..." of menu 1 of menu bar item "File" of menu bar 1
                end try
            end try
            delay 2.0

            if exists window "另存新檔" then
                set win to window "另存新檔"
            else
                set win to window "Save"
            end if

            -- Go to Folder
            keystroke "g" using {{command down, shift down}}
            delay 1.0
            set the clipboard to "{target_folder}"
            keystroke "v" using {{command down}}
            delay 0.5
            keystroke return
            delay 1.0

            -- Set Filename
            try
                 -- Try finding the right field again to write to
                 set targetField to missing value
                 try
                     set uiList to UI elements of splitter group 1 of win
                     repeat with uiItem in uiList
                        if class of uiItem is text field then
                            set val to value of uiItem
                            if val contains ".pdf" then
                                set targetField to uiItem
                                exit repeat
                            end if
                        end if
                     end repeat
                 end try

                 if targetField is not missing value then
                     set value of targetField to "{clean_fn}"
                 else
                     -- Blind Fallback: Text field 1
                     set value of text field 1 of splitter group 1 of win to "{clean_fn}"
                 end if
            on error
                 set value of text field 1 of win to "{clean_fn}"
            end try
            delay 0.5

            -- Save
            keystroke return
            delay 1.5

             -- Handle Replace
            if exists sheet 1 of win then
                click button "Replace" of sheet 1 of win
                delay 1.0
            end if
        end tell
    end tell
    '''
    return osa(script)


def blind_navigate(x, y):
    script = f'''
    tell application "System Events"
        tell process "Microsoft OneNote"
            click at {{{x}, {y}}}
            delay 0.5
            key code 125 -- Down Arrow
        end tell
    end tell
    '''
    osa(script)

def main():
    print("OneNote PDF Exporter v10 (Hybrid)")
    print("---------------------------------")
    print("Strategy: Attempt to read original title. If fail, use 'Section_001'.")
    print("1. Open OneNote -> Target Section.")
    print("2. Click FIRST PAGE.")
    print("3. Ensure visible.")

    nb = input("Notebook Name: ").strip()
    section = input("Section Name: ").strip()
    count_str = input("Pages to export: ").strip()
    try:
        count = int(count_str)
    except:
        sys.exit(1)

    base_dir = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    target_dir = os.path.join(base_dir, nb, section)
    os.makedirs(target_dir, exist_ok=True)

    print(f"\nTarget: {target_dir}")
    print("Detecting Geometry...")
    coords = get_click_coordinates()
    if not coords:
        print("OneNote window not found.")
        sys.exit(1)
    click_x, click_y = coords
    print(f"Geometry OK: {click_x}, {click_y}")

    print("\nStarting Hybrid Export Loop...")

    for i in range(1, count + 1):
        print(f"[{i}/{count}] Reading title...")

        # 1. Try to read title
        raw_name = get_filename_heuristic()

        final_name = ""
        is_fallback = False

        if raw_name and ".pdf" in raw_name and "Unknown" not in raw_name and "Missing" not in raw_name and "Error" not in raw_name:
            # Got it!
            final_name = raw_name
            print(f"  Found Title: {final_name}")
        else:
            # Failed
            is_fallback = True
            final_name = f"{section}_{i:03d}.pdf"
            print(f"  Title Not Found. Using Fallback: {final_name}")

        # 2. Export
        export_page_v10(os.path.abspath(target_dir), final_name)

        if i < count:
            print("  Navigating...")
            blind_navigate(click_x, click_y)
            time.sleep(1.5)

    print("\nBatch Complete!")

if __name__ == "__main__":
    main()
