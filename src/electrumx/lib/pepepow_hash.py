# Copyright (c) 2026, the ElectrumX authors
#
# All rights reserved.

'''PEPEPOW hashing helpers.

Implements:
- Legacy memehash pipeline (BLAKE512 -> SIMD512 -> ECHO512 -> CUBEHASH512
  -> SHAVITE512 -> SHA256^3)
- Xelis v2 path (pure python implementation using blake3)
- Header hash selector based on the PEPEPOW version bit switch.
'''

from __future__ import annotations

import ctypes
import hashlib
import math
import struct
from pathlib import Path
from typing import Optional

try:
    from blake3 import blake3
except ImportError:  # pragma: no cover - optional dependency
    blake3 = None


_SPH_LIB_CANDIDATES = {
    'blake': ('libsph_blake.so',),
    'simd': ('libsph_simd.so',),
    'echo': ('libsph_echo.so',),
    'cubehash': ('libsph_cubehash.so',),
    'shavite': ('libsph_shavite.so',),
}
_SPH_LIB_HANDLES: dict[str, ctypes.CDLL] = {}
_SPH_CTX_SIZE = 1024


def _load_sph_library(kind: str) -> ctypes.CDLL:
    handle = _SPH_LIB_HANDLES.get(kind)
    if handle is not None:
        return handle

    filenames = _SPH_LIB_CANDIDATES[kind]
    module_dir = Path(__file__).resolve().parent

    for filename in filenames:
        local_path = module_dir / filename
        if local_path.exists():
            try:
                handle = ctypes.CDLL(str(local_path))
                _SPH_LIB_HANDLES[kind] = handle
                return handle
            except OSError as exc:  # pragma: no cover - system dependent
                raise RuntimeError(
                    f"Unable to load PEPEPOW SPH library '{filename}' at {local_path}: {exc}"
                ) from exc

    for filename in filenames:
        try:
            handle = ctypes.CDLL(filename)
            _SPH_LIB_HANDLES[kind] = handle
            return handle
        except OSError:
            continue

    raise RuntimeError(
        f"Missing PEPEPOW SPH library for '{kind}'. "
        f"Expected one of {filenames} in {module_dir} or system library paths."
    )


def _run_sph_512(kind: str, data: bytes) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        data = bytes(data)
    data = bytes(data)

    lib = _load_sph_library(kind)
    init = getattr(lib, f'sph_{kind}512_init')
    update = getattr(lib, f'sph_{kind}512')
    close = getattr(lib, f'sph_{kind}512_close')

    init.argtypes = [ctypes.c_void_p]
    update.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    close.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    init.restype = None
    update.restype = None
    close.restype = None

    ctx = ctypes.create_string_buffer(_SPH_CTX_SIZE)
    in_buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    out_buf = (ctypes.c_ubyte * 64)()

    init(ctypes.byref(ctx))
    update(ctypes.byref(ctx), ctypes.byref(in_buf), len(data))
    close(ctypes.byref(ctx), ctypes.byref(out_buf))

    return bytes(out_buf)


def pepepow_memehash(header: bytes) -> bytes:
    '''PEPEPOW legacy PoW hash (pre-Xelis v2 path).'''
    data = bytes(header)
    if len(data) < 80:
        raise ValueError('PEPEPOW header must be at least 80 bytes')

    hash1 = _run_sph_512('blake', data)
    hash2 = _run_sph_512('simd', hash1)
    hash3 = _run_sph_512('echo', hash2)
    hash4 = _run_sph_512('cubehash', hash3)
    hash5 = _run_sph_512('shavite', hash4)

    hash6 = hashlib.sha256(hash5).digest()
    hash7 = hashlib.sha256(hash6).digest()
    hash8 = hashlib.sha256(hash7).digest()
    return hash8


_XELIS_V2_INPUT_LEN = 112
_XELIS_V2_MEMORY_SIZE = 429 * 128
_XELIS_V2_BUFFER_SIZE = _XELIS_V2_MEMORY_SIZE // 2
_XELIS_V2_OUTPUT_SIZE = _XELIS_V2_MEMORY_SIZE * 8
_XELIS_V2_CHUNKS = 4
_XELIS_V2_CHUNK_SIZE = 32
_XELIS_V2_HASH_SIZE = 32
_XELIS_V2_NONCE_SIZE = 12
_XELIS_V2_SCRATCHPAD_ITERS = 3
_XELIS_V2_AES_KEY = b'xelishash-pow-v2'
_CHACHA_CONST_STATE = (1634760805, 857760878, 2036477234, 1797285236)
_MASK_64 = (1 << 64) - 1

_AES_SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)


