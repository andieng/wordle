# Wordle Solver

A Python Wordle solver that plays against the live API at
[wordle.votee.dev](https://wordle.votee.dev:8000), with a colored terminal
board and keyboard. No third-party dependencies -- Python 3 standard
library only.

## How it picks guesses

Two strategies, selected with `--strategy`:

- **`entropy`** (default): for each candidate guess, picks the one minimizing
  *expected total remaining guesses*, following 3Blue1Brown's own formula:
  `prob*1 + (1-prob)*(1 + entropy_to_expected_score(H0 - H1))`, where `H0`
  is the current uncertainty (`log2(candidates remaining)`), `H1` is the
  guess's own Shannon entropy, and `prob` is `1/n` if the guess is itself a
  candidate (credit for a chance to win outright) or `0` otherwise --
  3Blue1Brown's own *default* prior is a binary real-answer indicator,
  which reduces to exactly this uniform `1/n`, not continuous real-word
  frequency. Since `H0` is fixed per candidate set and the regression is
  monotonic, this is provably close to plain entropy maximization with a
  candidacy tie-break, but expressed as a proper formula rather than an
  arbitrary epsilon -- so a genuinely large entropy edge for a non-candidate
  can still (correctly) outweigh a candidate's small win-probability credit,
  which a boolean tie-break can't express.

  Real per-word frequency (`src/data/word_freq.json`, 3Blue1Brown's
  `freq_map.json`) only comes in for genuine exact ties that remain after
  that -- e.g. two remaining candidates always split into two singleton
  buckets with identical entropy and identical `1/n` win probability,
  whichever you guess, so without a further tie-break the choice between a
  common word and an obsolete one is arbitrary/list-order-dependent. See
  `tests/test_solver.py::TestBestEntropyGuess` for a concrete demonstration,
  and `best_entropy_guess` in `src/solver.py` for the full derivation.

  **This took two iterations to get right, validated by a 2,309-game local
  benchmark (every answer as the secret) each time**: continuously blending
  *real* word frequency into the formula -- whether weighting the entropy
  calculation itself, or even just the win-probability term alone with
  entropy left uniform -- measurably hurt performance (3.84-3.86 vs 3.61
  average guesses, ~98% vs 99.4% win rate), because a small win-probability
  credit for a common word can outweigh a genuinely stronger split at
  *every* turn, not just true endgame ties, quietly eroding overall guess
  quality; the live API's secrets also don't appear to be frequency-biased
  in the first place. The uniform-probability formula above benchmarked
  identically to a simpler boolean/epsilon tie-break (3.614 avg, 2296/2309
  wins) -- no regression, just a more principled derivation with one fewer
  arbitrary constant -- and real frequency stays reserved for exact ties
  only.
- **`frequency`**: a faster, weaker heuristic (no simulation) that scores
  words by per-position letter frequency among the remaining candidates --
  useful mainly as an automatic fallback when the candidate pool is too
  large to run the full simulation on every guess (`--entropy-max-candidates`).

The first guess is precomputed offline (see below) since scoring the full
~13,000-word guess list against ~2,300 candidates is too slow to do live;
every guess after that is computed live in milliseconds once the candidate
set has narrowed.

## Word lists

`src/data/answers.txt` (2,309 words) and `src/data/guesses.txt` (12,953
words) are the official NYT Wordle word lists, taken from 3Blue1Brown's
[`videos`](https://github.com/3b1b/videos) repo
(`_2022/wordle/data/{possible,allowed}_words.txt`). `answers.txt` is the
solver's candidate pool; `guesses.txt` is the broader pool used only for
the one-time first-guess precomputation.

**The live API doesn't restrict its secrets (or accepted guesses) to any
fixed word list** -- it can generate proper nouns (confirmed live, e.g. a
secret of `katie`) and will score any 5-letter guess string without
dictionary-validating it. So the solver never just gives up when a word
isn't in our lists; it's layered in three tiers, tried in order:

1. `answers.txt` (2,309 words) -- the common case, fast and few guesses.
2. `guesses.txt` (12,953 words) -- a wider net for real words outside the
   curated answer list.
3. A raw per-letter/per-position constraint model, updated from every
   guess independent of any word list. The API's scoring is a simple
   membership check (see `score_naive` below), so every result maps to an
   unambiguous, permanent fact -- "absent" means the letter is nowhere in
   the secret, "present"/"correct" means it definitely is -- letting the
   solver narrow down to the exact secret through direct letter probing
   even once both word lists are exhausted (see `WordleSolver._fallback_guess`
   in `src/solver.py`).

Because a standard Wordle game only allows 6 guesses, and 4 of those may
already be spent on dictionary attempts before the solver realizes the
word isn't in either list, tier 3 sometimes doesn't have enough guesses
left to both *discover* a rare letter and *place* it correctly -- this is
a genuine information-theoretic limit (verified: solving `katie` from a
completely blank slate via tier 3 alone takes 9 guesses), not a bug. It
will, however, solve any secret given enough attempts, and it meaningfully
outperforms giving up outright.

The API also scores repeated letters differently from official Wordle
rules (it marks a letter "present" if it appears anywhere in the secret,
without capping credit to the number of remaining copies -- see
`score_naive` in `src/feedback.py`). This was confirmed by probing the live
API directly and is accounted for throughout the solver.

## Usage

```bash
# Solve a random secret (fixed seed so the same secret persists across all guesses in the game)
python3 src/main.py --source random --seed 42

# Solve today's daily puzzle
python3 src/main.py --source daily

# Solve a specific word (useful for testing)
python3 src/main.py --source word --word mango

# Use the faster/weaker frequency heuristic instead of entropy
python3 src/main.py --source random --seed 42 --strategy frequency

# No animation delay between guesses
python3 src/main.py --source random --seed 42 --delay 0
```

Full options: `python3 src/main.py --help`.

## Project layout

```
src/
  words.py       word list + frequency data loading
  feedback.py    feedback scoring, pattern encode/decode, parsing
  api_client.py  thin client for the live Wordle API
  solver.py      candidate filtering + entropy/frequency guess selection
  cli.py         colored terminal board/keyboard rendering
  main.py        CLI entry point
  data/          word lists, frequency data, cached first-guess result
scripts/
  precompute_first_guess.py   one-time offline cache builder (re-run if word/frequency data changes)
tests/
  test_feedback.py   scoring, pattern encoding, feedback parsing
  test_solver.py      guess-selection strategies (entropy w/ frequency tie-break, frequency)
```

## Running tests

```bash
python3 -m unittest discover
```

## Regenerating the first-guess cache

Only needed if you change `src/data/answers.txt`, `guesses.txt`, or
`word_freq.json`:

```bash
python3 scripts/precompute_first_guess.py
```
