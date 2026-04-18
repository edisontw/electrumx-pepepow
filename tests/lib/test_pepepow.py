import electrumx.lib.pepepow_hash as lib_pepepow_hash
from electrumx.lib.coins import Coin, Pepepow
from electrumx.lib.hash import hex_str_to_hash


def test_pepepow_lookup_coin_class():
    assert Coin.lookup_coin_class('PEPEPOW', 'mainnet') is Pepepow


def test_pepepow_constants():
    assert Pepepow.RPC_PORT == 8833
    assert Pepepow.GENESIS_HASH == '00000a308cc3b469703a3bc1aa55bc251a71c9287d7b413242592c0ab0a31f13'
    assert Pepepow.XELISV2_CUTOVER_HEIGHT == 1_930_000
    assert Pepepow.HOOHASHV110_CUTOVER_HEIGHT == 4_354_200


def test_pepepow_header_hash_for_height_dispatches_all_three_eras(monkeypatch):
    header = b"\x01" * 80
    calls = []

    def fake_memehash(value):
        calls.append(("memehash", value))
        return b"\x11" * 32

    def fake_xelis(value):
        calls.append(("xelisv2", value))
        return b"\x22" * 32

    def fake_hoohash(value):
        calls.append(("hoohashv110", value))
        return b"\x44" * 32

    monkeypatch.setattr(lib_pepepow_hash, "pepepow_memehash", fake_memehash)
    monkeypatch.setattr(lib_pepepow_hash, "pepepow_xelisv2_hash", fake_xelis)
    monkeypatch.setattr(lib_pepepow_hash, "pepepow_hoohash_v110_hash", fake_hoohash)

    assert Pepepow.header_hash_for_height(header, 100) == b"\x11" * 32
    assert Pepepow.header_hash_for_height(header, Pepepow.XELISV2_CUTOVER_HEIGHT) == b"\x22" * 32
    assert Pepepow.header_hash_for_height(header, Pepepow.HOOHASHV110_CUTOVER_HEIGHT) == b"\x44" * 32
    assert calls == [
        ("memehash", header),
        ("xelisv2", header),
        ("hoohashv110", header),
    ]


def test_pepepow_header_hash_falls_back_without_height(monkeypatch):
    version = (0x4000).to_bytes(4, 'little')
    header = version + (b"\x02" * 76)

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
    monkeypatch.setattr(
        lib_pepepow_hash,
        "pepepow_hoohash_v110_hash",
        lambda _value: (_ for _ in ()).throw(AssertionError("unexpected hoohash call")),
    )

    assert Pepepow.header_hash(header) == b"\x33" * 32


def test_pepepow_version_bit_dispatch_prefers_hoohash(monkeypatch):
    calls = []

    def fake_memehash(value):
        calls.append(("memehash", value[:4]))
        return b"\x11" * 32

    def fake_xelis(value):
        calls.append(("xelisv2", value[:4]))
        return b"\x22" * 32

    def fake_hoohash(value):
        calls.append(("hoohashv110", value[:4]))
        return b"\x44" * 32

    monkeypatch.setattr(lib_pepepow_hash, "pepepow_memehash", fake_memehash)
    monkeypatch.setattr(lib_pepepow_hash, "pepepow_xelisv2_hash", fake_xelis)
    monkeypatch.setattr(lib_pepepow_hash, "pepepow_hoohash_v110_hash", fake_hoohash)

    assert lib_pepepow_hash.pepepow_header_hash((0x0001).to_bytes(4, 'little') + b"\x00" * 76) == b"\x11" * 32
    assert lib_pepepow_hash.pepepow_header_hash((0x8000).to_bytes(4, 'little') + b"\x00" * 76) == b"\x22" * 32
    assert lib_pepepow_hash.pepepow_header_hash((0x4000).to_bytes(4, 'little') + b"\x00" * 76) == b"\x44" * 32
    assert lib_pepepow_hash.pepepow_header_hash((0xC000).to_bytes(4, 'little') + b"\x00" * 76) == b"\x44" * 32
    assert calls == [
        ("memehash", (0x0001).to_bytes(4, 'little')),
        ("xelisv2", (0x8000).to_bytes(4, 'little')),
        ("hoohashv110", (0x4000).to_bytes(4, 'little')),
        ("hoohashv110", (0xC000).to_bytes(4, 'little')),
    ]


def test_pepepow_genesis_block_hashes_with_height_zero(monkeypatch):
    heights = []

    def fake_header_hash(cls, header, height=None):
        heights.append(height)
        return hex_str_to_hash(cls.GENESIS_HASH)

    monkeypatch.setattr(Pepepow, "header_hash", classmethod(fake_header_hash))
    block = b"\x00" * 80

    assert Pepepow.genesis_block(block) == block + b"\0"
    assert heights == [0]
