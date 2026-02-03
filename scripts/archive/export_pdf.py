#!/usr/bin/env python3
"""
OneNote PDF Export via macOS UI Automation.

Strategy:
  1. Show notebook list → click notebook → enters notebook view
  2. Read section list from sidebar outline, click each section
  3. Check page list; skip empty sections
  4. For each page: File → 儲存為 PDF → read title → set path → Save
  5. Cmd+PageDown to next page; detect end by repeated title
  6. After all sections, switch to next notebook

Usage:
  python3 export_pdf.py              # Export ALL notebooks
  python3 export_pdf.py --resume     # Skip pages that already have PDFs
  python3 export_pdf.py --dry-run    # List pages without saving
  python3 export_pdf.py Work         # Export only "Work" notebook
"""

import subprocess, time, os, re, sys, sqlite3, json

EXPORT_DIR = os.path.expanduser("~/Desktop/OneNote-Export")
STATE_FILE = os.path.join(EXPORT_DIR, ".pdf_export_state.json")

DELAY_DIALOG = 3.5
DELAY_NAV = 1.5
DELAY_AFTER_SAVE = 2.5
DELAY_SECTION = 2.0

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

# Sidebar notebook table rows (1-based, discovered via UI inspection)
NOTEBOOK_ROW = {
    "Morton Rainey 的筆記本": 1,
    "Personal": 2,
    "Evernote": 3,
    "Work": 4,
    "7rendMicro": 5,
    "Morton 的筆記本": 6,
}

NOTEBOOK_ORDER = list(NOTEBOOK_ROW.keys())


# ── AppleScript helpers ──────────────────────────────────────────────

def osa(script, timeout=30):
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except subprocess.TimeoutExpired:
        return None


def activate():
    osa('tell application "Microsoft OneNote" to activate')
    time.sleep(1)


def click_content():
    """Click page content area so 'Save as PDF' works."""
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


def window_title():
    t = osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                return name of window 1
            end tell
        end tell
    ''')
    if t:
        t = t.strip().lstrip('\u200f\u200e')
        if " - " in t:
            t = t.rsplit(" - ", 1)[0].strip()
    return t or "Unknown"


# ── Notebook switching ───────────────────────────────────────────────

def show_notebook_list():
    """Click '顯示筆記本' button (searched by description in entire contents)."""
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                set parentG to group 1 of splitter group 1 of window 1
                set ec to entire contents of parentG
                repeat with item_ref in ec
                    try
                        if (class of item_ref as string) is "button" and description of item_ref is "顯示筆記本" then
                            click item_ref
                            exit repeat
                        end if
                    end try
                end repeat
            end tell
        end tell
    ''')
    time.sleep(2)


