#!/usr/bin/env python3
"""
Simple OneNote PDF exporter — exports one page at a time.

Flow:
  1. Opens save dialog (File → 儲存為 PDF)
  2. Reads page title from dialog
  3. Looks up notebook/section from SQLite
  4. Sets filename + path, clicks Save
  5. Presses Cmd+PageDown to go to next page
  6. Repeats until you press Ctrl+C

YOU control which notebook/section is active in OneNote.
The script just saves + advances. Press Ctrl+C to stop.

Usage:
  python3 export_pdf_simple.py                 # Export from current page
  python3 export_pdf_simple.py --section "AWS"  # Override section name
  python3 export_pdf_simple.py --no-advance    # Don't auto-advance (save current page only)
"""

import subprocess, time, os, re, sys, sqlite3

EXPORT_DIR = os.path.expanduser("~/Desktop/OneNote-Export")

FTS_DIR = os.path.expanduser(
    "~/Library/Containers/com.microsoft.onenote.mac/Data/Library/"
    "Application Support/Microsoft User Data/OneNote/"
    "15.0-restore/FullTextSearchIndex"
)

DATABASES = {
    "{3DBD86EA-D2F6-7343-AC97-863B47D29236}{19}.db": "Work",
    "{D62C1D86-38B0-0B4C-9A45-7259DDD20395}{51}.db": "Personal",
    "{D62C1D86-38B0-0B4C-9A45-7259DDD20395}{10}.db": "Morton Rainey 的筆記本",
    "{248E7F28-E3C6-AC43-A45F-8A5936C978E7}{10}.db": "Evernote",
    "{5497DFA7-B4A4-EC49-95F1-9B049B091C4E}{10}.db": "7rendMicro",
}


def osa(script, timeout=30):
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except subprocess.TimeoutExpired:
        return None


def build_page_map():
    """title → [(notebook, section), ...]"""
    pm = {}
    for db, nb in DATABASES.items():
        p = os.path.join(FTS_DIR, db)
        if not os.path.exists(p):
            continue
        conn = sqlite3.connect(p)
        c = conn.cursor()
        c.execute("SELECT GOID, Title FROM Entities WHERE Type=2")
        secs = {r[0]: r[1] for r in c.fetchall()}
        c.execute("SELECT Title, ParentGOID FROM Entities WHERE Type=1")
        for t, pg in c.fetchall():
            if t:
                pm.setdefault(t.strip(), []).append((nb, secs.get(pg, "Unsorted")))
        conn.close()
    return pm


def sanitize(name):
    if not name:
        return "Untitled"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'[\s_]+', ' ', name).strip()
    return (name[:100].strip() if len(name) > 100 else name) or "Untitled"


