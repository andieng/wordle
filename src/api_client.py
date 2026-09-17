"""Thin client for the live Wordle API at https://wordle.votee.dev:8000.

Endpoint behavior (confirmed by live probing, not just the OpenAPI schema):
  - size must be a positive integer; 0 or negative -> Internal Server Error.
  - seed must be in [0, 2**32 - 1]; outside that range -> Internal Server Error.
  - guess length must exactly equal size (or len(word) for /word/{word}),
    else a plain-text 400 body, not JSON.
  - /random without a seed draws a NEW secret every call, so a multi-guess
    game must generate one seed client-side and reuse it for every guess.
  - Scoring itself does not follow official Wordle duplicate-letter rules
    (see feedback.score_naive) -- present is plain membership in the secret.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from feedback import ABSENT, CORRECT, PRESENT

BASE_URL = "https://wordle.votee.dev:8000"
WORD_SIZE = 5
MAX_SEED = 2**32 - 1

_RESULT_TO_SCORE = {"absent": ABSENT, "present": PRESENT, "correct": CORRECT}


class ApiError(RuntimeError):
    """Raised for any failure talking to the Wordle API."""


def _validate_guess(guess: str, expected_length: int) -> None:
    if len(guess) != expected_length:
        raise ValueError(
            f"guess {guess!r} must be {expected_length} characters, got {len(guess)}"
        )


def _validate_seed(seed: int) -> None:
    if not (0 <= seed <= MAX_SEED):
        raise ValueError(f"seed must be in [0, {MAX_SEED}], got {seed}")


def _request(path: str, params: dict) -> tuple[int, ...]:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        raise ApiError(f"API returned {e.code} for {url}: {e.read().decode()!r}") from e
    except urllib.error.URLError as e:
        raise ApiError(f"failed to reach {url}: {e.reason}") from e

    try:
        results = json.loads(body)
    except json.JSONDecodeError as e:
        raise ApiError(f"API returned non-JSON body for {url}: {body!r}") from e

    pattern = [None] * len(results)
    for item in results:
        pattern[item["slot"]] = _RESULT_TO_SCORE[item["result"]]
    return tuple(pattern)


def guess_random(guess: str, seed: int) -> tuple[int, ...]:
    """Guess against a random secret determined by `seed` (reuse the same
    seed across every guess in one game -- omitting it draws a new secret
    per call)."""
    _validate_guess(guess, WORD_SIZE)
    _validate_seed(seed)
    return _request("/random", {"guess": guess, "size": WORD_SIZE, "seed": seed})


def guess_daily(guess: str) -> tuple[int, ...]:
    """Guess against today's daily puzzle."""
    _validate_guess(guess, WORD_SIZE)
    return _request("/daily", {"guess": guess, "size": WORD_SIZE})


def guess_word(word: str, guess: str) -> tuple[int, ...]:
    """Guess against a directly-specified secret word."""
    _validate_guess(guess, len(word))
    return _request(f"/word/{urllib.parse.quote(word)}", {"guess": guess})
