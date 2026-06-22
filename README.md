# ElectrumX for PEPEPOW

This repository packages ElectrumX with a PEPEPOW mainnet integration for
operators who need stable indexing and Electrum protocol serving.

- Python requirement: `>= 3.10`
- ElectrumX version: `1.19.0`
- PEPEPOW coin class: `src/electrumx/lib/coins.py` (`class Pepepow`)
- Main deployment guide: `docs/pepepow_deployment.rst`
- Daily operations guide: `docs/pepepow_operations.rst`

## PEPEPOW Integration Details

The PEPEPOW implementation uses dual PoW header hashing:

- Legacy memehash path:
  `BLAKE512 -> SIMD512 -> ECHO512 -> CUBEHASH512 -> SHAVITE512 -> SHA256^3`
- Xelis v2 path after height `1,930,000` (`XELISV2_CUTOVER_HEIGHT`)

Shipped SPH shared libraries required by the legacy path:

- `src/electrumx/lib/libsph_blake.so`
- `src/electrumx/lib/libsph_simd.so`
- `src/electrumx/lib/libsph_echo.so`
- `src/electrumx/lib/libsph_cubehash.so`
- `src/electrumx/lib/libsph_shavite.so`

Install with PEPEPOW extras:

```bash
pip install -e ".[pepepow]"
```

## Port Map

Use this map to avoid confusing PEPEPOW daemon P2P and daemon RPC ports:

| Port | Service | Purpose |
|---:|---|---|
| `8833` | PEPEPOW daemon P2P | Blockchain network peer traffic |
| `8834` | PEPEPOW daemon RPC | JSON-RPC endpoint used by ElectrumX |
| `50001` | ElectrumX TCP | Electrum wallet / application access |
| `8000` | ElectrumX LocalRPC | Local admin RPC, such as `getinfo` and `stop` |

`DAEMON_URL` must point to `127.0.0.1:8834`, not `8833`.

## PEPEPOW Core RPC Stability

ElectrumX stability depends heavily on PEPEPOW Core RPC capacity. If Core RPC is
overloaded or under-provisioned, ElectrumX synchronization and serving quality
usually degrade first.

Use this minimum recommended `PEPEPOW.conf` baseline:

```ini
server=1

rpcuser=CHANGE_ME
rpcpassword=CHANGE_ME
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
rpcport=8834
port=8833

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
- Keep daemon RPC local unless there is a hardened, isolated RPC network design.
- Scale `dbcache` based on available RAM. `768` is a proven baseline; raise it on
  larger hosts if Core is memory-constrained during index/serve peaks.

## Recommended ElectrumX Environment File

Production deployments should use a PEPEPOW-specific environment file:

```text
/etc/electrumx-pepepow.conf
```

This file is read by systemd through `EnvironmentFile=`. Use plain `KEY=value`
syntax. Do **not** use `export` in the systemd environment file.

```ini
COIN=PEPEPOW
NET=mainnet
DB_DIRECTORY=/var/lib/electrumx-pepepow
DAEMON_URL=http://<rpcuser>:<rpcpassword>@127.0.0.1:8834/

SERVICES=tcp://0.0.0.0:50001,rpc://127.0.0.1:8000
PEER_DISCOVERY=off
PEER_ANNOUNCE=
REPORT_SERVICES=

DB_ENGINE=leveldb
CACHE_MB=1200
REORG_LIMIT=1000
MAX_SESSIONS=256
REQUEST_TIMEOUT=60
SESSION_TIMEOUT=600
LOG_LEVEL=info
PRECACHE_HEADER_MERKLE=false
```

A ready-to-copy template is provided at:

```text
contrib/pepepow/electrumx-pepepow.conf.example
```

## Recommended systemd Service

A ready-to-copy service template is provided at:

```text
contrib/pepepow/electrumx.service.example
```

The recommended service layout uses:

- environment file: `/etc/electrumx-pepepow.conf`
- binary: `/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_server`
- admin RPC client: `/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000`
- DB path: `/var/lib/electrumx-pepepow`

## Start, Stop, and Health Check

Start or restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart electrumx
sudo systemctl status electrumx --no-pager -l
```

Check runtime health:

```bash
/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo
```

Monitor sync height:

```bash
watch -n 10 '/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo | egrep "daemon height|db height|db_flush_count|uptime"'
```

A healthy server should normally show:

- `daemon height` equal or close to `db height`
- `uptime` increasing
- `db_flush_count` far below `65535`

## Smoke and Consistency Checks

Run PEPEPOW smoke and consistency checks:

```bash
python contrib/pepepow/verify_block_hashes.py --help
python contrib/pepepow/electrum_smoke.py --help
python contrib/pepepow/tx_parser_smoke.py --help
```

Run PEPEPOW-focused tests:

```bash
python -m pytest tests/lib/test_pepepow.py tests/lib/test_tx_pepepow.py
```

## More Documentation

- Main docs index: `docs/index.rst`
- Deployment runbook: `docs/pepepow_deployment.rst`
- Operations and maintenance: `docs/pepepow_operations.rst`
