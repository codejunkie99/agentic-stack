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