def export_current_page(page_map, title_seen, section_override=None):
    """
    Open save dialog, read title, save PDF to correct path.
    Returns (title, success) or (None, False) on failure.
    """
    # Click content area for focus
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                set frontmost to true
                delay 0.3
                set p to position of window 1
                set s to size of window 1
                click at {(item 1 of p) + ((item 1 of s) * 0.7), (item 2 of p) + ((item 2 of s) * 0.5)}
            end tell
        end tell
    ''')
    time.sleep(0.5)

    # Open save dialog
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                click menu item "儲存為 PDF" of menu "檔案" of menu bar 1
            end tell
        end tell
    ''')
    time.sleep(3.5)

    # Check dialog appeared
    w = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window')
    if not w or "另存新檔" not in w:
        return None, False

    # Read title
    raw = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    return value of text field "儲存為：" of splitter group 1 of window "另存新檔"
                on error
                    return ""
                end try
            end tell
        end tell
    ''')
    if not raw:
        osa('tell application "System Events" to tell process "Microsoft OneNote" to try\nclick button "取消" of splitter group 1 of window "另存新檔"\nend try')
        return None, False

    title = raw[:-4] if raw.lower().endswith(".pdf") else raw

    # Look up path
    key = title.strip()
    title_seen[key] = title_seen.get(key, 0) + 1
    occ = title_seen[key]

    if section_override:
        nb_name = "Override"
        sec_name = section_override
        # Try to find the notebook from page_map
        if key in page_map:
            nb_name = page_map[key][0][0]
    elif key in page_map:
        matches = page_map[key]
        idx = min(occ - 1, len(matches) - 1)
        nb_name, sec_name = matches[idx]
    else:
        nb_name = "Unknown"
        sec_name = "Unsorted"

    safe_nb = sanitize(nb_name)
    safe_sec = sanitize(sec_name)
    safe_t = sanitize(title)
    target_dir = os.path.join(EXPORT_DIR, safe_nb, safe_sec)
    pdf_fn = f"{safe_t}.pdf"
    pdf_path = os.path.join(target_dir, pdf_fn)

    # Skip if exists
    if os.path.exists(pdf_path):
        osa('tell application "System Events" to tell process "Microsoft OneNote" to try\nclick button "取消" of splitter group 1 of window "另存新檔"\nend try')
        time.sleep(0.5)
        return title, "SKIP"

    # Set filename and save
    os.makedirs(target_dir, exist_ok=True)
    ef = pdf_fn.replace('\\', '\\\\').replace('"', '\\"')
    ed = target_dir.replace('\\', '\\\\').replace('"', '\\"')

    osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                tell splitter group 1 of window "另存新檔"
                    set focused of text field "儲存為：" to true
                    delay 0.2
                    keystroke "a" using {{command down}}
                    delay 0.2
                    keystroke "{ef}"
                end tell
            end tell
        end tell
    ''')
    time.sleep(0.3)

    osa('tell application "System Events" to tell process "Microsoft OneNote" to keystroke "g" using {command down, shift down}')
    time.sleep(1.0)

    osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                keystroke "{ed}"
                delay 0.5
                keystroke return
            end tell
        end tell
    ''')
    time.sleep(1.5)

    result = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "儲存" of splitter group 1 of window "另存新檔"
                    return "OK"
                on error errMsg
                    return "ERR"
                end try
            end tell
        end tell
    ''')
    time.sleep(2.5)

    # Handle replace dialog
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取代" of sheet 1 of window 1
                on error
                    try
                        if exists button "取代" of window 1 then click button "取代" of window 1
                    end try
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)

    ok = result is not None and "OK" in result
    return title, ok


def advance_page():
    osa('tell application "System Events" to tell process "Microsoft OneNote" to key code 121 using {command down}')
    time.sleep(1.5)


def main():
    no_advance = "--no-advance" in sys.argv
    section_override = None
    for i, arg in enumerate(sys.argv):
        if arg == "--section" and i + 1 < len(sys.argv):
            section_override = sys.argv[i + 1]

    page_map = build_page_map()
    print(f"Page map: {len(page_map)} titles from SQLite")
    print(f"Output: {EXPORT_DIR}")
    if section_override:
        print(f"Section override: {section_override}")
    if no_advance:
        print("Mode: single page (no auto-advance)")
    else:
        print("Mode: auto-advance with Cmd+PageDown")
    print("Press Ctrl+C to stop.\n")

    osa('tell application "Microsoft OneNote" to activate')
    time.sleep(1)

    exported = 0
    skipped = 0
    errors = 0
    title_seen = {}
    last_title = None
    consec = 0

    try:
        for i in range(500):
            title, result = export_current_page(page_map, title_seen, section_override)

            if title is None:
                print(f"  [{i+1}] ERROR: dialog failed")
                errors += 1
                if errors > 5:
                    print("Too many errors, stopping.")
                    break
                if not no_advance:
                    advance_page()
                continue

            if title == last_title:
                consec += 1
                if consec >= 2:
                    print(f"  [{i+1}] End of section (repeated: {title})")
                    break
            else:
                consec = 0
            last_title = title

            if result == "SKIP":
                print(f"  [{i+1}] SKIP  {title}")
                skipped += 1
            elif result:
                print(f"  [{i+1}] SAVED {title}")
                exported += 1
            else:
                print(f"  [{i+1}] FAIL  {title}")
                errors += 1

            if no_advance:
                break

            advance_page()

    except KeyboardInterrupt:
        print("\n\nStopped.")

    print(f"\n{'='*50}")
    print(f"Saved: {exported}  Skipped: {skipped}  Errors: {errors}")
    print(f"Output: {EXPORT_DIR}")


if __name__ == "__main__":
    main()
