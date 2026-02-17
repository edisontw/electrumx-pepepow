import electrumx.lib.pepepow_hash as lib_pepepow_hash
from electrumx.lib.coins import Coin, Pepepow
from electrumx.lib.hash import hex_str_to_hash


def test_pepepow_lookup_coin_class():
    assert Coin.lookup_coin_class('PEPEPOW', 'mainnet') is Pepepow


def test_pepepow_constants():
    assert Pepepow.RPC_PORT == 8833
    assert Pepepow.GENESIS_HASH == '00000a308cc3b469703a3bc1aa55bc251a71c9287d7b413242592c0ab0a31f13'
    assert Pepepow.XELISV2_CUTOVER_HEIGHT == 1_930_000


def test_pepepow_header_hash_dispatch_by_height(monkeypatch):
    header = b"\x01" * 80
    calls = []

    def fake_memehash(value):
        calls.append(("memehash", value))
        return b"\x11" * 32

    def fake_xelis(value):
        calls.append(("xelisv2", value))
        return b"\x22" * 32

    monkeypatch.setattr(lib_pepepow_hash, "pepepow_memehash", fake_memehash)
    monkeypatch.setattr(lib_pepepow_hash, "pepepow_xelisv2_hash", fake_xelis)

    assert Pepepow.header_hash(header, 100) == b"\x11" * 32
    assert Pepepow.header_hash(header, Pepepow.XELISV2_CUTOVER_HEIGHT) == b"\x22" * 32
    assert Pepepow.header_hash(header, Pepepow.XELISV2_CUTOVER_HEIGHT + 1) == b"\x22" * 32
    assert calls == [
        ("memehash", header),
        ("xelisv2", header),
        ("xelisv2", header),
    ]


def test_pepepow_header_hash_falls_back_without_height(monkeypatch):
    header = b"\x02" * 80

    monkeypatch.setattr(lib_pepepow_hash, "pepepow_header_hash", lambda value: b"\x33" * 32)
    monkeypatch.setattr(
        lib_pepepow_hash,
        "pepepow_memehash",
        lambda _value: (_ for _ in ()).throw(AssertionError("unexpected memehash call")),
    )
    monkeypatch.setattr(
        lib_pepepow_hash,
        "pepepow_xelisv2_hash",
        lambda _value: (_ for _ in ()).throw(AssertionError("unexpected xelisv2 call")),
    )

    assert Pepepow.header_hash(header) == b"\x33" * 32


def test_pepepow_genesis_block_hashes_with_height_zero(monkeypatch):
    heights = []

    def fake_header_hash(cls, header, height=None):
        heights.append(height)
        return hex_str_to_hash(cls.GENESIS_HASH)

    monkeypatch.setattr(Pepepow, "header_hash", classmethod(fake_header_hash))
    block = b"\x00" * 80

    assert Pepepow.genesis_block(block) == block + b"\0"
    assert heights == [0]
