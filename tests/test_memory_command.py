import unittest

from handlers.memory import parse_keep_recent_facts


class MemoryCommandParseTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(parse_keep_recent_facts([]), 200)
        self.assertEqual(parse_keep_recent_facts(["apply"]), 200)

    def test_explicit_values(self):
        self.assertEqual(parse_keep_recent_facts(["apply", "300"]), 300)
        self.assertEqual(parse_keep_recent_facts(["dry-run", "150"]), 150)
        self.assertEqual(parse_keep_recent_facts(["250"]), 250)

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            parse_keep_recent_facts(["apply", "bad"])


if __name__ == "__main__":
    unittest.main()
