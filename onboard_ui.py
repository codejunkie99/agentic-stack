"""ANSI palette, block-char banner, and clack-style layout atoms (stdlib only)."""
import sys, os, shutil

_WIN = sys.platform == "win32"
if _WIN:
    import msvcrt
else:
    import tty, termios

# ── Palette ───────────────────────────────────────────────────────────────
def _e(*c): return f"\x1b[{';'.join(map(str,c))}m"
def _hex(h, bg=False):
    h = h.lstrip("#"); r,g,b = int(h[:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"\x1b[{'48' if bg else '38'};2;{r};{g};{b}m"

R  = _e(0);  B  = _e(1);  D  = _e(2)
PURPLE = _hex("#BF5AF2"); BLUE   = _hex("#0A84FF")
GREEN  = _hex("#30D158"); ORANGE = _hex("#FF9F0A")
MUTED  = _hex("#636366"); WHITE  = _hex("#F5F5F7")

HIDE = "\x1b[?25l"; SHOW = "\x1b[?25h"
CLR  = "\x1b[2K\r"; UP   = "\x1b[1A"

# ── Banner ────────────────────────────────────────────────────────────────
# 2-row pixel font spells "AGENTIC STACK"
_L1 = "  ▄▀█ █▀▀ █▀▀ █▄░█ ▀█▀ █ █▀▀  █▀ ▀█▀ ▄▀█ █▀▀ █▄▀ "
_L2 = "  █▀█ █▄█ ██▄ █░▀█ ░█░ █ █▄▄  ▄█ ░█░ █▀█ █▄▄ █░█ "
_T  = "  your portable brain  ·  harness-agnostic AI memory  ·  v0.4.0"

def _cc(c):
    if c == "█": return f"{PURPLE}{B}{c}{R}"
    if c in "▀▄": return f"{BLUE}{c}{R}"
    return f"{MUTED}{c}{R}"

def print_banner():
    w = shutil.get_terminal_size((80, 24)).columns
    print()
    print("".join(_cc(c) for c in _L1))
    print("".join(_cc(c) for c in _L2))
    print(f"\n{MUTED}{'':>{(w - len(_T.strip()))//2}}{_T.strip()}{R}\n")

# ── Layout atoms ──────────────────────────────────────────────────────────
BAR = f"{MUTED}│{R}"

def intro(title):
    print(f"\n{PURPLE}◇{R}  {B}{WHITE}{title}{R}")
    print(BAR)

def note(title, lines):
    print(f"{BAR}\n{BAR}  {B}{ORANGE}{title}{R}")
    for ln in lines:
        print(f"{BAR}  {MUTED}{ln}{R}")
    print(BAR)

def step_done(label, value):
    v = f"{WHITE}{B}{value}{R}" if value else f"{MUTED}(skipped){R}"
    print(f"{PURPLE}◆{R}  {D}{label}{R}  {MUTED}…{R}  {v}")

def outro(lines):
    print(BAR)
    for i, ln in enumerate(lines):
        icon = f"{GREEN}◆{R}" if i == 0 else f"{MUTED}│{R}"
        print(f"{icon}  {WHITE}{ln}{R}")
    print(f"{MUTED}└{R}\n")

# ── Raw key reader ────────────────────────────────────────────────────────
if _WIN:
    def get_key():
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):        # arrow-key / function-key prefix
            c2 = msvcrt.getwch()
            return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(c2, "ESC")
        if ch in "\r\n":  return "ENTER"
        if ch == "\x03":  raise KeyboardInterrupt
        if ch == "\x08":  return "BACKSPACE"
        if ch == "\x1b":  return "ESC"
        return ch
else:
    def _getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.buffer.read(1).decode("utf-8", errors="replace")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def get_key():
        ch = _getch()
        if ch == "\x1b":
            _getch()                      # consume '['
            c2 = _getch()
            return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(c2, "ESC")
        if ch in "\r\n":  return "ENTER"
        if ch == "\x03":  raise KeyboardInterrupt
        if ch == "\x7f":  return "BACKSPACE"
        return ch
