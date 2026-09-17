"""CLI entry point: solves a live Wordle game via https://wordle.votee.dev:8000."""

from __future__ import annotations

import argparse
import random
import sys
import time

from api_client import MAX_SEED, MAX_SIZE, MIN_SIZE, ApiError, guess_daily, guess_random, guess_word
from cli import render_board, status_line
from solver import WordleSolver

DEFAULT_MAX_GUESSES = 20


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
        "--size", type=int, default=5,
        help=f"word length (default: 5). --source random/daily are capped at "
        f"[{MIN_SIZE}, {MAX_SIZE}] by the API; --source word is uncapped and "
        "inferred from --word if not given",
    )
    parser.add_argument(
        "--mode", choices=["solver", "manual"], default="solver",
        help="'solver' auto-plays with the solver's suggestions (default); "
        "'manual' lets you type your own guesses, with the solver's analysis "
        "shown alongside as a hint",
    )
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
    parser.add_argument(
        "--max-guesses", type=int, default=DEFAULT_MAX_GUESSES,
        help=f"give up after this many guesses (default: {DEFAULT_MAX_GUESSES}); "
        "not an official Wordle rule, just a sane cap against runaway games",
    )
    args = parser.parse_args(argv)

    if args.source == "word" and not args.word:
        parser.error("--source word requires --word")
    if args.source == "word" and args.word:
        args.size = len(args.word)
    if args.seed is not None and not (0 <= args.seed <= MAX_SEED):
        parser.error(f"--seed must be in [0, {MAX_SEED}]")
    if args.source in ("random", "daily") and not (MIN_SIZE <= args.size <= MAX_SIZE):
        parser.error(f"--size must be in [{MIN_SIZE}, {MAX_SIZE}] for --source {args.source}")
    if args.size < 1:
        parser.error("--size must be at least 1")
    if args.max_guesses < 1:
        parser.error("--max-guesses must be at least 1")
    return args


def make_guesser(args: argparse.Namespace):
    if args.source == "daily":
        return lambda guess: guess_daily(guess, size=args.size)
    if args.source == "word":
        return lambda guess: guess_word(args.word, guess)

    seed = args.seed if args.seed is not None else random.randint(0, MAX_SEED)
    print(status_line(f"using seed={seed}", "cyan"))
    return lambda guess: guess_random(guess, seed, size=args.size)


def print_top_entropy(solver: WordleSolver) -> None:
    if not solver.last_top_entropy:
        return
    ranked = ", ".join(f"{w} ({e:.2f} bits)" for w, e in solver.last_top_entropy)
    print(status_line(f"Top {len(solver.last_top_entropy)} by entropy: {ranked}", "yellow"))


def run_solver_mode(args: argparse.Namespace, guesser) -> int:
    solver = WordleSolver(strategy=args.strategy, entropy_max_candidates=args.entropy_max_candidates, size=args.size)

    history: list[tuple[str, tuple[int, ...]]] = []
    for attempt in range(1, args.max_guesses + 1):
        guess = solver.suggest(remaining_attempts=args.max_guesses - attempt + 1)
        print_top_entropy(solver)
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

        if all(s == 2 for s in pattern):
            print()
            print(status_line(f"Solved in {attempt} guess{'es' if attempt != 1 else ''}!", "green"))
            return 0

        time.sleep(args.delay)

    print()
    print(status_line(f"Failed to solve within {args.max_guesses} guesses.", "red"))
    return 1


def run_manual_mode(args: argparse.Namespace, guesser) -> int:
    solver = WordleSolver(strategy=args.strategy, entropy_max_candidates=args.entropy_max_candidates, size=args.size)

    history: list[tuple[str, tuple[int, ...]]] = []
    attempt = 0
    while attempt < args.max_guesses:
        attempt += 1
        n_candidates = len(solver.candidates) or len(solver.broad_candidates)
        if n_candidates:
            print(status_line(f"{n_candidates} candidate word(s) remain.", "yellow"))
        suggested = solver.suggest(remaining_attempts=args.max_guesses - attempt + 1)
        print_top_entropy(solver)
        print(status_line(f"(solver would guess: {suggested})", "yellow"))

        guess = input(f"Guess {attempt} (word of length {args.size}): ").strip().lower()
        if len(guess) != args.size:
            print(status_line(f"error: guess must be {args.size} letters", "red"))
            attempt -= 1
            continue

        try:
            pattern = guesser(guess)
        except (ApiError, ValueError) as e:
            print(status_line(f"error: {e}", "red"))
            attempt -= 1
            continue

        history.append((guess, pattern))
        solver.filter(guess, pattern)

        print()
        print(render_board(history))
        print()

        if all(s == 2 for s in pattern):
            print(status_line(f"Solved in {attempt} guess{'es' if attempt != 1 else ''}!", "green"))
            return 0

    print(status_line(f"Failed to solve within {args.max_guesses} guesses.", "red"))
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    guesser = make_guesser(args)
    if args.mode == "manual":
        return run_manual_mode(args, guesser)
    return run_solver_mode(args, guesser)


if __name__ == "__main__":
    sys.exit(main())
