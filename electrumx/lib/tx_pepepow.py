from electrumx.lib.tx import Deserializer
from electrumx.lib.util import unpack_le_uint32, unpack_le_uint64

class DeserializerPepepow(Deserializer):
    def __init__(self, binary, start=0):
        super().__init__(binary, start)

    def read_tx(self):
        """Read a single transaction and return it as a dictionary."""
        version = unpack_le_uint32(self.binary, self.cursor)
        self.cursor += 4

        # Read flag if present
        flag = None
        if self.cursor < len(self.binary) and self.binary[self.cursor] == 0:
            flag = unpack_le_uint32(self.binary, self.cursor)
            self.cursor += 4

        # Get inputs (vin)
        num_inputs = self._read_varint()
        inputs = [self._read_input() for _ in range(num_inputs)]

        # Get outputs (vout)
        num_outputs = self._read_varint()
        outputs = [self._read_output() for _ in range(num_outputs)]

        # Locktime
        locktime = unpack_le_uint32(self.binary, self.cursor)
        self.cursor += 4

        return {
            'version': version,
            'flag': flag,
            'inputs': inputs,
            'outputs': outputs,
            'locktime': locktime,
        }

    def _read_input(self):
        """Read a transaction input."""
        # Coinbase transaction handling
        prev_hash = self.binary[self.cursor:self.cursor + 32][::-1].hex()
        self.cursor += 32
        prev_idx = unpack_le_uint32(self.binary, self.cursor)
        self.cursor += 4
        
        if prev_hash == '0' * 64:  # This is a coinbase transaction
            coinbase_len = self._read_varint()
            coinbase = self.binary[self.cursor:self.cursor + coinbase_len].hex()
            self.cursor += coinbase_len
            sequence = unpack_le_uint32(self.binary, self.cursor)
            self.cursor += 4
            return {
                'coinbase': coinbase,
                'sequence': sequence,
            }
        else:
            script_sig_len = self._read_varint()
            script_sig = self.binary[self.cursor:self.cursor + script_sig_len].hex()
            self.cursor += script_sig_len
            sequence = unpack_le_uint32(self.binary, self.cursor)
            self.cursor += 4
            return {
                'prev_hash': prev_hash,
                'prev_idx': prev_idx,
                'script_sig': script_sig,
                'sequence': sequence,
            }

    def _read_output(self):
        """Read a transaction output."""
        value = unpack_le_uint64(self.binary, self.cursor)
        self.cursor += 8
        script_pubkey_len = self._read_varint()
        script_pubkey = self.binary[self.cursor:self.cursor + script_pubkey_len].hex()
        self.cursor += script_pubkey_len
        return {
            'value': value,
            'script_pubkey': script_pubkey,
        }
