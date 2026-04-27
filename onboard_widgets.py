"""Interactive prompt widgets — clack-style, raw-terminal, stdlib only."""
import sys
from onboard_ui import (
    R, B, D, PURPLE, BLUE, GREEN, MUTED, WHITE,
    HIDE, SHOW, CLR, UP, BAR, step_done, get_key,
)

def ask_text(label, default="", hint=""):
    """Single-line text input. Enter accepts the shown default."""
    dflt = f"  {MUTED}({default}){R}" if default else ""
    hnt  = f"  {MUTED}{hint}{R}"       if hint    else ""
    print(f"{PURPLE}◇{R}  {B}{WHITE}{label}{R}{dflt}{hnt}")
    print(BAR)
    sys.stdout.write(f"{MUTED}└{R}  {BLUE}›{R} ")
    sys.stdout.flush()
    try:
        raw = input().strip()
    except EOFError:
        raw = ""
    result = raw or default
    # Erase the 3 printed lines, replace with ◆ summary
    sys.stdout.write(UP + CLR + UP + CLR + UP + CLR)
    step_done(label, result)
    return result


def ask_select(label, choices, default=0):
    """Arrow-key single-select. Returns the chosen string."""
    sel = default

    def _render():
        for i, c in enumerate(choices):
            if i == sel:
                print(f"{BAR}  {BLUE}●{R}  {WHITE}{B}{c}{R}")
            else:
                print(f"{BAR}  {MUTED}○  {c}{R}")
        print(f"{MUTED}└{R}")

    hint = f"  {MUTED}↑↓ navigate  ·  enter select{R}"
    print(f"{PURPLE}◇{R}  {B}{WHITE}{label}{R}{hint}")
    _render()

    sys.stdout.write(HIDE)
    sys.stdout.flush()
    n = len(choices)
    try:
        while True:
            key = get_key()
            if   key == "UP":    sel = (sel - 1) % n
            elif key == "DOWN":  sel = (sel + 1) % n
            elif key == "ENTER": break
            else: continue
            # Redraw choices only (question line stays)
            for _ in range(n + 1):
                sys.stdout.write(UP + CLR)
            sys.stdout.flush()
            _render()
    finally:
        sys.stdout.write(SHOW)
        sys.stdout.flush()

    # Erase question + choices + └, print ◆ summary
    for _ in range(n + 2):
        sys.stdout.write(UP + CLR)
    sys.stdout.flush()
    step_done(label, choices[sel])
    return choices[sel]


def ask_multiselect(label, choices, defaults=None, hint_extra=""):
    """Arrow-key multi-select with space-toggle. Returns list of chosen strings.

    `choices`: list of strings.
    `defaults`: list of indices to start checked (default: none).
    `hint_extra`: extra hint string appended to the navigation help.

    Same posture as ask_select: clack ◇ label, BAR rail, ▮ summary.
    Glyphs: ◉ checked / ○ unchecked, ▸ cursor.
    Keys: ↑↓ navigate · space toggle · enter confirm · q cancel (returns []).

    NOTE: uses `q` (not ESC) to cancel because the existing POSIX get_key()
    blocks on lone ESC waiting for an arrow-key sequence's second byte.
    `q` is universally available, no platform-specific terminal dance.
    """
    sel = set(defaults or [])
    cur = 0

    def _render():
        for i, c in enumerate(choices):
            box = f"{GREEN}◉{R}" if i in sel else f"{MUTED}○{R}"
            arrow = f"{BLUE}▸{R}" if i == cur else " "
            label_color = f"{WHITE}{B}" if i == cur else MUTED
            print(f"{BAR}  {arrow} {box}  {label_color}{c}{R}")
        print(f"{MUTED}└{R}")

    hint = f"  {MUTED}↑↓ navigate  ·  space toggle  ·  enter confirm  ·  q cancel{hint_extra}{R}"
    print(f"{PURPLE}◇{R}  {B}{WHITE}{label}{R}{hint}")
    _render()

    sys.stdout.write(HIDE)
    sys.stdout.flush()
    n = len(choices)
    cancelled = False
    try:
        while True:
            key = get_key()
            if   key == "UP":    cur = (cur - 1) % n
            elif key == "DOWN":  cur = (cur + 1) % n
            elif key == " ":     # literal space toggles current row
                if cur in sel: sel.remove(cur)
                else:          sel.add(cur)
            elif key == "ENTER": break
            elif key == "q" or key == "Q":
                cancelled = True
                break
            else:
                continue
            for _ in range(n + 1):
                sys.stdout.write(UP + CLR)
            sys.stdout.flush()
            _render()
    finally:
        sys.stdout.write(SHOW)
        sys.stdout.flush()

    for _ in range(n + 2):
        sys.stdout.write(UP + CLR)
    sys.stdout.flush()

    if cancelled:
        step_done(label, "(cancelled)")
        return []

    chosen = [choices[i] for i in sorted(sel)]
    summary = ", ".join(chosen) if chosen else "(none)"
    step_done(label, summary)
    return chosen


def ask_confirm(label, default=True):
    """Y / n confirm. Returns bool."""
    hint = f"{'Y/n' if default else 'y/N'}"
    print(f"{PURPLE}◇{R}  {B}{WHITE}{label}{R}  {MUTED}({hint}){R}")
    sys.stdout.write(f"{MUTED}└{R}  {BLUE}›{R} ")
    sys.stdout.flush()
    try:
        ans = input().strip().lower()
    except EOFError:
        ans = ""
    if   ans in ("y", "yes"): result = True
    elif ans in ("n", "no"):  result = False
    else:                     result = default
    sys.stdout.write(UP + CLR + UP + CLR)
    step_done(label, "yes" if result else "no")
    return result