def _require_blake3() -> None:
    if blake3 is None:  # pragma: no cover - only hit in misconfiguration
        raise RuntimeError(
            "PEPEPOW Xelis v2 hashing requires the 'blake3' package. "
            "Install it with 'pip install blake3' to continue."
        )


def _uint64(value: int) -> int:
    return value & _MASK_64


def _rotl64(value: int, shift: int) -> int:
    shift &= 63
    value &= _MASK_64
    if shift == 0:
        return value
    return ((value << shift) & _MASK_64) | (value >> (64 - shift))


def _rotr64(value: int, shift: int) -> int:
    shift &= 63
    value &= _MASK_64
    if shift == 0:
        return value
    return (value >> shift) | ((value << (64 - shift)) & _MASK_64)


def _combine_uint64(high: int, low: int) -> int:
    return ((high & _MASK_64) << 64) | (low & _MASK_64)


def _write_uint64_le(buf: bytearray, offset: int, value: int) -> None:
    buf[offset:offset + 8] = _uint64(value).to_bytes(8, 'little')


def _read_uint64_le(buf: bytearray, offset: int = 0) -> int:
    return int.from_bytes(buf[offset:offset + 8], 'little')


def _xtime(x: int) -> int:
    return ((x << 1) ^ 0x1B) & 0xFF if x & 0x80 else (x << 1) & 0xFF


