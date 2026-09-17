"""Candidate filtering and guess selection for the Wordle solver.

The API doesn't restrict its secrets (or accepted guesses) to any fixed
word list -- it can generate proper nouns and other non-dictionary strings
(confirmed live, e.g. a secret of "katie"), and it will score any 5-letter
guess string without validating it against a dictionary. So the solver is
layered in three tiers, tried in order, so it never simply gives up just
because a word isn't in our lists:

  1. `candidates` (the curated 2,309-word answer list) -- fast, few
     guesses, human-readable, correct for the common case of a real
     Wordle-style answer.
  2. `broad_candidates` (the 12,953-word valid-guess list) -- a wider net
     for real words that aren't in the curated answer list.
  3. A raw per-letter constraint model (`known_in`/`known_out`/
     `position_letters`), updated from every guess independent of any word
     list. Because the API's scoring is a simple membership check (see
     `feedback.score_naive`), every piece of feedback maps to an
     unambiguous, permanent fact about the secret -- a letter marked
     absent is never in the secret at all, and a letter marked
     present/correct always is -- so this model narrows down to the exact
     secret through direct letter-by-letter probing even when tiers 1 and
     2 are both exhausted.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from math import log2
from pathlib import Path

from feedback import CORRECT, PRESENT, encode_pattern, score_naive
from words import ANSWERS_FILE, GUESSES_FILE, WORD_FREQ_FILE, load_answers, load_frequencies, load_guesses

FIRST_GUESS_CACHE = Path(__file__).parent / "data" / "first_guess_cache.json"

_ALPHABET = set("abcdefghijklmnopqrstuvwxyz")
# Approximate English letter frequency, most common first -- used to prioritize
# which untested letter to probe first when constructing a raw fallback guess.
_FREQ_ORDER = "etaoinshrdlcumwfgypbvkjxqz"


def entropy_of_guess(guess: str, candidates: list[str]) -> float:
    """Expected information gain (bits) from guessing `guess` against `candidates`."""
    n = len(candidates)
    buckets = Counter(encode_pattern(score_naive(guess, secret)) for secret in candidates)
    return -sum((c / n) * log2(c / n) for c in buckets.values())


def compute_entropies(candidates: list[str], guess_pool: list[str]) -> dict[str, float]:
    """Shannon entropy (bits) for every guess in `guess_pool` against `candidates`,
    computed once so callers that need both a ranked list (e.g. a "top 10 by
    entropy" display) and the best-guess pick don't redo the same work."""
    return {guess: entropy_of_guess(guess, candidates) for guess in guess_pool}


def top_entropy_guesses(
    candidates: list[str], guess_pool: list[str], n: int = 10, entropies: dict[str, float] | None = None
) -> list[tuple[str, float]]:
    """Return the `n` guesses in `guess_pool` with the highest raw entropy
    against `candidates` (ties broken alphabetically for determinism)."""
    if entropies is None:
        entropies = compute_entropies(candidates, guess_pool)
    ranked = sorted(entropies.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:n]


def entropy_to_expected_score(ent: float) -> float:
    """Regression (from 3Blue1Brown's Wordle analysis) mapping "bits of
    entropy remaining after a guess" to "expected number of further guesses
    needed", calibrated against his simulated games. Monotonically
    increasing: more remaining uncertainty -> more expected guesses."""
    min_score = 2 ** (-ent) + 2 * (1 - 2 ** (-ent))
    return min_score + 1.5 * ent / 11.5


def best_entropy_guess(
    candidates: list[str],
    guess_pool: list[str],
    freq: dict[str, float] | None = None,
    epsilon: float = 1e-9,
    entropies: dict[str, float] | None = None,
) -> str:
    """Return the guess in `guess_pool` minimizing expected total remaining
    guesses against `candidates`, following 3Blue1Brown's own formula:

        expected(guess) = prob*1 + (1-prob)*(1 + entropy_to_expected_score(H0 - H1))

    where H0 = log2(n) is the current uncertainty (n = len(candidates)), H1
    is this guess's entropy (`entropy_of_guess`), and `prob` is `1/n` if the
    guess is itself a candidate (a chance to win outright) else 0 --
    3Blue1Brown's own *default* prior (`get_true_wordle_prior`, a binary
    real-answer indicator) reduces to exactly this uniform 1/n, not a
    continuous real-word-frequency weighting: benchmarking showed that
    blending in real frequency (whether into the entropy calculation or
    just this probability term) measurably hurts average guesses, since a
    common word's small win-probability credit can outweigh a genuinely
    stronger split even outside true endgame ties.

    Genuine exact ties remain (e.g. 2 remaining candidates always split into
    2 singleton buckets with identical entropy and identical 1/n win
    probability, whichever you guess) and are broken by `freq`, when given:
    prefer the guess more likely to actually be the secret by real-world
    usage, rather than an arbitrary/list-order-dependent pick.
    """
    n = len(candidates)
    h0 = log2(n)
    candidate_set = set(candidates)
    if entropies is None:
        entropies = compute_entropies(candidates, guess_pool)

    scores: dict[str, float] = {}
    for guess in guess_pool:
        h1 = entropies[guess]
        prob = (1.0 / n) if guess in candidate_set else 0.0
        scores[guess] = prob * 1 + (1 - prob) * (1 + entropy_to_expected_score(h0 - h1))

    best_score = min(scores.values())
    tied = [g for g, s in scores.items() if s <= best_score + epsilon]

    if freq is not None:
        return max(tied, key=lambda w: (freq.get(w, 0.0), w in candidate_set))
    return max(tied, key=lambda w: (w in candidate_set,))


def best_frequency_guess(candidates: list[str]) -> str:
    """Fast heuristic: score each candidate by summed per-position letter
    frequency across the remaining candidates, pick the highest."""
    position_counts = [Counter(word[i] for word in candidates) for i in range(5)]
    best_word = None
    best_score = -1
    for word in candidates:
        s = sum(position_counts[i][ch] for i, ch in enumerate(word))
        if s > best_score:
            best_score = s
            best_word = word
    return best_word


def _words_hash() -> str:
    h = hashlib.sha256()
    h.update(ANSWERS_FILE.read_bytes())
    h.update(GUESSES_FILE.read_bytes())
    h.update(WORD_FREQ_FILE.read_bytes())
    return h.hexdigest()


def _load_cached_first_guess() -> str | None:
    if not FIRST_GUESS_CACHE.exists():
        return None
    try:
        data = json.loads(FIRST_GUESS_CACHE.read_text())
    except json.JSONDecodeError:
        return None
    if data.get("words_sha256") != _words_hash():
        return None
    return data.get("guess")


class WordleSolver:
    def __init__(self, strategy: str = "entropy", entropy_max_candidates: int = 2000, size: int = 5):
        self.strategy = strategy
        self.entropy_max_candidates = entropy_max_candidates
        self.size = size
        # The curated word lists are all 5-letter NYT Wordle words -- for any
        # other size they're filtered down (usually to empty), and the
        # solver naturally drops straight to the tier-3 constraint model,
        # which works for any word length.
        self.candidates: list[str] = [w for w in load_answers() if len(w) == size]
        self.broad_candidates: list[str] = [w for w in load_guesses() if len(w) == size]
        self._full_size = len(load_answers()) if size == 5 else -1
        self.freq: dict[str, float] = load_frequencies()
        self.last_top_entropy: list[tuple[str, float]] = []

        # Raw letter/position constraint model -- always kept up to date,
        # used as the last-resort tier once both word lists are exhausted.
        self.known_in: set[str] = set()
        self.known_out: set[str] = set()
        self.position_letters: list[set[str]] = [set(_ALPHABET) for _ in range(size)]

    def filter(self, guess: str, pattern: tuple[int, ...]) -> list[str]:
        self.candidates = [c for c in self.candidates if score_naive(guess, c) == pattern]
        self.broad_candidates = [c for c in self.broad_candidates if score_naive(guess, c) == pattern]
        self._update_constraints(guess, pattern)
        return self.candidates

    def _update_constraints(self, guess: str, pattern: tuple[int, ...]) -> None:
        for i, (ch, s) in enumerate(zip(guess, pattern)):
            if s == CORRECT:
                self.position_letters[i] = {ch}
                self.known_in.add(ch)
            elif s == PRESENT:
                self.position_letters[i].discard(ch)
                self.known_in.add(ch)
            else:  # ABSENT: the letter is not in the secret at all (naive scoring).
                self.known_out.add(ch)
                for pl in self.position_letters:
                    pl.discard(ch)

    def is_solved(self) -> bool:
        return all(len(pl) == 1 for pl in self.position_letters)

    def _suggest_from_pool(self, pool: list[str]) -> str:
        if len(pool) == 1:
            self.last_top_entropy = [(pool[0], 0.0)]
            return pool[0]
        if self.strategy == "frequency" or len(pool) > self.entropy_max_candidates:
            self.last_top_entropy = []
            return best_frequency_guess(pool)
        entropies = compute_entropies(pool, pool)
        self.last_top_entropy = top_entropy_guesses(pool, pool, entropies=entropies)
        return best_entropy_guess(pool, guess_pool=pool, freq=self.freq, entropies=entropies)

    def _fallback_guess(self) -> str:
        """Construct a guess directly from the constraint model, for when the
        secret isn't in either word list.

        Key idea: an "absent" result eliminates a letter globally, regardless
        of which slot it was tested in -- so once some positions are already
        resolved, re-confirming their known letter every guess wastes a slot
        that could instead test a brand-new letter. So every guess here fills
        as many of the `self.size` slots as possible with untested letters
        (to learn up to `self.size` new membership facts per guess),
        reserving slots only for known-in letters that still need to find
        their position. Only once the whole alphabet has been tested does it
        fall back to the known possible letters (which by then should be
        fully resolved anyway).
        """
        if self.is_solved():
            return "".join(next(iter(pl)) for pl in self.position_letters)

        placed = {next(iter(pl)) for pl in self.position_letters if len(pl) == 1}
        unplaced_known_in = self.known_in - placed
        untested_priority = [l for l in _FREQ_ORDER if l not in self.known_in and l not in self.known_out]

        letters: list[str | None] = [None] * self.size
        used: set[str] = set()

        # Tier 1: place each still-homeless known-in letter at an unresolved
        # position where it's still a valid candidate.
        for i in range(self.size):
            if len(self.position_letters[i]) == 1:
                continue
            for l in sorted(self.position_letters[i]):
                if l in unplaced_known_in and l not in used:
                    letters[i] = l
                    used.add(l)
                    unplaced_known_in.discard(l)
                    break

        # Tier 2: fill every remaining slot (resolved or not) with a fresh
        # untested letter, prioritizing common English letters, to maximize
        # new information from this one guess.
        untested_iter = iter(untested_priority)
        for i in range(self.size):
            if letters[i] is not None:
                continue
            candidate = next((l for l in untested_iter if l not in used), None)
            if candidate is None:
                possible = self.position_letters[i]
                remaining = [l for l in sorted(possible) if l not in used]
                candidate = remaining[0] if remaining else next(iter(possible))
            letters[i] = candidate
            used.add(candidate)

        return "".join(letters)

    def suggest(self, remaining_attempts: int | None = None) -> str:
        if self.candidates:
            if self.strategy == "entropy" and len(self.candidates) == self._full_size:
                cached = _load_cached_first_guess()
                if cached is not None:
                    self.last_top_entropy = []
                    return cached
                print(
                    "note: no first-guess cache found "
                    "(run scripts/precompute_first_guess.py); "
                    "falling back to the frequency heuristic for this guess"
                )
                self.last_top_entropy = []
                return best_frequency_guess(self.candidates)
            return self._suggest_from_pool(self.candidates)

        unresolved = sum(1 for pl in self.position_letters if len(pl) > 1)

        # Once attempts are tight relative to how many positions are still
        # unresolved, prefer the constraint model: every fallback guess is
        # guaranteed to narrow at least one position or eliminate a letter
        # outright, whereas another dictionary guess might be a real word
        # that simply happens to be wrong, burning an attempt without
        # guaranteed progress.
        if remaining_attempts is not None and remaining_attempts <= unresolved:
            print(
                "note: running low on attempts relative to unresolved letters; "
                "solving directly from letter/position constraints"
            )
            self.last_top_entropy = []
            return self._fallback_guess()

        if self.broad_candidates:
            print(
                "note: secret isn't in the curated answer list; "
                "widening to the full valid-guess dictionary"
            )
            return self._suggest_from_pool(self.broad_candidates)

        print(
            "note: secret isn't in either word list (likely a proper noun); "
            "solving directly from letter/position constraints"
        )
        self.last_top_entropy = []
        return self._fallback_guess()
