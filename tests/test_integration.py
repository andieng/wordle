"""Integration tests against the live API at https://wordle.votee.dev:8000.

Unlike test_feedback.py/test_solver.py (pure local logic, no network), these
tests make real HTTP calls end-to-end -- api_client parsing the live
response shape correctly, and the full WordleSolver loop actually
converging against a real secret. If the API is unreachable, the whole
module is skipped rather than failing the suite (see setUpModule).
"""

from __future__ import annotations

import unittest

from api_client import ApiError, guess_daily, guess_random, guess_word
from feedback import CORRECT
from solver import WordleSolver

MAX_GUESSES = 8  # generous cap; real dictionary answers should solve well under this


def setUpModule() -> None:
    try:
        guess_word("mango", "mango")
    except ApiError as e:
        raise unittest.SkipTest(f"live API unreachable: {e}")


def play(secret: str, strategy: str = "entropy", max_guesses: int = MAX_GUESSES) -> int | None:
    """Run a full solver game against a live /word/{secret} secret. Returns
    the number of guesses to solve, or None if not solved within max_guesses."""
    solver = WordleSolver(strategy=strategy)
    for attempt in range(1, max_guesses + 1):
        guess = solver.suggest(remaining_attempts=max_guesses - attempt + 1)
        pattern = guess_word(secret, guess)
        solver.filter(guess, pattern)
        if all(s == CORRECT for s in pattern):
            return attempt
    return None


class TestApiClient(unittest.TestCase):
    def test_guess_word_exact_match_is_all_correct(self):
        pattern = guess_word("mango", "mango")
        self.assertEqual(pattern, (CORRECT,) * 5)

    def test_guess_word_naive_scoring_credits_every_repeated_letter(self):
        # Confirms the live API's actual (non-official) scoring rule: a
        # repeated guess letter is credited every time it appears in the
        # secret, uncapped -- see feedback.score_naive. "mango" has one "a"
        # (at index 1, matched exactly by "aaaaa"'s index 1 -> correct), and
        # every other "a" in the guess is still credited present, not absent
        # as official Wordle rules would score it.
        pattern = guess_word("mango", "aaaaa")
        self.assertEqual(pattern.count(CORRECT) + pattern.count(1), 5)

    def test_guess_random_same_seed_is_deterministic(self):
        first = guess_random("crane", seed=12345)
        second = guess_random("crane", seed=12345)
        self.assertEqual(first, second)

    def test_guess_daily_returns_a_valid_pattern(self):
        pattern = guess_daily("crane")
        self.assertEqual(len(pattern), 5)
        self.assertTrue(all(s in (0, 1, 2) for s in pattern))

    def test_oversized_random_request_raises_api_error(self):
        # The API only has secrets up to 22 letters for /random; above that
        # it returns an Internal Server Error rather than a valid pattern.
        with self.assertRaises(ValueError):
            guess_random("a" * 23, seed=1, size=23)


class TestSolverEndToEnd(unittest.TestCase):
    def test_solves_a_known_answer_word(self):
        guesses = play("mango")
        self.assertIsNotNone(guesses, "solver failed to converge on a real answer word")
        self.assertLessEqual(guesses, MAX_GUESSES)

    def test_solves_a_word_with_a_repeated_letter(self):
        # "sassy" has a repeated letter, exercising the naive (uncapped)
        # duplicate-letter scoring path end-to-end against the live API.
        guesses = play("sassy")
        self.assertIsNotNone(guesses, "solver failed to converge on a repeated-letter word")
        self.assertLessEqual(guesses, MAX_GUESSES)

    def test_solves_with_frequency_strategy_too(self):
        guesses = play("board", strategy="frequency")
        self.assertIsNotNone(guesses, "frequency strategy failed to converge")
        self.assertLessEqual(guesses, MAX_GUESSES)


if __name__ == "__main__":
    unittest.main()
