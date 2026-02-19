# Copyright (c) 2026, the ElectrumX authors
#
# All rights reserved.

'''Deserializer for PEPEPOW transactions.'''

from dataclasses import dataclass
from typing import Any

from electrumx.lib.tx import Deserializer, Tx
from electrumx.lib.tx_dash import DeserializerDash
from electrumx.lib.util import (
    pack_le_int32, pack_le_uint16, pack_le_uint32,
    pack_varbytes, pack_varint,
)


@dataclass(kw_only=True, slots=True)
class PepepowTx(Tx):
    '''Class representing a PEPEPOW transaction.'''
    tx_type: int
    extra_payload: Any

    def serialize(self):
        n_locktime = pack_le_uint32(self.locktime)
        txins = (
            pack_varint(len(self.inputs))
            + b''.join(tx_in.serialize() for tx_in in self.inputs)
        )
        txouts = (
            pack_varint(len(self.outputs))
            + b''.join(tx_out.serialize() for tx_out in self.outputs)
        )
        if self.tx_type:
            header = pack_le_uint16(self.version) + pack_le_uint16(self.tx_type)
            return header + txins + txouts + n_locktime + self._serialize_extra_payload()
        return pack_le_int32(self.version) + txins + txouts + n_locktime

    def _serialize_extra_payload(self):
        extra = self.extra_payload
        spec_tx_class = DeserializerPepepow.SPEC_TX_HANDLERS.get(self.tx_type)
        if spec_tx_class and isinstance(extra, spec_tx_class):
            return pack_varbytes(extra.serialize())
        if not isinstance(extra, (bytes, bytearray)):
            raise ValueError(
                'PEPEPOW tx_type does not conform with extra payload class: '
                f'{self.tx_type}, {extra}'
            )
        return pack_varbytes(extra)


class DeserializerPepepow(Deserializer):
    '''Deserializer for PEPEPOW transactions with conservative DIP2 fallback.'''

    # PEPEPOW is Dash-derived. Reuse known special tx payload handlers when possible.
    SPEC_TX_HANDLERS = DeserializerDash.SPEC_TX_HANDLERS
    CB_TX = DeserializerDash.CB_TX

    def _read_extra_payload(self, tx_type: int, payload_size: int):
        payload_start = self.cursor
        remaining = self._binary_length - payload_start
        if payload_size > remaining:
            payload_size = remaining
        payload_end = payload_start + payload_size

        spec_tx_class = self.SPEC_TX_HANDLERS.get(tx_type)
        if spec_tx_class:
            read_method = getattr(spec_tx_class, 'read_tx_extra', None)
            if read_method:
                try:
                    parsed = read_method(self)
                    if self.cursor == payload_end and isinstance(parsed, spec_tx_class):
                        return parsed
                except Exception:
                    pass
                # Conservative fallback: do not fail sync on unknown/non-standard payload.
                self.cursor = payload_start

        return self._read_nbytes(payload_size)

    def read_tx(self):
        start = self.cursor
        header = self._read_le_uint32()
        tx_type = header >> 16
        if tx_type:
            version = header & 0x0000ffff
        else:
            version = header

        # Dash-style safeguard: legacy txs with high bits set but low version remain legacy.
        if tx_type and version < 3:
            version = header
            tx_type = 0

        inputs = self._read_inputs()
        outputs = self._read_outputs()
        locktime = self._read_le_uint32()

        if tx_type:
            payload_size = self._read_varint()
            extra_payload = self._read_extra_payload(tx_type, payload_size)
        else:
            extra_payload = b''

        txid = self.TX_HASH_FN(self.binary[start:self.cursor])
        return PepepowTx(
            version=version,
            inputs=inputs,
            outputs=outputs,
            locktime=locktime,
            tx_type=tx_type,
            extra_payload=extra_payload,
            txid=txid,
            wtxid=txid,
        )
