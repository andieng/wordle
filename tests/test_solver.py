import unittest

from solver import best_entropy_guess, best_frequency_guess, entropy_of_guess


class TestEntropyOfGuess(unittest.TestCase):
    def test_perfect_split_has_max_entropy_for_pool_size(self):
        # Guessing "abcde" against these 4 candidates produces 4 distinct
        # patterns (hand-verified): abcde->(2,2,2,2,2), fbcde->(0,2,2,2,2),
        # fgcde->(0,0,2,2,2), fghde->(0,0,0,2,2). 4 singleton buckets ->
        # entropy log2(4) == 2.0 bits, the max possible for a 4-way split.
        candidates = ["abcde", "fbcde", "fgcde", "fghde"]
        entropy = entropy_of_guess("abcde", candidates)
        self.assertAlmostEqual(entropy, 2.0, places=6)

    def test_uninformative_guess_has_zero_entropy(self):
        # If every candidate produces the identical feedback pattern against
        # a guess, that guess carries zero information (one bucket, p=1).
        candidates = ["abcde"]
        self.assertEqual(entropy_of_guess("zzzzz", candidates), 0.0)


class TestBestEntropyGuess(unittest.TestCase):
    def test_picks_the_maximally_informative_guess(self):
        candidates = ["abcde", "fbcde", "fgcde", "fghde"]
        # "zzzzz" shares no letters with any candidate -> produces the same
        # all-absent pattern for all 4, i.e. zero information.
        guess_pool = candidates + ["zzzzz"]
        best = best_entropy_guess(candidates, guess_pool)
        self.assertAlmostEqual(entropy_of_guess(best, candidates), 2.0, places=6)
        self.assertNotEqual(best, "zzzzz")

    def test_ties_prefer_a_word_that_is_itself_a_candidate(self):
        # candidates "abcde"/"fghij" (disjoint letters): guessing "abcde"
        # gives patterns (2,2,2,2,2) vs (0,0,0,0,0) -- entropy 1.0.
        # "aghij" (not a candidate) gives (2,0,0,0,0) vs (0,2,2,2,2) against
        # the same two candidates -- also entropy 1.0, a genuine tie.
        candidates = ["abcde", "fghij"]
        guess_pool = ["abcde", "aghij"]
        self.assertEqual(best_entropy_guess(candidates, guess_pool), "abcde")

    def test_ties_prefer_the_more_common_word_when_frequency_given(self):
        # "fresh"/"wroth" both split this 2-candidate set into 2 singleton
        # buckets (entropy exactly 1.0 either way) -- without frequency
        # data the tie-break is arbitrary/list-order-dependent (see below);
        # with it, the far more common "fresh" should always win regardless
        # of list order.
        freq = {"fresh": 5.5e-05, "wroth": 6.9e-07}
        self.assertEqual(
            best_entropy_guess(["fresh", "wroth"], ["fresh", "wroth"], freq=freq), "fresh"
        )
        self.assertEqual(
            best_entropy_guess(["wroth", "fresh"], ["wroth", "fresh"], freq=freq), "fresh"
        )

    def test_tie_break_is_order_dependent_without_frequency_data(self):
        # Documents the arbitrary-tie-break behavior that motivated adding
        # the `freq` parameter above: with no frequency data, whichever
        # equally-informative candidate appears first in the pool wins.
        self.assertEqual(best_entropy_guess(["wroth", "fresh"], ["wroth", "fresh"]), "wroth")
        self.assertEqual(best_entropy_guess(["fresh", "wroth"], ["fresh", "wroth"]), "fresh")


class TestBestFrequencyGuess(unittest.TestCase):
    def test_picks_word_with_most_common_letters_by_position(self):
        candidates = ["black", "crack", "track", "stack"]
        # "track" and others share the "ack" suffix; the heuristic should at
        # least return one of the actual candidates, never an outside word.
        self.assertIn(best_frequency_guess(candidates), candidates)

    def test_single_candidate_returns_itself(self):
        self.assertEqual(best_frequency_guess(["only1"]), "only1")


if __name__ == "__main__":
    unittest.main()
