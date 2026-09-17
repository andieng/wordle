"""Word list loading.

Word lists and frequency data are all as published in 3Blue1Brown's
"videos" repo (github.com/3b1b/videos, _2022/wordle/data/):
  - answers.txt (2,309 words): the curated set Wordle actually draws
    secrets from -- used as the solver's starting candidate pool.
  - guesses.txt (12,953 words): the full set of guesses the real game
    accepts (a superset of answers.txt) -- used as the guess pool for the
    one-time offline first-guess entropy computation.
  - word_freq.json: real-world usage frequency per word (their
    `freq_map.json`), used to weight how *likely* each candidate is to
    actually be the secret, not just whether it's plausible at all.
"""

import json
from functools import lru_cache
from pathlib import Path

ANSWERS_FILE = Path(__file__).parent / "data" / "answers.txt"
GUESSES_FILE = Path(__file__).parent / "data" / "guesses.txt"
WORD_FREQ_FILE = Path(__file__).parent / "data" / "word_freq.json"


def _read(path: Path) -> tuple[str, ...]:
    with path.open() as f:
        return tuple(line.strip() for line in f if line.strip())


@lru_cache(maxsize=1)
def load_answers() -> tuple[str, ...]:
    """Return the curated candidate/answer word list."""
    return _read(ANSWERS_FILE)


@lru_cache(maxsize=1)
def load_guesses() -> tuple[str, ...]:
    """Return the full valid-guess word list (superset of answers)."""
    return _read(GUESSES_FILE)


@lru_cache(maxsize=1)
def load_frequencies() -> dict[str, float]:
    """Return {word: relative usage frequency}. Words with no entry (e.g. a
    proper noun encountered via the raw fallback tier) should be treated as
    frequency 0 by callers."""
    with WORD_FREQ_FILE.open() as f:
        return json.load(f)
