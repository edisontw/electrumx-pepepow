import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest

from electrumx.server.db import DB


def make_db(db_height=100, reorg_limit=10):
    db = DB.__new__(DB)
    db.logger = mock.Mock()
    db.env = SimpleNamespace(reorg_limit=reorg_limit)
    db.db_height = db_height
    db._header_mc_init_task = None
    return db


@pytest.mark.asyncio
async def test_header_branch_and_root_initializes_cache_once_for_concurrent_calls():
    db = make_db()
    initialized = asyncio.Event()
    init_started = asyncio.Event()
    allow_init = asyncio.Event()
    init_lengths = []

    async def initialize(length):
        init_lengths.append(length)
        init_started.set()
        await allow_init.wait()
        initialized.set()

    async def branch_and_root(length, height):
        return [length, height], b"root"

    db.header_mc = mock.Mock(
        initialized=initialized,
        initialize=mock.AsyncMock(side_effect=initialize),
        branch_and_root=mock.AsyncMock(side_effect=branch_and_root),
    )

    task1 = asyncio.create_task(db.header_branch_and_root(90, 7))
    await init_started.wait()
    task2 = asyncio.create_task(db.header_branch_and_root(90, 8))
    await asyncio.sleep(0)
    allow_init.set()

    result1, result2 = await asyncio.gather(task1, task2)

    assert init_lengths == [90]
    assert result1 == ([90, 7], b"root")
    assert result2 == ([90, 8], b"root")
    assert db.header_mc.initialize.await_count == 1
    assert db.header_mc.branch_and_root.await_args_list == [
        mock.call(90, 7),
        mock.call(90, 8),
    ]


@pytest.mark.asyncio
async def test_header_branch_and_root_reuses_initialized_cache_without_fs_block_hashes():
    db = make_db(db_height=200, reorg_limit=10)
    initialized = asyncio.Event()

    async def initialize(length):
        initialized.set()

    async def branch_and_root(length, height):
        return [height], b"root"

    db.header_mc = mock.Mock(
        initialized=initialized,
        initialize=mock.AsyncMock(side_effect=initialize),
        branch_and_root=mock.AsyncMock(side_effect=branch_and_root),
    )
    db.fs_block_hashes = mock.AsyncMock(side_effect=AssertionError("unexpected fs_block_hashes call"))

    first = await db.header_branch_and_root(50, 3)
    second = await db.header_branch_and_root(75, 4)

    assert first == ([3], b"root")
    assert second == ([4], b"root")
    assert db.header_mc.initialize.await_args_list == [mock.call(190)]
    assert db.header_mc.branch_and_root.await_args_list == [
        mock.call(50, 3),
        mock.call(75, 4),
    ]
    db.fs_block_hashes.assert_not_called()
