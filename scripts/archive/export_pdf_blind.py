#!/usr/bin/env python3
"""
OneNote Blind PDF Exporter (v9)
- Strategy: Sequential Export (Page_001.pdf, Page_002.pdf...)
- No UI Text Reading (100% Blind)
- Robust Window Detection (Largest Window)
- Robust Save Dialog Control
"""
import subprocess
import time
import sys
import os

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

            -- Find largest window (likely main window)
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
               return "Error: Main window not found"
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

def export_page_blind(target_folder, target_filename):
    """
    Export current page using blind manual entry.
    Robustness: Uses 'text field 1 of splitter group 1' fallback.
    """
    script = f'''
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

            if exists window "另存新檔" then
                set win to window "另存新檔"
            else
                set win to window "Save"
            end if

            -- 2. Go to Folder (Cmd+Shift+G)
            keystroke "g" using {{command down, shift down}}
            delay 1.0

            -- Paste Path
            set the clipboard to "{target_folder}"
            keystroke "v" using {{command down}}
            delay 0.5
            keystroke return
            delay 1.0

            -- 3. Set Filename
            try
                -- Try index based approach which is most robust
                if exists splitter group 1 of win then
                    set value of text field 1 of splitter group 1 of win to "{target_filename}"
                else
                    set value of text field 1 of win to "{target_filename}"
                end if
            on error
                try
                    set value of text field "Save As:" of splitter group 1 of win to "{target_filename}"
                on error
                    set value of text field 1 of win to "{target_filename}"
                end try
            end try
            delay 0.5

            -- 4. Save
            keystroke return
            delay 1.5

            -- 5. Handle "Replace?" Dialog if it appears
            if exists sheet 1 of win then
                click button "Replace" of sheet 1 of win
                delay 1.0
            end if

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
    print("OneNote Blind PDF Exporter (v9)")
    print("-------------------------------")
    print("Instructions:")
    print("1. Open OneNote and go to the target section.")
    print("2. Click on the FIRST PAGE you want to export.")
    print("3. Ensure OneNote is visible.")

    nb = input("Enter Notebook Name: ").strip()
    section = input("Enter Section Name: ").strip()
    count_str = input("How many pages to export? ").strip()

    try:
        count = int(count_str)
    except:
        print("Invalid number.")
        sys.exit(1)

    base_dir = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    target_dir = os.path.join(base_dir, nb, section)
    os.makedirs(target_dir, exist_ok=True)

    print(f"\nTarget: {target_dir}")
    print("Detecting Window Geometry...")
    coords = get_click_coordinates()

    if not coords:
        print("Failed to find OneNote window. Is it open?")
        sys.exit(1)

    click_x, click_y = coords
    print(f"Click Coordinates: {click_x}, {click_y}")

    print("\nStarting Blind Export Loop...")

    for i in range(1, count + 1):
        filename = f"{section}_{i:03d}.pdf"
        print(f"[{i}/{count}] Exporting {filename}...")

        # Check if exists
        # We don't skip because we want to maintain the loop alignment
        # But we could check? No, overwrite is safer to ensure it matches current page.

        export_page_blind(os.path.abspath(target_dir), filename)

        if i < count:
            print("  Navigating...")
            blind_navigate(click_x, click_y)
            time.sleep(1.5)

    print("\nBatch Complete!")

if __name__ == "__main__":
    main()
