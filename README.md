# ElectrumX for PEPEPOW

This repository packages ElectrumX with a PEPEPOW mainnet integration for
operators who need stable indexing and Electrum protocol serving.

- Python requirement: `>= 3.10`
- ElectrumX version: `1.19.0`
- PEPEPOW coin class: `src/electrumx/lib/coins.py` (`class Pepepow`)

## PEPEPOW Integration Details

The PEPEPOW implementation uses dual PoW header hashing:

- Legacy memehash path:
  `BLAKE512 -> SIMD512 -> ECHO512 -> CUBEHASH512 -> SHAVITE512 -> SHA256^3`
- Xelis v2 path after height `1,930,000` (`XELISV2_CUTOVER_HEIGHT`)

Shipped SPH shared libraries (required by the legacy path):

- `src/electrumx/lib/libsph_blake.so`
- `src/electrumx/lib/libsph_simd.so`
- `src/electrumx/lib/libsph_echo.so`
- `src/electrumx/lib/libsph_cubehash.so`
- `src/electrumx/lib/libsph_shavite.so`

Install with PEPEPOW extras:

```bash
pip install -e ".[pepepow]"
```

## PEPEPOW Core RPC Stability (Critical)

ElectrumX stability depends heavily on PEPEPOW Core RPC capacity.
In practice, if Core RPC is overloaded or under-provisioned, ElectrumX
synchronization and serving quality degrade first.
Operationally, treat this as: around 80% of ElectrumX stability is determined
by whether Core RPC can keep up.

Use this minimum recommended `PEPEPOW.conf` baseline:

```ini
server=1

rpcuser=CHANGE_ME
rpcpassword=CHANGE_ME
rpcbind=127.0.0.1
rpcallowip=127.0.0.1

txindex=1

rpcthreads=16
rpcworkqueue=256
rpcclienttimeout=120
dbcache=768
maxconnections=32
```

Notes:

- `txindex=1` is strongly recommended and generally required for reliable
  ElectrumX operation.
- Scale `dbcache` based on available RAM. `768` is a proven baseline; raise it
  on larger hosts if Core is memory-constrained during index/serve peaks.

## ElectrumX Runtime Profile (Single-Node / LAN)

Recommended environment profile for a private or LAN deployment:

```bash
export COIN=PEPEPOW
export NET=mainnet
export DB_DIRECTORY=/var/lib/electrumx-pepepow
export DAEMON_URL=http://<rpcuser>:<rpcpassword>@127.0.0.1:8833/

export SERVICES=tcp://127.0.0.1:50001,rpc://127.0.0.1:8000
export PEER_DISCOVERY=off
export PEER_ANNOUNCE=
export REPORT_SERVICES=

export DB_ENGINE=leveldb
export CACHE_MB=1200
export REORG_LIMIT=1000
export MAX_SESSIONS=256
export REQUEST_TIMEOUT=60
export SESSION_TIMEOUT=600
export DAEMON_POLL_INTERVAL_BLOCKS=5000
export DAEMON_POLL_INTERVAL_MEMPOOL=5000
export LOG_LEVEL=info
```

Sizing guidance:

- `CACHE_MB=1200` is a stable default.
- As a starting rule, keep ElectrumX cache under about 60% of host RAM, and
  validate behavior during initial sync.

## Start and Operate

Start server:

```bash
electrumx_server
```

Check runtime health:

```bash
electrumx_rpc -p 8000 getinfo
```

Run PEPEPOW smoke and consistency checks:

```bash
python contrib/pepepow/verify_block_hashes.py --help
python contrib/pepepow/electrum_smoke.py --help
python contrib/pepepow/tx_parser_smoke.py --help
```

## Testing

Run PEPEPOW-focused tests:

```bash
python -m pytest tests/lib/test_pepepow.py tests/lib/test_tx_pepepow.py
```

## More Documentation

- Main docs index: `docs/index.rst`
- PEPEPOW runbook: `docs/pepepow_deployment.rst`
