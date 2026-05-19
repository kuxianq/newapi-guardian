import asyncio
import unittest

from async_utils import run_blocking, run_many_blocking


class AsyncUtilsTests(unittest.TestCase):
    def test_run_blocking(self):
        async def run():
            return await run_blocking(lambda x, y: x + y, 2, 3)
        self.assertEqual(asyncio.run(run()), 5)

    def test_run_many_blocking_keeps_order(self):
        async def run():
            return await run_many_blocking([1, 2, 3], lambda x: x * 2, max_workers=2)
        self.assertEqual(asyncio.run(run()), [2, 4, 6])


if __name__ == "__main__":
    unittest.main()
