#!/usr/bin/env python3
"""
OneNote PDF Exporter v11 - Ultimate Automation
- Features:
  - Minimal Input: Only Notebook Name required.
  - Smart Stop: Detects duplicate filenames to stop automatically.
  - Hybrid Naming: Preserves original titles (with fallback).
  - Robust Geometry: Supports multi-monitor.
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
    """Find OneNote main window (Largest Area) and click point (G5)."""
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

            if win is missing value then return "Error"

            try
                set mainG to group 1 of splitter group 1 of win
                set g5 to item 5 of UI elements of mainG
                set pos to position of g5
                set sz to size of g5

                -- Click Point: Right Edge - 80, Top + 100
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
    if not result or "Error" in result: return None
    try:
        x, y = map(int, result.split(','))
        return (x, y)
    except:
        return None

def get_filename_heuristic():
    """Open Save Dialog, find field with '.pdf', return value, Close Dialog."""
    script = '''
    tell application "System Events"
        tell process "Microsoft OneNote"
            set frontmost to true

            -- Open Dialog
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

            set foundName to "Missing"

            if win is not missing value then
                -- Search Splitter Group 1
                try
                    set uiList to UI elements of splitter group 1 of win
                    repeat with uiItem in uiList
                        try
                            if value of uiItem contains ".pdf" then
                                set foundName to value of uiItem
                                exit repeat
                            end if
                        end try
                    end repeat
                end try

                -- Fallback Search Window Direct
                if foundName is "Missing" then
                    try
                        set uiList to UI elements of win
                        repeat with uiItem in uiList
                           try
                               if value of uiItem contains ".pdf" then
                                   set foundName to value of uiItem
                                   exit repeat
                               end if
                           end try
                        end repeat
                    end try
                end if

                -- Close Dialog
                try
                    click button "取消" of win
                on error
                    click button "Cancel" of win
                end try
            else
                -- Safety escape
                keystroke "." using {command down}
            end if

            return foundName
        end tell
    end tell
    '''
    return osa(script)

def export_page(target_folder, target_filename):
    """Save PDF with target filename."""
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
            -- Try blindly setting text field 1 of splitter group 1 OR window
            try
               if exists splitter group 1 of win then
                   set value of text field 1 of splitter group 1 of win to "{clean_fn}"
               else
                   set value of text field 1 of win to "{clean_fn}"
               end if
            on error
               -- Worst case
               keystroke "{clean_fn}"
            end try
            delay 0.5

            -- Save
            keystroke return
            delay 1.5

            -- Replace?
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
    print("OneNote PDF Exporter v11 (Ultimate)")
    print("-----------------------------------")
    print("Instructions:")
    print("1. Open OneNote -> Target Section -> First Page.")
    print("2. Ensure OneNote is visible.")

    nb = input("Notebook Name (Required): ").strip()
    if not nb:
        print("Notebook Name is required.")
        sys.exit(1)

    sec = input("Section Name (Enter -> 'Default_Section'): ").strip()
    if not sec:
        sec = "Default_Section"

    print("\nStarting Auto-Export...")
    print("Press Ctrl+C to Stop manually if needed.")

    base_dir = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    target_dir = os.path.join(base_dir, nb, sec)
    os.makedirs(target_dir, exist_ok=True)

    coords = get_click_coordinates()
    if not coords:
        print("Error: OneNote window not found.")
        sys.exit(1)
    click_x, click_y = coords

    last_title = ""
    retry_count = 0
    i = 1

    while True:
        # 1. Peek at Title
        raw_name = get_filename_heuristic()

        # Logic: If we can read it, use it. If not, fallback to numbered.
        # But if we fallback, we lose "Auto-Stop" capability based on duplicate names.

        final_name = ""
        is_unknown = False

        if raw_name and ".pdf" in raw_name and "Missing" not in raw_name:
             final_name = raw_name
        else:
             final_name = f"Page_{i:03d}.pdf"
             is_unknown = True

        print(f"[{i}] Processing: {final_name}")

        # 2. Check for Duplicate (Stop Condition)
        if not is_unknown and final_name == last_title:
            retry_count += 1
            if retry_count >= 2:
                print("End of Section detected (Duplicate Title).")
                break
            print("  Title same as last. Retrying navigation...")
            blind_navigate(click_x, click_y)
            time.sleep(1.0)
            continue
        else:
            retry_count = 0

        # 3. Export
        export_page(os.path.abspath(target_dir), final_name)

        last_title = final_name
        i += 1

        # 4. Navigate
        blind_navigate(click_x, click_y)
        time.sleep(1.5)

    print(f"\nCompleted! Files saved to: {target_dir}")

if __name__ == "__main__":
    main()
