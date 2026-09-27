import unittest

from crlf_line_folder import fold_line, fold_header
from crlf_line_folder.core import FoldError


class TestFoldLineShort(unittest.TestCase):
    """Lines at or under the limit pass through unchanged."""

    def test_short_line_unchanged(self):
        self.assertEqual(fold_line("Subject: Hi"), "Subject: Hi")

    def test_exactly_max_len_unchanged(self):
        line = "x" * 78
        self.assertEqual(fold_line(line), line)

    def test_empty_line(self):
        self.assertEqual(fold_line(""), "")


class TestFoldLineBasic(unittest.TestCase):
    """Basic folding at whitespace boundaries."""

    def test_folds_at_space(self):
        # 80 chars, space at position 40.
        line = "a" * 40 + " " + "b" * 39
        result = fold_line(line)
        parts = result.split("\r\n ")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "a" * 40)
        self.assertEqual(parts[1], "b" * 39)
        # Every physical line within budget.
        for p in result.split("\r\n"):
            self.assertLessEqual(len(p), 78)

    def test_folds_at_tab(self):
        line = "a" * 40 + "\t" + "b" * 39
        result = fold_line(line)
        parts = result.split("\r\n ")
        self.assertEqual(parts[0], "a" * 40)
        self.assertEqual(parts[1], "b" * 39)

    def test_multiple_wraps(self):
        # 200 chars with spaces every 50.
        words = ["w" * 49 for _ in range(4)]
        line = " ".join(words)  # 49*4 + 3 = 199
        result = fold_line(line)
        for p in result.split("\r\n"):
            self.assertLessEqual(len(p), 78)
        # No content lost.
        rejoined = result.replace("\r\n ", " ")
        self.assertEqual(rejoined, line)

    def test_prefers_rightmost_space(self):
        # Spaces at 10 and 60; budget 78 -> should wrap at 60.
        line = "a" * 10 + " " + "b" * 49 + " " + "c" * 19  # total 80
        result = fold_line(line)
        first = result.split("\r\n ")[0]
        self.assertEqual(first, "a" * 10 + " " + "b" * 49)


class TestFoldLineHardBreak(unittest.TestCase):
    """Tokens longer than the budget are hard-broken."""

    def test_long_token_hard_break(self):
        line = "a" * 200
        result = fold_line(line)
        for p in result.split("\r\n"):
            self.assertLessEqual(len(p), 78)
        rejoined = result.replace("\r\n ", "")
        self.assertEqual(rejoined, line)

    def test_long_token_with_short_prefix(self):
        line = "Subject: " + "x" * 100
        result = fold_line(line)
        for p in result.split("\r\n"):
            self.assertLessEqual(len(p), 78)
        # Unfold: the fold at the space after "Subject:" consumes that
        # space and replaces it with the continuation space, so it round-
        # trips via replace("\r\n ", " "). The subsequent hard breaks of
        # the long "x" token introduce continuation spaces that were not
        # present in the original; those spaces are an unavoidable artifact
        # of hard-breaking, so we only check that the non-space content
        # survives.
        rejoined = result.replace("\r\n ", " ")
        self.assertEqual(rejoined.replace(" ", ""), line.replace(" ", ""))


class TestFoldLineContinuationBudget(unittest.TestCase):
    """Continuation lines reserve one char for the leading space."""

    def test_continuation_line_respects_budget(self):
        # First chunk 78 chars ending at a space; continuation must be <=77
        # plus leading space = 78.
        first = "a" * 77 + " "
        second = "b" * 77
        line = first + second  # 155 chars
        result = fold_line(line)
        physical = result.split("\r\n")
        self.assertLessEqual(len(physical[0]), 78)
        self.assertLessEqual(len(physical[1]), 78)
        self.assertTrue(physical[1].startswith(" "))


class TestFoldLineErrors(unittest.TestCase):

    def test_rejects_cr(self):
        with self.assertRaises(FoldError):
            fold_line("a\rb")

    def test_rejects_lf(self):
        with self.assertRaises(FoldError):
            fold_line("a\nb")

    def test_rejects_crlf(self):
        with self.assertRaises(FoldError):
            fold_line("a\r\nb")

    def test_rejects_non_ascii(self):
        with self.assertRaises(FoldError):
            fold_line("caf\u00e9")

    def test_rejects_small_max_len(self):
        with self.assertRaises(FoldError):
            fold_line("hello", max_len=2)

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            fold_line(b"hello")


class TestFoldHeader(unittest.TestCase):

    def test_basic_header(self):
        result = fold_header("Subject", "Hello")
        self.assertEqual(result, "Subject: Hello")

    def test_long_header_folds(self):
        result = fold_header("Subject", "x" * 100)
        for p in result.split("\r\n"):
            self.assertLessEqual(len(p), 78)
        # Unfold: the first fold is at the space after "Subject:" (which
        # round-trips as replace("\r\n ", " ")), but the remaining long
        # "x" token is hard-broken and the continuation spaces introduced
        # there were not in the original. Those spaces are an unavoidable
        # artifact of hard-breaking, so we only check that the non-space
        # content survives.
        rejoined = result.replace("\r\n ", " ")
        self.assertEqual(rejoined.replace(" ", ""), ("Subject: " + "x" * 100).replace(" ", ""))

    def test_empty_name_rejected(self):
        with self.assertRaises(FoldError):
            fold_header("", "value")

    def test_colon_in_name_rejected(self):
        with self.assertRaises(FoldError):
            fold_header("Na:me", "value")


class TestCustomMaxLen(unittest.TestCase):

    def test_custom_max_len(self):
        line = "aaaa bbbb cccc"
        result = fold_line(line, max_len=10)
        for p in result.split("\r\n"):
            self.assertLessEqual(len(p), 10)


class TestNoTrailingCRLF(unittest.TestCase):

    def test_no_trailing_crlf(self):
        line = "a" * 100
        result = fold_line(line)
        self.assertFalse(result.endswith("\r\n"))


if __name__ == "__main__":
    unittest.main()