def _gmul(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        a = _xtime(a)
        b >>= 1
    return result


def _sub_bytes(state: bytearray) -> None:
    for i in range(16):
        state[i] = _AES_SBOX[state[i]]


def _shift_rows(state: bytearray) -> None:
    tmp = state[:]
    state[1] = tmp[5]
    state[2] = tmp[10]
    state[3] = tmp[15]
    state[5] = tmp[9]
    state[6] = tmp[14]
    state[7] = tmp[3]
    state[9] = tmp[13]
    state[10] = tmp[2]
    state[11] = tmp[7]
    state[13] = tmp[1]
    state[14] = tmp[6]
    state[15] = tmp[11]


def _mix_columns(state: bytearray) -> None:
    tmp = state[:]
    for i in range(4):
        base = i * 4
        state[base + 0] = (
            _gmul(0x02, tmp[base + 0]) ^
            _gmul(0x03, tmp[base + 1]) ^
            tmp[base + 2] ^
            tmp[base + 3]
        )
        state[base + 1] = (
            tmp[base + 0] ^
            _gmul(0x02, tmp[base + 1]) ^
            _gmul(0x03, tmp[base + 2]) ^
            tmp[base + 3]
        )
        state[base + 2] = (
            tmp[base + 0] ^
            tmp[base + 1] ^
            _gmul(0x02, tmp[base + 2]) ^
            _gmul(0x03, tmp[base + 3])
        )
        state[base + 3] = (
            _gmul(0x03, tmp[base + 0]) ^
            tmp[base + 1] ^
            tmp[base + 2] ^
            _gmul(0x02, tmp[base + 3])
        )


def _add_round_key(state: bytearray, round_key: bytes) -> None:
    for i in range(16):
        state[i] ^= round_key[i]


def _aes_single_round(block: bytearray, key: bytes) -> None:
    _sub_bytes(block)
    _shift_rows(block)
    _mix_columns(block)
    _add_round_key(block, key)


def _quarter_round(state, a, b, c, d):
    state[a] = (state[a] + state[b]) & 0xFFFFFFFF
    state[d] ^= state[a]
    state[d] = ((state[d] << 16) | (state[d] >> 16)) & 0xFFFFFFFF

    state[c] = (state[c] + state[d]) & 0xFFFFFFFF
    state[b] ^= state[c]
    state[b] = ((state[b] << 12) | (state[b] >> 20)) & 0xFFFFFFFF

    state[a] = (state[a] + state[b]) & 0xFFFFFFFF
    state[d] ^= state[a]
    state[d] = ((state[d] << 8) | (state[d] >> 24)) & 0xFFFFFFFF

    state[c] = (state[c] + state[d]) & 0xFFFFFFFF
    state[b] ^= state[c]
    state[b] = ((state[b] << 7) | (state[b] >> 25)) & 0xFFFFFFFF


def _chacha20_block(key_words, counter, nonce_words, rounds):
    state = [
        _CHACHA_CONST_STATE[0], _CHACHA_CONST_STATE[1],
        _CHACHA_CONST_STATE[2], _CHACHA_CONST_STATE[3],
        *key_words,
        counter,
        *nonce_words,
    ]
    working = state[:]
    for _ in range(rounds // 2):
        _quarter_round(working, 0, 4, 8, 12)
        _quarter_round(working, 1, 5, 9, 13)
        _quarter_round(working, 2, 6, 10, 14)
        _quarter_round(working, 3, 7, 11, 15)
        _quarter_round(working, 0, 5, 10, 15)
        _quarter_round(working, 1, 6, 11, 12)
        _quarter_round(working, 2, 7, 8, 13)
        _quarter_round(working, 3, 4, 9, 14)
    for i in range(16):
        working[i] = (working[i] + state[i]) & 0xFFFFFFFF
    return working


def _chacha20_encrypt_bytes(
    key: bytes,
    nonce: bytes,
    length: int,
    rounds: int,
    in_data: Optional[bytes] = None,
) -> bytes:
    if len(key) != 32:
        raise ValueError('ChaCha20 key must be 32 bytes')
    if rounds % 2:
        raise ValueError('ChaCha20 rounds must be even')

    nonce_bytes = bytes((nonce or b'\x00' * _XELIS_V2_NONCE_SIZE)[:_XELIS_V2_NONCE_SIZE])
    nonce_words = list(struct.unpack('<3I', nonce_bytes.ljust(_XELIS_V2_NONCE_SIZE, b'\x00')))
    key_words = list(struct.unpack('<8I', key))

    counter = 0
    out = bytearray(length)
    in_view = memoryview(in_data) if in_data is not None else None
    produced = 0
    while produced < length:
        block_words = _chacha20_block(key_words, counter, nonce_words, rounds)
        block = b''.join(struct.pack('<I', word) for word in block_words)
        take = min(64, length - produced)
        if in_view is None:
            out[produced:produced + take] = block[:take]
        else:
            for idx in range(take):
                out[produced + idx] = in_view[produced + idx] ^ block[idx]
        produced += take
        counter = (counter + 1) & 0xFFFFFFFF

    return bytes(out)


def _blake3_digest(data: bytes) -> bytes:
    _require_blake3()
    return blake3(data).digest(length=_XELIS_V2_HASH_SIZE)


def _xelis_stage1(input_bytes: bytes, scratch: bytearray) -> None:
    key = bytearray(_XELIS_V2_CHUNK_SIZE * _XELIS_V2_CHUNKS)
    key[:len(input_bytes)] = input_bytes
    buffer = bytearray(_XELIS_V2_CHUNK_SIZE * 2)
    buffer[:_XELIS_V2_CHUNK_SIZE] = _blake3_digest(input_bytes)

    chunk_len = _XELIS_V2_OUTPUT_SIZE // _XELIS_V2_CHUNKS
    offset = 0
    for chunk in range(_XELIS_V2_CHUNKS):
        start = chunk * _XELIS_V2_CHUNK_SIZE
        buffer[_XELIS_V2_CHUNK_SIZE:] = key[start:start + _XELIS_V2_CHUNK_SIZE]
        input_hash = _blake3_digest(buffer)
        if chunk == 0:
            nonce = buffer[:_XELIS_V2_NONCE_SIZE]
        else:
            nonce = scratch[offset - _XELIS_V2_NONCE_SIZE:offset]
        stream = _chacha20_encrypt_bytes(input_hash, nonce, chunk_len, rounds=8)
        scratch[offset:offset + chunk_len] = stream
        offset += chunk_len
        buffer[:_XELIS_V2_CHUNK_SIZE] = input_hash


def _udiv(high: int, low: int, divisor: int) -> int:
    if divisor == 0:
        return 0
    dividend = _combine_uint64(high, low)
    return (dividend // divisor) & _MASK_64


def _operation_case_0(a, b, c, r, result, i, j):
    return _uint64(_rotl64(c, i * j) ^ b)


def _operation_case_1(a, b, c, r, result, i, j):
    return _uint64(_rotr64(c, i * j) ^ a)


def _operation_case_2(a, b, c, *_):
    return _uint64(a ^ b ^ c)


def _operation_case_3(a, b, c, *_):
    return _uint64((a + b) * c)


def _operation_case_4(a, b, c, *_):
    return _uint64((b - c) * a)


def _operation_case_5(a, b, c, *_):
    return _uint64(c - a + b)


def _operation_case_6(a, b, c, *_):
    return _uint64(a - b + c)


def _operation_case_7(a, b, c, *_):
    return _uint64(b * c + a)


def _operation_case_8(a, b, c, *_):
    return _uint64(c * a + b)


def _operation_case_9(a, b, c, *_):
    return _uint64(a * b * c)


def _operation_case_10(a, b, c, *_):
    return _uint64(_combine_uint64(a, b) % ((c | 1) & _MASK_64))


def _operation_case_11(a, b, c, r, result, *_):
    t2 = _combine_uint64(_rotl64(result, r), a | 2)
    combined = _combine_uint64(b, c)
    return _uint64(c if t2 > combined else combined % t2)


def _operation_case_12(a, b, c, *_):
    return _udiv(c, a, (b | 4) & _MASK_64)


def _operation_case_13(a, b, c, r, result, *_):
    t1 = _combine_uint64(_rotl64(result, r), b)
    t2 = _combine_uint64(a, c | 8)
    if t1 > t2 and t2 != 0:
        return _uint64(t1 // t2)
    return _uint64(a ^ b)


def _operation_case_14(a, b, c, *_):
    return _uint64((_combine_uint64(b, a) * c) >> 64)


def _operation_case_15(a, b, c, r, result, *_):
    left = _combine_uint64(a, c)
    right = _combine_uint64(_rotr64(result, r), b)
    return _uint64((left * right) >> 64)


_XELIS_OPERATIONS = [
    _operation_case_0,
    _operation_case_1,
    _operation_case_2,
    _operation_case_3,
    _operation_case_4,
    _operation_case_5,
    _operation_case_6,
    _operation_case_7,
    _operation_case_8,
    _operation_case_9,
    _operation_case_10,
    _operation_case_11,
    _operation_case_12,
    _operation_case_13,
    _operation_case_14,
    _operation_case_15,
]


def _xelis_stage3(scratch: bytearray) -> None:
    qwords = memoryview(scratch).cast('Q')
    mem_a = qwords[:_XELIS_V2_BUFFER_SIZE]
    mem_b = qwords[_XELIS_V2_BUFFER_SIZE:]

    addr_a = mem_b[_XELIS_V2_BUFFER_SIZE - 1]
    addr_b = mem_a[_XELIS_V2_BUFFER_SIZE - 1] >> 32
    r = 0
    block = bytearray(16)

    for i in range(_XELIS_V2_SCRATCHPAD_ITERS):
        mem_a_val = mem_a[addr_a % _XELIS_V2_BUFFER_SIZE]
        mem_b_val = mem_b[addr_b % _XELIS_V2_BUFFER_SIZE]

        _write_uint64_le(block, 0, mem_b_val)
        _write_uint64_le(block, 8, mem_a_val)
        _aes_single_round(block, _XELIS_V2_AES_KEY)
        hash1 = _read_uint64_le(block, 0)
        hash2 = mem_a_val ^ mem_b_val
        addr_a = _uint64(~(hash1 ^ hash2))

        for j in range(_XELIS_V2_BUFFER_SIZE):
            idx_a = addr_a % _XELIS_V2_BUFFER_SIZE
            a = mem_a[idx_a]
            idx_b = _uint64(~_rotr64(addr_a, r)) % _XELIS_V2_BUFFER_SIZE
            b = mem_b[idx_b]
            c = mem_a[r] if r < _XELIS_V2_BUFFER_SIZE else mem_b[r - _XELIS_V2_BUFFER_SIZE]
            r = (r + 1) % _XELIS_V2_MEMORY_SIZE
            op_index = _rotl64(addr_a, c & 0xFFFFFFFF) & 0xF
            v = _XELIS_OPERATIONS[op_index](a, b, c, r, addr_a, i, j)
            addr_a = _uint64(_rotl64(addr_a ^ v, 1))

            target = _XELIS_V2_BUFFER_SIZE - j - 1
            t = _uint64(mem_a[target] ^ addr_a)
            mem_a[target] = t
            mem_b[j] = _uint64(mem_b[j] ^ _rotr64(t, addr_a & 0xFFFFFFFF))

        addr_b = math.isqrt(addr_a)


def pepepow_xelisv2_hash(header: bytes) -> bytes:
    '''PEPEPOW Xelis v2 hash path.'''
    data = header if isinstance(header, (bytes, bytearray)) else bytes(header)
    if len(data) < 80:
        raise ValueError('PEPEPOW header must be at least 80 bytes')

    prepared = bytearray(_XELIS_V2_INPUT_LEN)
    length = min(len(data), _XELIS_V2_INPUT_LEN)
    prepared[:length] = data[:length]

    scratch = bytearray(_XELIS_V2_OUTPUT_SIZE)
    _xelis_stage1(prepared, scratch)
    _xelis_stage3(scratch)
    return _blake3_digest(scratch)


def pepepow_header_hash(header: bytes) -> bytes:
    '''Select PEPEPOW PoW hash path based on the version bit switch.

    PePe-core uses the Xelis v2 path when nVersion has bit 0x8000 set.
    '''
    data = bytes(header)
    if len(data) < 80:
        raise ValueError('PEPEPOW header must be at least 80 bytes')

    version = int.from_bytes(data[:4], 'little', signed=False)
    if version & 0x8000:
        return pepepow_xelisv2_hash(data)
    return pepepow_memehash(data)

