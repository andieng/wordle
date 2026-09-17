"""One-time offline computation of the entropy-optimal opening guess.

Scoring all 12,953 valid guesses against all 2,309 candidate answers is
O(guesses x candidates) (~30M pattern computations) -- too slow to run on
every solver invocation, so this script runs it once and caches the result
to data/first_guess_cache.json, keyed by a hash of the word list and
frequency data files so the cache self-invalidates if any of them change.

Run from the repo root: python3 scripts/precompute_first_guess.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from solver import FIRST_GUESS_CACHE, _words_hash, best_entropy_guess, entropy_of_guess
from words import load_answers, load_frequencies, load_guesses


def main() -> None:
    answers = list(load_answers())
    guesses = list(load_guesses())
    freq = load_frequencies()
    print(f"computing entropy-optimal first guess: {len(guesses)} guesses x {len(answers)} answers...")
    start = time.time()
    guess = best_entropy_guess(answers, guess_pool=guesses, freq=freq)
    entropy = entropy_of_guess(guess, answers)
    elapsed = time.time() - start
    print(f"best first guess: {guess!r} ({entropy:.3f} bits, {elapsed:.1f}s)")

    FIRST_GUESS_CACHE.write_text(
        json.dumps({"words_sha256": _words_hash(), "guess": guess, "entropy_bits": entropy})
        + "\n"
    )
    print(f"cached to {FIRST_GUESS_CACHE}")


if __name__ == "__main__":
    main()
