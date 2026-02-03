#!/bin/bash
# OneNote PDF Export via AppleScript UI Automation
#
# PREREQUISITES:
# 1. Open System Settings → Privacy & Security → Accessibility
# 2. Add "Terminal" (or "iTerm" if using iTerm) to the allowed apps
# 3. OneNote must be open with the notebooks loaded
#
# This script navigates through OneNote using keyboard shortcuts
# and exports each page as PDF via Cmd+P → "Save as PDF"
#
# Usage: bash export_pdf_applescript.sh

EXPORT_DIR="$HOME/Desktop/OneNote-Export"
DELAY=2  # seconds between operations (increase if OneNote is slow)

echo "=== OneNote PDF Export ==="
echo "Export directory: $EXPORT_DIR"
echo ""
echo "IMPORTANT: Before running this script:"
echo "  1. Grant Terminal accessibility permission in System Settings"
echo "  2. Open OneNote and make sure all notebooks are loaded"
echo "  3. Navigate to the first page of the first notebook"
echo ""
echo "This script will use Cmd+P → Save as PDF for each page."
echo "Press Ctrl+C to stop at any time."
echo ""
read -p "Press Enter to start (or Ctrl+C to cancel)..."

# Read the page list from the markdown export to know the structure
python3 << 'PYEOF'
import os
import sys
import subprocess
import time

EXPORT_DIR = os.path.expanduser("~/Desktop/OneNote-Export")
DELAY = 2.5  # seconds between operations

def run_applescript(script):
    """Run an AppleScript and return the result."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"  AppleScript error: {result.stderr.strip()}")
        return None
    return result.stdout.strip()

def activate_onenote():
    run_applescript('tell application "Microsoft OneNote" to activate')
    time.sleep(1)

def send_keystroke(key, modifiers=""):
    """Send a keystroke to OneNote via System Events."""
    if modifiers:
        mod_str = ", ".join(f"{m} down" for m in modifiers.split(","))
        script = f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                keystroke "{key}" using {{{mod_str}}}
            end tell
        end tell
        '''
    else:
        script = f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                keystroke "{key}"
            end tell
        end tell
        '''
    return run_applescript(script)

def send_key_code(code, modifiers=""):
    """Send a key code to OneNote via System Events."""
    if modifiers:
        mod_str = ", ".join(f"{m} down" for m in modifiers.split(","))
        script = f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                key code {code} using {{{mod_str}}}
            end tell
        end tell
        '''
    else:
        script = f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                key code {code}
            end tell
        end tell
        '''
    return run_applescript(script)

def export_current_page_as_pdf(pdf_path):
    """Export the currently displayed page as PDF."""
    # Create directory if needed
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    # Cmd+P to open print dialog
    send_keystroke("p", "command")
    time.sleep(DELAY)

    # Click "PDF" dropdown → "Save as PDF"
    # On macOS, in the print dialog, we need to click the PDF button
    # Using keyboard: the PDF button can be reached via the menu
    script = '''
    tell application "System Events"
        tell process "Microsoft OneNote"
            -- Click the PDF dropdown button in the print dialog
            try
                click menu button "PDF" of sheet 1 of window 1
                delay 1
                click menu item "Save as PDF…" of menu 1 of menu button "PDF" of sheet 1 of window 1
                delay 1
            on error
                -- Try alternate layout
                click menu button "PDF" of window 1
                delay 1
                click menu item "Save as PDF…" of menu 1 of menu button "PDF" of window 1
                delay 1
            end try
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(1)

    # Type the filename using Cmd+Shift+G to go to path
    send_keystroke("g", "command,shift")
    time.sleep(0.5)

    # Type the full path
    script = f'''
    tell application "System Events"
        tell process "Microsoft OneNote"
            keystroke "{os.path.dirname(pdf_path)}"
            delay 0.5
            keystroke return
            delay 1
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(1)

    # Set filename
    filename = os.path.basename(pdf_path)
    script = f'''
    tell application "System Events"
        tell process "Microsoft OneNote"
            -- Select all text in the filename field and type new name
            keystroke "a" using {{command down}}
            delay 0.3
            keystroke "{filename}"
            delay 0.5
            keystroke return
            delay 2
        end tell
    end tell
    '''
    run_applescript(script)
    time.sleep(DELAY)

def navigate_next_page():
    """Move to the next page in OneNote (Cmd+Page Down or Ctrl+Page Down)."""
    # OneNote Mac: Ctrl+Cmd+Down to go to next page
    send_key_code(125, "control,command")  # key code 125 = Down arrow
    time.sleep(1)

# Main logic: iterate through all .md files we exported and export PDF for each
print("Scanning exported markdown files for page list...")
page_list = []
for root, dirs, files in os.walk(EXPORT_DIR):
    for f in sorted(files):
        if f.endswith(".md") and f != "index.md":
            md_path = os.path.join(root, f)
            rel_path = os.path.relpath(md_path, EXPORT_DIR)
            pdf_path = os.path.join(EXPORT_DIR, rel_path.replace(".md", ".pdf"))
            page_list.append((rel_path, pdf_path))

print(f"Found {len(page_list)} pages to export as PDF")
print()
print("NOTE: This script requires accessibility permissions.")
print("If you see errors about accessibility, grant Terminal permission in:")
print("  System Settings → Privacy & Security → Accessibility")
print()

activate_onenote()
time.sleep(1)

exported = 0
errors = 0
for i, (rel_path, pdf_path) in enumerate(page_list):
    if os.path.exists(pdf_path):
        print(f"  [{i+1}/{len(page_list)}] SKIP (exists): {rel_path}")
        continue

    print(f"  [{i+1}/{len(page_list)}] Exporting: {rel_path}")
    try:
        export_current_page_as_pdf(pdf_path)
        navigate_next_page()
        exported += 1
    except Exception as e:
        print(f"    ERROR: {e}")
        errors += 1
        if errors > 5:
            print("Too many errors, stopping.")
            break

print(f"\nDone. Exported {exported} PDFs, {errors} errors.")
PYEOF
