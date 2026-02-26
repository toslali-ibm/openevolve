"""
Tests for code utilities in openevolve.utils.code_utils
"""

import unittest
from openevolve.utils.code_utils import apply_diff, extract_diffs


class TestCodeUtils(unittest.TestCase):
    """Tests for code utilities"""

    def test_extract_diffs(self):
        """Test extracting diffs from a response"""
        diff_text = """
        Let's improve this code:

        <<<<<<< SEARCH
        def hello():
            print("Hello")
        =======
        def hello():
            print("Hello, World!")
        >>>>>>> REPLACE

        Another change:

        <<<<<<< SEARCH
        x = 1
        =======
        x = 2
        >>>>>>> REPLACE
        """

        diffs = extract_diffs(diff_text)
        self.assertEqual(len(diffs), 2)
        self.assertEqual(
            diffs[0][0],
            """        def hello():
            print(\"Hello\")""",
        )
        self.assertEqual(
            diffs[0][1],
            """        def hello():
            print(\"Hello, World!\")""",
        )
        self.assertEqual(diffs[1][0], "        x = 1")
        self.assertEqual(diffs[1][1], "        x = 2")

    def test_apply_diff(self):
        """Test applying diffs to code"""
        original_code = """
        def hello():
            print("Hello")

        x = 1
        y = 2
        """

        diff_text = """
        <<<<<<< SEARCH
        def hello():
            print("Hello")
        =======
        def hello():
            print("Hello, World!")
        >>>>>>> REPLACE

        <<<<<<< SEARCH
        x = 1
        =======
        x = 2
        >>>>>>> REPLACE
        """

        expected_code = """
        def hello():
            print("Hello, World!")

        x = 2
        y = 2
        """

        result = apply_diff(original_code, diff_text)

        # Normalize whitespace for comparison
        self.assertEqual(
            result,
            expected_code,
        )


class TestStripDiffMarkers(unittest.TestCase):
    """Test that stray ======= markers are stripped from replacement text."""

    def test_single_trailing_separator(self):
        """LLM wraps replacement with extra ======= before >>>>>>> REPLACE."""
        diff_text = (
            "<<<<<<< SEARCH\n"
            "old code\n"
            "=======\n"
            "new code\n"
            "=======\n"
            ">>>>>>> REPLACE\n"
        )
        diffs = extract_diffs(diff_text)
        self.assertEqual(len(diffs), 1)
        self.assertNotIn("=======", diffs[0][1])
        self.assertEqual(diffs[0][1], "new code")

    def test_multiple_separators(self):
        """LLM generates 5 ======= in a single diff block."""
        diff_text = (
            "<<<<<<< SEARCH\n"
            "old\n"
            "=======\n"
            "part1\n"
            "=======\n"
            "part2\n"
            "=======\n"
            "part3\n"
            "=======\n"
            "part4\n"
            "=======\n"
            ">>>>>>> REPLACE\n"
        )
        diffs = extract_diffs(diff_text)
        self.assertEqual(len(diffs), 1)
        self.assertNotIn("=======", diffs[0][1])
        # All parts should be preserved (just markers removed)
        self.assertIn("part1", diffs[0][1])
        self.assertIn("part4", diffs[0][1])

    def test_no_stripping_when_clean(self):
        """Normal diff without extra separators is unchanged."""
        diff_text = (
            "<<<<<<< SEARCH\n"
            "old\n"
            "=======\n"
            "new\n"
            ">>>>>>> REPLACE\n"
        )
        diffs = extract_diffs(diff_text)
        self.assertEqual(diffs[0][1], "new")

    def test_apply_diff_strips_markers(self):
        """End-to-end: apply_diff produces clean code even with extra =======."""
        original = "// EVOLVE-BLOCK-START\nold code\n// EVOLVE-BLOCK-END\n"
        diff_text = (
            "<<<<<<< SEARCH\nold code\n=======\nnew code\n=======\n>>>>>>> REPLACE\n"
        )
        result = apply_diff(original, diff_text)
        self.assertNotIn("=======", result)
        self.assertIn("new code", result)


if __name__ == "__main__":
    unittest.main()
