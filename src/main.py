"""CLI entry point: solves a live Wordle game via https://wordle.votee.dev:8000."""

from __future__ import annotations

import argparse
import random
import sys
import time

from api_client import MAX_SEED, ApiError, guess_daily, guess_random, guess_word
from cli import render_board, render_keyboard, status_line
from solver import WordleSolver

MAX_ATTEMPTS = 6


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", choices=["random", "daily", "word"], default="random",
        help="which API endpoint to solve against (default: random)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="seed for --source random (0-4294967295); auto-generated and reused "
        "for the whole game if omitted",
    )
    parser.add_argument("--word", help="secret word for --source word")
    parser.add_argument(
        "--strategy", choices=["frequency", "entropy"], default="entropy",
        help="guess-selection strategy (default: entropy)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.6, help="seconds between guesses (default: 0.6)"
    )
    parser.add_argument(
        "--entropy-max-candidates", type=int, default=2000,
        help="fall back to the frequency heuristic above this many candidates (default: 2000)",
    )
    args = parser.parse_args(argv)

    if args.source == "word" and not args.word:
        parser.error("--source word requires --word")
    if args.seed is not None and not (0 <= args.seed <= MAX_SEED):
        parser.error(f"--seed must be in [0, {MAX_SEED}]")
    return args


def make_guesser(args: argparse.Namespace):
    if args.source == "daily":
        return guess_daily
    if args.source == "word":
        return lambda guess: guess_word(args.word, guess)

    seed = args.seed if args.seed is not None else random.randint(0, MAX_SEED)
    print(status_line(f"using seed={seed}", "cyan"))
    return lambda guess: guess_random(guess, seed)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    guesser = make_guesser(args)
    solver = WordleSolver(strategy=args.strategy, entropy_max_candidates=args.entropy_max_candidates)

    history: list[tuple[str, tuple[int, ...]]] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        guess = solver.suggest(remaining_attempts=MAX_ATTEMPTS - attempt + 1)
        try:
            pattern = guesser(guess)
        except (ApiError, ValueError) as e:
            print(status_line(f"error: {e}", "red"), file=sys.stderr)
            return 1

        history.append((guess, pattern))
        solver.filter(guess, pattern)

        print()
        print(status_line(f"Guess {attempt}: {guess}", "cyan"))
        print(render_board(history))
        print()
        print(render_keyboard(history))

        if all(s == 2 for s in pattern):
            print()
            print(status_line(f"Solved in {attempt} guess{'es' if attempt != 1 else ''}!", "green"))
            return 0

        time.sleep(args.delay)

    print()
    print(status_line(f"Failed to solve within {MAX_ATTEMPTS} guesses.", "red"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
