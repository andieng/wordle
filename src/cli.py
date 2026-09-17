"""Terminal rendering: colored tile board, via raw ANSI codes."""

from __future__ import annotations

from feedback import ABSENT, CORRECT, PRESENT

_RESET = "\033[0m"
_BOLD = "\033[1m"
_BG = {CORRECT: "\033[42;30m", PRESENT: "\033[43;30m", ABSENT: "\033[100;37m"}


def render_tile(letter: str, status: int) -> str:
    return f"{_BG[status]}{_BOLD} {letter.upper()} {_RESET}"


def render_board(history: list[tuple[str, tuple[int, ...]]]) -> str:
    lines = []
    for guess, pattern in history:
        tiles = " ".join(render_tile(ch, s) for ch, s in zip(guess, pattern))
        lines.append(tiles)
    return "\n".join(lines)


def status_line(text: str, color: str = "cyan") -> str:
    codes = {"cyan": "\033[36m", "green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m"}
    return f"{codes.get(color, '')}{text}{_RESET}"
