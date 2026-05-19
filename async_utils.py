"""Async helpers for running blocking work from Telegram async handlers."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def run_blocking(func: Callable[..., R], *args, **kwargs) -> R:
    """Run a blocking callable in the default executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


async def run_many_blocking(
    items: Iterable[T],
    worker: Callable[[T], R],
    *,
    max_workers: int = 10,
) -> list[R]:
    """Run blocking work for many items with a bounded thread pool."""
    item_list = list(items)
    if not item_list:
        return []
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return await asyncio.gather(*[
            loop.run_in_executor(executor, worker, item)
            for item in item_list
        ])
