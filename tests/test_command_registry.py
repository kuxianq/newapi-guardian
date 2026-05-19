import unittest

from bot import get_commands


class CommandRegistryTests(unittest.TestCase):
    def test_commands_are_unique_and_callable(self):
        commands = get_commands()
        names = [name for name, _desc, _handler in commands]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("usage_summary", names)
        self.assertIn("memory_status", names)
        self.assertIn("memory_compact", names)
        for name, desc, handler in commands:
            self.assertIsInstance(name, str)
            self.assertTrue(desc)
            self.assertTrue(callable(handler))


if __name__ == "__main__":
    unittest.main()