def switch_notebook(row_idx):
    """Show notebook list, then click row. Returns new window title."""
    show_notebook_list()
    # The table may or may not appear depending on current view.
    # Try clicking the notebook row.
    osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                set parentG to group 1 of splitter group 1 of window 1
                set sa to scroll area 1 of group 1 of group 1 of parentG
                set tbl to table 1 of sa
                set rw to row {row_idx} of tbl
                set selected of rw to true
                delay 0.3
                click UI element 1 of rw
                delay 0.3
                keystroke return
            end tell
        end tell
    ''')
    time.sleep(3)
    # Window name may have changed (causing the prior script to error).
    # Just re-read.
    return window_title()


# ── Section / page sidebar ───────────────────────────────────────────

def _read_outlines():
    """Read all outlines in the sidebar, return list of (group_path, [names])."""
    raw = osa('''
        set output to ""
        tell application "System Events"
            tell process "Microsoft OneNote"
                set parentG to group 1 of splitter group 1 of window 1
                repeat with i from 1 to (count of every group of parentG)
                    try
                        set g to group i of parentG
                        repeat with j from 1 to (count of every group of g)
                            try
                                set sg to group j of g
                                set ol to outline 1 of scroll area 1 of sg
                                set rws to every row of ol
                                if (count of rws) > 0 then
                                    set output to output & "OUTLINE:g" & i & "/sg" & j & ":" & (count of rws) & "|||"
                                    repeat with rw in rws
                                        set ec to entire contents of rw
                                        repeat with item_ref in ec
                                            try
                                                if (class of item_ref as string) is "static text" then
                                                    set v to value of item_ref
                                                    if v is not "" and v is not missing value then
                                                        set output to output & v & "|||"
                                                    end if
                                                end if
                                            end try
                                        end repeat
                                    end repeat
                                end if
                            end try
                        end repeat
                    end try
                end repeat
            end tell
        end tell
        return output
    ''')
    if not raw:
        return []
    outlines = []
    cur_key, cur_items = None, []
    for part in raw.split("|||"):
        part = part.strip()
        if part.startswith("OUTLINE:"):
            if cur_key:
                outlines.append((cur_key, cur_items))
            cur_key = part
            cur_items = []
        elif cur_key and part:
            cur_items.append(part)
    if cur_key:
        outlines.append((cur_key, cur_items))
    return outlines


def get_section_list():
    """Return (section_names, group_path) for the sidebar section outline."""
    outlines = _read_outlines()
    if not outlines:
        return [], None
    # Sections outline = the one with FEWER rows (pages outline has more)
    outlines.sort(key=lambda x: len(x[1]))
    key, names = outlines[0]
    path = key.split(":")[1]  # e.g. "g2/sg2"
    return names, path


def click_section(sec_idx, group_path):
    """Click section row (0-based) in the sidebar outline at group_path."""
    gi, sgi = [int(x[1:]) if x[0] == 'g' else int(x[2:]) for x in group_path.split("/")]
    osa(f'''
        tell application "System Events"
            tell process "Microsoft OneNote"
                set parentG to group 1 of splitter group 1 of window 1
                set ol to outline 1 of scroll area 1 of group {sgi} of group {gi} of parentG
                set rw to row {sec_idx + 1} of ol
                set selected of rw to true
                delay 0.2
                click rw
            end tell
        end tell
    ''')
    time.sleep(DELAY_SECTION)


def get_page_count():
    """Return number of pages visible in the page-list outline (the bigger one)."""
    outlines = _read_outlines()
    if len(outlines) < 2:
        return 0
    outlines.sort(key=lambda x: len(x[1]), reverse=True)
    return len(outlines[0][1])


# ── Save dialog ──────────────────────────────────────────────────────

def open_save_dialog():
    click_content()
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                click menu item "儲存為 PDF" of menu "檔案" of menu bar 1
            end tell
        end tell
    ''')
    time.sleep(DELAY_DIALOG)
    w = osa('tell application "System Events" to tell process "Microsoft OneNote" to get name of every window')
    return w is not None and "另存新檔" in w


def read_dialog_title():
    t = osa('''
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
    if t and t.lower().endswith(".pdf"):
        t = t[:-4]
    return t


def cancel_dialog():
    osa('''
        tell application "System Events"
            tell process "Microsoft OneNote"
                try
                    click button "取消" of splitter group 1 of window "另存新檔"
                end try
            end tell
        end tell
    ''')
    time.sleep(0.5)


def save_dialog(target_dir, filename):
    """With dialog open, set path + filename and click Save."""
    os.makedirs(target_dir, exist_ok=True)
    ef = filename.replace('\\', '\\\\').replace('"', '\\"')
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
                    return "ERR:" & errMsg
                end try
            end tell
        end tell
    ''')
    time.sleep(DELAY_AFTER_SAVE)

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
    return result is not None and "OK" in result


def next_page():
    osa('tell application "System Events" to tell process "Microsoft OneNote" to key code 121 using {command down}')
    time.sleep(DELAY_NAV)


# ── Utilities ────────────────────────────────────────────────────────

def sanitize(name):
    if not name:
        return "Untitled"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'[\s_]+', ' ', name).strip()
    return (name[:100].strip() if len(name) > 100 else name) or "Untitled"


def build_page_map():
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


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"exported_files": [], "done_sections": {}}


