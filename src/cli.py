"""Terminal rendering: colored tile board and keyboard, via raw ANSI codes."""

from __future__ import annotations

from feedback import ABSENT, CORRECT, PRESENT

_RESET = "\033[0m"
_BOLD = "\033[1m"
_BG = {CORRECT: "\033[42;30m", PRESENT: "\033[43;30m", ABSENT: "\033[100;37m"}
_UNUSED_BG = "\033[47;30m"

_KEYBOARD_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]


def render_tile(letter: str, status: int) -> str:
    return f"{_BG[status]}{_BOLD} {letter.upper()} {_RESET}"


def render_board(history: list[tuple[str, tuple[int, ...]]]) -> str:
    lines = []
    for guess, pattern in history:
        tiles = " ".join(render_tile(ch, s) for ch, s in zip(guess, pattern))
        lines.append(tiles)
    return "\n".join(lines)


def render_keyboard(history: list[tuple[str, tuple[int, ...]]]) -> str:
    best_status: dict[str, int] = {}
    for guess, pattern in history:
        for ch, status in zip(guess, pattern):
            if status > best_status.get(ch, -1):
                best_status[ch] = status

    lines = []
    for row in _KEYBOARD_ROWS:
        cells = []
        for ch in row:
            if ch in best_status:
                bg = _BG[best_status[ch]]
            else:
                bg = _UNUSED_BG
            cells.append(f"{bg}{_BOLD} {ch.upper()} {_RESET}")
        lines.append(" ".join(cells))
    return "\n".join(lines)


def status_line(text: str, color: str = "cyan") -> str:
    codes = {"cyan": "\033[36m", "green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m"}
    return f"{codes.get(color, '')}{text}{_RESET}"
