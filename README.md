# Wordle Solver

A Python Wordle solver that plays against the live API at
[wordle.votee.dev](https://wordle.votee.dev:8000), with a colored terminal
board. No third-party dependencies -- Python 3 standard library only.

## How it picks guesses

Two strategies, selected with `--strategy`:

- **`entropy`** (default): simulates every candidate guess against the
  remaining candidates and picks the one minimizing expected total
  remaining guesses (3Blue1Brown's information-theoretic approach). Real
  word-usage frequency (`src/data/word_freq.json`) only breaks genuine
  ties -- see `best_entropy_guess` in `src/solver.py` for the full
  derivation and `tests/test_solver.py` for examples.
- **`frequency`**: a faster, weaker heuristic (no simulation) that scores
  words by per-position letter frequency among the remaining candidates --
  used automatically once the candidate pool is too large to simulate
  (`--entropy-max-candidates`).

The first guess is precomputed offline (see below), since scoring the full
~13,000-word guess list against ~2,300 candidates is too slow to do live;
every guess after that is computed live in milliseconds once the candidate
set has narrowed. When the entropy strategy runs, the solver also prints
its top 10 considered guesses ranked by raw Shannon entropy.

## Word lists and the three-tier fallback

`src/data/answers.txt` (2,309 words) and `src/data/guesses.txt` (12,953
words) are the official NYT Wordle word lists, from 3Blue1Brown's
[`videos`](https://github.com/3b1b/videos) repo
(`_2022/wordle/data/{possible,allowed}_words.txt`).

The live API doesn't restrict its secrets (or accepted guesses) to any
fixed word list -- it can generate proper nouns (confirmed live, e.g. a
secret of `katie`) and scores any guess string without dictionary
validation. So the solver never just gives up on an out-of-list word; it
tries three tiers in order:

1. `answers.txt` -- the common case, fast and few guesses.
2. `guesses.txt` -- a wider net for real words outside the curated list.
3. A raw per-letter/per-position constraint model, updated from every
   guess independent of any word list. Because the API's scoring is a
   simple membership check (see `score_naive` below), every result is an
   unambiguous, permanent fact about the secret, letting the solver narrow
   down to it through direct letter probing even once both word lists are
   exhausted (see `WordleSolver._fallback_guess`).

The curated lists are all 5-letter words, so a non-default `--size` drops
straight to tier 3.

The API also scores repeated letters differently from official Wordle
rules -- a letter is "present" if it appears anywhere in the secret, with
no cap on repeated-guess-letter credit (see `score_naive` in
`src/feedback.py`). This was confirmed by probing the live API directly.

There's no official 6-guess limit here -- the solver keeps guessing until
it solves the word or hits `--max-guesses` (default 20, just a sane cap
against a runaway game). Word length is configurable with `--size`
(default 5); `--source random`/`--source daily` are capped to `[1, 22]` by
the API itself, while `--source word` is uncapped and infers `--size` from
`--word`.

## Usage

```bash
# Solve a random secret (fixed seed so the same secret persists across all guesses in the game)
python3 src/main.py --source random --seed 42

# Solve today's daily puzzle
python3 src/main.py --source daily

# Solve a specific word (useful for testing)
python3 src/main.py --source word --word mango

# Solve a 7-letter random secret
python3 src/main.py --source random --seed 42 --size 7

# Use the faster/weaker frequency heuristic instead of entropy
python3 src/main.py --source random --seed 42 --strategy frequency

# No animation delay between guesses
python3 src/main.py --source random --seed 42 --delay 0

# Type your own guesses instead of letting the solver play -- the solver's
# top-10-by-entropy list and its own suggested guess are still shown as a hint
python3 src/main.py --source word --word mango --mode manual
```

Full options: `python3 src/main.py --help`.

## Project layout

```
src/
  words.py       word list + frequency data loading
  feedback.py    feedback scoring, pattern encode/decode, parsing
  api_client.py  thin client for the live Wordle API
  solver.py      candidate filtering + entropy/frequency guess selection
  cli.py         colored terminal board rendering
  main.py        CLI entry point
  data/          word lists, frequency data, cached first-guess result
scripts/
  precompute_first_guess.py   one-time offline cache builder (re-run if word/frequency data changes)
  benchmark.py                 local entropy-vs-frequency strategy benchmark (no network needed)
tests/
  test_feedback.py     scoring, pattern encoding, feedback parsing
  test_solver.py        guess-selection strategies (entropy w/ frequency tie-break, frequency)
  test_integration.py   end-to-end against the live API (see below)
```

## Running tests

```bash
python3 -m unittest discover
```

`test_feedback.py` and `test_solver.py` are pure local logic -- no network.
`test_integration.py` makes real HTTP calls to the live API and is skipped
automatically if the API is unreachable.

## Regenerating the first-guess cache

Only needed if you change `src/data/answers.txt`, `guesses.txt`, or
`word_freq.json`:

```bash
python3 scripts/precompute_first_guess.py
```
