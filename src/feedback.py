"""Wordle feedback computation and encoding.

A feedback pattern is a tuple of 5 ints, one per letter position:
  2 = correct   (right letter, right spot   -> green)
  1 = present    (right letter, wrong spot   -> yellow)
  0 = absent     (letter not in word, or all copies already accounted for -> gray)
"""

from __future__ import annotations

CORRECT, PRESENT, ABSENT = 2, 1, 0

_CHAR_TO_SCORE = {"g": CORRECT, "y": PRESENT, "x": ABSENT, "-": ABSENT, ".": ABSENT}
_SCORE_TO_CHAR = {CORRECT: "G", PRESENT: "Y", ABSENT: "X"}


def score_naive(guess: str, secret: str) -> tuple[int, ...]:
    """Score `guess` against `secret` the way the votee.dev Wordle API actually does:
    a letter is "present" if it appears anywhere in the secret, with no cap on how
    many times a repeated guess letter can be credited. This diverges from official
    Wordle rules, and was confirmed against the live API, e.g. secret="mango" (one
    "a"), guess="aaaaa" -> all four non-green "a"s score present, not absent.
    """
    n = len(secret)
    result = [ABSENT] * n
    for i in range(n):
        if guess[i] == secret[i]:
            result[i] = CORRECT
        elif guess[i] in secret:
            result[i] = PRESENT
    return tuple(result)


def encode_pattern(pattern: tuple[int, ...]) -> int:
    """Encode a pattern tuple as a single base-3 integer for fast hashing/grouping."""
    value = 0
    for digit in reversed(pattern):
        value = value * 3 + digit
    return value


def decode_pattern(value: int, length: int = 5) -> tuple[int, ...]:
    """Inverse of `encode_pattern`."""
    digits = []
    for _ in range(length):
        digits.append(value % 3)
        value //= 3
    return tuple(digits)


def pattern_to_str(pattern: tuple[int, ...]) -> str:
    return "".join(_SCORE_TO_CHAR[s] for s in pattern)


def parse_feedback(text: str, length: int = 5) -> tuple[int, ...]:
    """Parse user-typed feedback, e.g. 'g-y-x' or 'GXYXX', into a pattern tuple."""
    text = text.strip().lower()
    if len(text) != length:
        raise ValueError(f"feedback must be {length} characters, got {text!r}")
    try:
        return tuple(_CHAR_TO_SCORE[c] for c in text)
    except KeyError as e:
        raise ValueError(f"unrecognized feedback character {e.args[0]!r}; use g/y/x") from e
