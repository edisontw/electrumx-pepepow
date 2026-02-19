from electrumx.lib.hash import double_sha256
from electrumx.lib.tx_pepepow import DeserializerPepepow, PepepowTx
from electrumx.lib.util import pack_le_uint32, pack_varint


def _minimal_spec_tx(*, tx_type: int, version: int, payload: bytes) -> bytes:
    header = pack_le_uint32((tx_type << 16) | version)
    # 0 inputs, 0 outputs, locktime=0
    body = b'\x00\x00' + pack_le_uint32(0)
    return header + body + pack_varint(len(payload)) + payload


def _minimal_legacy_tx(version: int) -> bytes:
    return pack_le_uint32(version) + b'\x00\x00' + pack_le_uint32(0)


def test_pepepow_unknown_spec_payload_falls_back_to_raw_bytes():
    raw_tx = _minimal_spec_tx(tx_type=187, version=3, payload=b'abc')
    deser = DeserializerPepepow(raw_tx)
    tx = deser.read_tx()

    assert isinstance(tx, PepepowTx)
    assert tx.tx_type == 187
    assert tx.extra_payload == b'abc'
    assert deser.cursor == len(raw_tx)
    assert tx.txid == double_sha256(raw_tx)


def test_pepepow_rare_version_is_parsed_without_exception():
    header = (9 << 16) | 2
    raw_tx = _minimal_legacy_tx(header)
    deser = DeserializerPepepow(raw_tx)
    tx = deser.read_tx()

    assert isinstance(tx, PepepowTx)
    assert tx.version == header
    assert tx.tx_type == 0
    assert tx.extra_payload == b''
    assert deser.cursor == len(raw_tx)
    assert tx.txid == double_sha256(raw_tx)


def test_pepepow_known_spec_parse_failure_downgrades_to_raw_payload():
    raw_tx = _minimal_spec_tx(
        tx_type=DeserializerPepepow.CB_TX,
        version=3,
        payload=b'\xaa',
    )
    deser = DeserializerPepepow(raw_tx)
    tx = deser.read_tx()

    assert isinstance(tx, PepepowTx)
    assert tx.tx_type == DeserializerPepepow.CB_TX
    assert tx.extra_payload == b'\xaa'
    assert deser.cursor == len(raw_tx)
    assert tx.txid == double_sha256(raw_tx)
