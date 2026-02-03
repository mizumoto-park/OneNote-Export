#!/usr/bin/env python3
"""
OneNote PDF Exporter v8 - Blind Navigation Edition
- Features:
  - Dynamic Geometry Detection for Multi-Monitor Support
  - Blind Click + Down Arrow for Page Navigation
  - Robust Filename Reading (Legacy/Classic Dialogs)
  - Semi-Automated Loop (User picks section, script does the rest)
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
    """Dynamically find optimal click coordinates for Page List (G5)"""
    script = '''
    tell application "System Events"
        tell process "Microsoft OneNote"
            set win to missing value
            set maxArea to 0

            -- Find main window by size (largest window is likely the main one)
            set allWins to every window
            repeat with w in allWins
                try
                    set wSize to size of w
                    if wSize is not missing value then
                        set wArea to (item 1 of wSize) * (item 2 of wSize)
                        -- Filter out small dialogs (arbitrary threshold 500x500)
                        if wArea > 250000 and wArea > maxArea then
                            set maxArea to wArea
                            set win to w
                        end if
                    end if
                end try
            end repeat

            if win is missing value then
               return "Error: Main window not found (No large window detected)"
            end if

            -- Find G5 (Splitter -> Group 1 -> Item 5)
            try
                set sg1 to splitter group 1 of win
                set mainG to group 1 of sg1

                -- G5 is typically item 5 or the last item
                set g5 to item 5 of UI elements of mainG

                set pos to position of g5
                set sz to size of g5

                -- Calculate Click Point: Right Edge - 80px, Top + 100px
                -- Adjust these offsets if click misses the list
                set targetX to (item 1 of pos) + (item 1 of sz) - 80
                set targetY to (item 2 of pos) + 100

                return (targetX as string) & "," & (targetY as string)
            on error errMsg
                return "Error finding G5: " & errMsg
            end try
        end tell
    end tell
    '''
    result = osa(script)
    if "Error" in result:
        print(f"Geometry Error: {result}")
        return None
    try:
        x, y = map(int, result.split(','))
        return (x, y)
    except:
        return None

def get_page_filename():
    """Open Save Dialog, read filename, Close Dialog."""
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

            -- 2. Read Title
            set fName to "Unknown"
            set win to missing value

            if exists window "另存新檔" then
                set win to window "另存新檔"
                try
                    -- Get first text field in the splitter group (safer than name)
                    set fName to value of text field 1 of splitter group 1 of win
                on error
                    set fName to value of text field 1 of win
                end try
            else if exists window "Save" then
                set win to window "Save"
                try
                    set fName to value of text field 1 of splitter group 1 of win
                on error
                    set fName to value of text field 1 of win
                end try
            end if

            -- 3. Close Dialog
            if win is not missing value then
                 try
                     click button "取消" of win
                 on error
                     click button "Cancel" of win
                 end try
            else
                 -- Try Esc/Cmd+. if window not found but stuck
                 keystroke "." using {command down}
            end if

            return fName
        end tell
    end tell
    '''
    return osa(script)

def export_page_v7(target_folder, target_filename):
    """Actual export logic from v7"""
    full_path = os.path.join(target_folder, target_filename).replace('"', '\\"')
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

            -- Go to Folder (Cmd+Shift+G)
            keystroke "g" using {{command down, shift down}}
            delay 1.0

            -- Paste Path
            set the clipboard to "{target_folder}"
            keystroke "v" using {{command down}}
            delay 0.5
            keystroke return
            delay 1.0

            -- Set Filename
            try
                set value of text field 1 of win to "{target_filename}"
            on error
                set value of text field "Save As:" of splitter group 1 of win to "{target_filename}"
            end try
            delay 0.5

            -- Save
            keystroke return
            delay 1.0
        end tell
    end tell
    '''
    return osa(script)

def blind_navigate(x, y):
    """Click at (x,y) and press Down Arrow"""
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
    print("OneNote PDF Exporter v8 (Blind Navigation)")
    print("------------------------------------------")
    print("Instructions:")
    print("1. Open OneNote and navigate to the SECTION you want to export.")
    print("2. Click on the FIRST PAGE of that section.")
    print("3. Ensure OneNote is visible (on any monitor).")

    nb = input("Enter Notebook Name: ").strip()
    section = input("Enter Section Name: ").strip()

    base_dir = result = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    target_dir = os.path.join(base_dir, nb, section)
    os.makedirs(target_dir, exist_ok=True)

    print(f"\nTarget Folder: {target_dir}")
    print("Detecting Window Geometry...")

    coords = get_click_coordinates()
    if not coords:
        print("Failed to detect window geometry. Make sure OneNote is open.")
        sys.exit(1)

    click_x, click_y = coords
    print(f"Click Coordinates Detected: {click_x}, {click_y}")

    print("\nStarting Export Loop...")
    last_title = ""

    while True:
        # 1. Get Current Title
        title = get_page_filename()
        if not title or title == "Unknown":
            print("Error reading title. Retrying once...")
            time.sleep(1)
            title = get_page_filename()
            if not title or title == "Unknown":
               print("Failed to read title. Stopping.")
               break

        # Stop condition: Same title as last time (means we hit the bottom)
        if title == last_title:
            print("Title unchanging. End of section reached.")
            break

        print(f"Exporting: {title}")

        # 2. Export
        clean_name = re.sub(r'[\\/:*?"<>|]', '_', title)
        # Assuming .pdf is added by OneNote, but if we provide it, safer.
        # Check if v7 added it. v7 checked if it exists.

        # We will strip extension from title if present (usually not in field)
        if clean_name.lower().endswith('.pdf'):
            clean_name = clean_name[:-4]

        # Check if exists
        pdf_path = os.path.join(target_dir, clean_name + ".pdf")
        if os.path.exists(pdf_path):
            print(f"  Skipping {clean_name} (Already exists)")
        else:
            export_page_v7(os.path.abspath(target_dir), clean_name)

        last_title = title

        # 3. Navigate
        print("  Navigating to next page...")
        blind_navigate(click_x, click_y)
        time.sleep(1.5) # Wait for page load

    print("\nExport Complete!")

if __name__ == "__main__":
    main()