def persist(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── Export one section ───────────────────────────────────────────────

def export_section(nb_name, sec_name, state, dry_run, resume):
    safe_nb = sanitize(nb_name)
    safe_sec = sanitize(sec_name)
    target_dir = os.path.join(EXPORT_DIR, safe_nb, safe_sec)
    exported_set = set(state.get("exported_files", []))

    exp, skip, err = 0, 0, 0
    last_title = None
    consec = 0

    for i in range(200):
        if not open_save_dialog():
            time.sleep(2); activate(); time.sleep(1)
            if not open_save_dialog():
                err += 1
                if err > 3:
                    break
                next_page()
                continue

        title = read_dialog_title()
        if not title:
            cancel_dialog(); err += 1; next_page(); continue

        if title == last_title:
            consec += 1
            if consec >= 2:
                cancel_dialog()
                break
        else:
            consec = 0
        last_title = title

        safe_t = sanitize(title)
        pdf_fn = f"{safe_t}.pdf"
        pdf_path = os.path.join(target_dir, pdf_fn)

        if os.path.exists(pdf_path):
            if resume:
                print(f"      [{i+1}] SKIP {pdf_fn}")
                skip += 1; cancel_dialog(); next_page(); continue
            n = 2
            while os.path.exists(os.path.join(target_dir, f"{safe_t} ({n}).pdf")):
                n += 1
            pdf_fn = f"{safe_t} ({n}).pdf"
            pdf_path = os.path.join(target_dir, pdf_fn)

        if dry_run:
            print(f"      [{i+1}] DRY  {pdf_fn}")
            skip += 1; cancel_dialog(); next_page(); continue

        print(f"      [{i+1}] SAVE {pdf_fn}")
        if save_dialog(target_dir, pdf_fn):
            exp += 1
            exported_set.add(pdf_path)
            state["exported_files"] = list(exported_set)
            if exp % 10 == 0:
                persist(state)
        else:
            err += 1
            print(f"           FAILED")
            if err > 5:
                break

        next_page()

    return exp, skip, err


# ── Main ─────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    resume = "--resume" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]

    page_map = build_page_map()
    print(f"Page map: {len(page_map)} unique titles")

    state = load_state() if resume else {"exported_files": [], "done_sections": {}}
    done_secs = state.get("done_sections", {})

    nbs = NOTEBOOK_ORDER if not only else [
        n for n in NOTEBOOK_ORDER if any(o.lower() in n.lower() for o in only)
    ]
    print(f"Notebooks: {nbs}\n")

    activate()
    tot_exp, tot_skip, tot_err = 0, 0, 0

    try:
        for nb_name in nbs:
            row = NOTEBOOK_ROW.get(nb_name)
            if row is None:
                continue

            print(f"\n{'='*60}")
            print(f"Notebook: {nb_name} (row {row})")
            win = switch_notebook(row)
            print(f"  Window: {win}")

            sections, gpath = get_section_list()
            if not sections:
                print(f"  No sections found, skipping")
                continue
            print(f"  Sections ({len(sections)}): {sections}")

            for si, sname in enumerate(sections):
                sec_key = f"{nb_name}/{sname}"
                if resume and sec_key in done_secs:
                    print(f"\n    [{si+1}/{len(sections)}] DONE: {sname}")
                    continue

                print(f"\n    [{si+1}/{len(sections)}] Section: {sname}")
                click_section(si, gpath)

                pc = get_page_count()
                if pc == 0:
                    print(f"      (empty section)")
                    done_secs[sec_key] = True
                    state["done_sections"] = done_secs
                    persist(state)
                    continue
                print(f"      Pages visible: {pc}")

                exp, skip, err = export_section(nb_name, sname, state, dry_run, resume)
                tot_exp += exp; tot_skip += skip; tot_err += err

                done_secs[sec_key] = True
                state["done_sections"] = done_secs
                persist(state)
                print(f"      → {exp} saved, {skip} skipped, {err} errors")

    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    finally:
        persist(state)

    print(f"\n{'='*60}")
    print(f"TOTAL: {tot_exp} PDFs saved, {tot_skip} skipped, {tot_err} errors")
    print(f"Output: {EXPORT_DIR}")


if __name__ == "__main__":
    main()
