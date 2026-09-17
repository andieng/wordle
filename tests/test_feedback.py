import unittest

from feedback import (
    decode_pattern,
    encode_pattern,
    parse_feedback,
    score_naive,
)


class TestScoreNaive(unittest.TestCase):
    """Matches the live votee.dev API: "present" is plain membership in the
    secret, with no cap on repeated-letter credit. Expected values below were
    cross-checked against real responses from https://wordle.votee.dev:8000."""

    def test_repeated_guess_letter_all_credited(self):
        # secret "mango" has one "a"; API marked the other four "a"s present too.
        self.assertEqual(score_naive("aaaaa", "mango"), (1, 2, 1, 1, 1))

    def test_repeated_guess_letter_single_secret_copy(self):
        # secret "rebus" has one "r"; API marked all five guess "r"s as correct/present.
        self.assertEqual(score_naive("rrrrr", "rebus"), (2, 1, 1, 1, 1))

    def test_secret_has_fewer_copies_than_guess(self):
        # secret "speed" has two "e"s; guess "eerie" has three -> naive still
        # credits all three as present (no capping), unlike official rules.
        self.assertEqual(score_naive("eerie", "speed"), (1, 1, 0, 0, 1))

    def test_no_repeats_case(self):
        self.assertEqual(score_naive("babel", "abbey"), (1, 1, 2, 2, 0))


class TestPatternEncoding(unittest.TestCase):
    def test_round_trip(self):
        for pattern in [(0, 0, 0, 0, 0), (2, 2, 2, 2, 2), (0, 1, 2, 1, 0), (1, 0, 2, 0, 1)]:
            self.assertEqual(decode_pattern(encode_pattern(pattern)), pattern)

    def test_encoding_is_injective_over_all_patterns(self):
        import itertools

        seen = set()
        for pattern in itertools.product((0, 1, 2), repeat=5):
            code = encode_pattern(pattern)
            self.assertNotIn(code, seen)
            seen.add(code)
        self.assertEqual(len(seen), 3**5)


class TestParseFeedback(unittest.TestCase):
    def test_parses_dash_style(self):
        self.assertEqual(parse_feedback("g-y-x"), (2, 0, 1, 0, 0))

    def test_parses_letter_style_case_insensitive(self):
        self.assertEqual(parse_feedback("GXYXX"), (2, 0, 1, 0, 0))

    def test_wrong_length_raises(self):
        with self.assertRaises(ValueError):
            parse_feedback("gg")

    def test_invalid_character_raises(self):
        with self.assertRaises(ValueError):
            parse_feedback("g-y-q")


if __name__ == "__main__":
    unittest.main()
