"""Offline benchmark comparing the entropy and frequency strategies.

Simulates solving every (or a sampled subset of) word in the answer list
against the solver, scoring guesses locally with `score_naive` -- no live
API calls needed, since the API's scoring rules are fully reproduced
offline. Reports win rate, guess-count distribution, and wall-clock time
per strategy so the entropy/frequency trade-off (stronger but slower vs.
weaker but faster) can be measured concretely instead of taken on faith.

Run from the repo root: python3 scripts/benchmark.py
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from feedback import score_naive
from solver import WordleSolver
from words import load_answers

MAX_ATTEMPTS = 6


def solve_one(strategy: str, secret: str, entropy_max_candidates: int) -> int | None:
    """Return the number of guesses to solve `secret`, or None if it fails
    within MAX_ATTEMPTS."""
    solver = WordleSolver(strategy=strategy, entropy_max_candidates=entropy_max_candidates)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        guess = solver.suggest(remaining_attempts=MAX_ATTEMPTS - attempt + 1)
        pattern = score_naive(guess, secret)
        solver.filter(guess, pattern)
        if all(s == 2 for s in pattern):
            return attempt
    return None


def run_benchmark(strategy: str, secrets: list[str], entropy_max_candidates: int) -> dict:
    results: list[int | None] = []
    start = time.time()
    for secret in secrets:
        results.append(solve_one(strategy, secret, entropy_max_candidates))
    elapsed = time.time() - start

    solved = [r for r in results if r is not None]
    failed = len(results) - len(solved)
    distribution = Counter(solved)

    return {
        "strategy": strategy,
        "n": len(secrets),
        "solved": len(solved),
        "failed": failed,
        "win_rate": len(solved) / len(secrets),
        "avg_guesses": statistics.mean(solved) if solved else float("nan"),
        "median_guesses": statistics.median(solved) if solved else float("nan"),
        "distribution": distribution,
        "elapsed": elapsed,
        "avg_time_per_game": elapsed / len(secrets),
    }


def print_report(stats: dict) -> None:
    print(f"\n=== {stats['strategy']} ===")
    print(f"  words tested:       {stats['n']}")
    print(f"  solved:             {stats['solved']} ({stats['win_rate']:.1%})")
    print(f"  failed (>{MAX_ATTEMPTS} guesses): {stats['failed']}")
    print(f"  avg guesses:        {stats['avg_guesses']:.3f}")
    print(f"  median guesses:     {stats['median_guesses']}")
    print(f"  guess distribution: " + ", ".join(
        f"{k}:{stats['distribution'][k]}" for k in sorted(stats["distribution"])
    ))
    print(f"  total time:         {stats['elapsed']:.1f}s")
    print(f"  avg time/game:      {stats['avg_time_per_game'] * 1000:.1f}ms")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy", choices=["frequency", "entropy", "both"], default="both",
        help="which strategy to benchmark (default: both)",
    )
    parser.add_argument(
        "--sample", type=int, default=None,
        help="benchmark a random sample of N answer words instead of the full list "
        "(useful for a quick check, since entropy is much slower)",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed for --sample (default: 0)")
    parser.add_argument(
        "--entropy-max-candidates", type=int, default=2000,
        help="fall back to the frequency heuristic above this many candidates (default: 2000)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    answers = list(load_answers())

    if args.sample is not None:
        secrets = random.Random(args.seed).sample(answers, min(args.sample, len(answers)))
    else:
        secrets = answers

    strategies = ["frequency", "entropy"] if args.strategy == "both" else [args.strategy]

    print(f"benchmarking {len(secrets)} secret(s): {', '.join(strategies)}")
    for strategy in strategies:
        stats = run_benchmark(strategy, secrets, args.entropy_max_candidates)
        print_report(stats)

    return 0


if __name__ == "__main__":
    sys.exit(main())
