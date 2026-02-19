.. _pepepow_deployment:

==========================
PEPEPOW Deployment Runbook
==========================

This guide documents a production-oriented, single-node / LAN deployment model
for running ElectrumX on PEPEPOW mainnet.

It is aligned with the current codebase:

* ``COIN=PEPEPOW``
* ``RPC_PORT=8833``
* ``REORG_LIMIT=1000``
* ``XELISV2_CUTOVER_HEIGHT=1,930,000``


Architecture and Hash Cutover
=============================

PEPEPOW block header hashing is dual-path:

* Legacy path (before cutover): ``BLAKE512 -> SIMD512 -> ECHO512 -> CUBEHASH512 -> SHAVITE512 -> SHA256^3``
* Xelis v2 path (from cutover onward): selected at height ``1,930,000``

The PEPEPOW hash implementation lives in:

* ``src/electrumx/lib/pepepow_hash.py``
* ``src/electrumx/lib/coins.py`` (``class Pepepow``)

SPH shared libraries required by the legacy path:

* ``src/electrumx/lib/libsph_blake.so``
* ``src/electrumx/lib/libsph_simd.so``
* ``src/electrumx/lib/libsph_echo.so``
* ``src/electrumx/lib/libsph_cubehash.so``
* ``src/electrumx/lib/libsph_shavite.so``


Recommended PEPEPOW.conf
========================

ElectrumX quality is strongly coupled to PEPEPOW Core JSON-RPC stability and
capacity. Use this baseline:
As an operational rule, roughly 80% of ElectrumX stability depends on Core RPC
keeping up.

.. code-block:: ini

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

Notes:

* ``txindex=1`` is strongly recommended for ElectrumX reliability.
* ``dbcache=768`` is a stable baseline; tune upward with RAM headroom.
* Keep RPC local (``127.0.0.1``) unless you have a hardened, isolated RPC
  network design.


Recommended ElectrumX Environment Profile
=========================================

For a single-node / LAN profile:

.. code-block:: bash

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

Rationale by key setting:

* ``SERVICES`` binds both Electrum TCP and LocalRPC to localhost for private
  operations.
* ``PEER_DISCOVERY=off`` and empty ``REPORT_SERVICES`` disable public peer
  advertisement in private mode.
* ``CACHE_MB=1200`` is a balanced default for sync + serving.
* ``MAX_SESSIONS=256`` avoids unnecessary file/socket pressure for LAN-only
  access.
* ``REQUEST_TIMEOUT=60`` tolerates heavy daemon calls while still failing fast
  under saturation.
* Poll intervals at ``5000`` ms avoid over-polling daemon RPC.


Capacity and Memory Notes
=========================

PEPEPOW Core and ElectrumX share host resources. Tune both sides together:

* PEPEPOW Core ``dbcache`` controls daemon-side index/cache pressure.
* ElectrumX ``CACHE_MB`` controls address/UTXO/history cache behavior.

Practical sizing:

* Start with ``dbcache=768`` and ``CACHE_MB=1200``.
* Keep ElectrumX cache below roughly 60% of system RAM.
* If sync stalls with frequent RPC timeouts, increase Core RPC capacity first
  (``rpcthreads``, ``rpcworkqueue``, ``dbcache``), then revisit ElectrumX.


Verification Workflow
=====================

1. Start ElectrumX:

   .. code-block:: bash

      electrumx_server

2. Check server state:

   .. code-block:: bash

      electrumx_rpc -p 8000 getinfo

3. Verify header hashes against PEPEPOW core:

   .. code-block:: bash

      python contrib/pepepow/verify_block_hashes.py --help

4. Run Electrum protocol smoke checks:

   .. code-block:: bash

      python contrib/pepepow/electrum_smoke.py --help

5. Run PEPEPOW transaction parser smoke checks:

   .. code-block:: bash

      python contrib/pepepow/tx_parser_smoke.py --help


Troubleshooting Matrix
======================

.. list-table::
   :header-rows: 1

   * - Symptom
     - Likely Cause
     - Action
   * - Slow initial sync or repeated timeout logs
     - Core RPC saturation
     - Increase ``rpcthreads`` and ``rpcworkqueue``; verify ``txindex=1``; raise
       ``dbcache`` with RAM headroom.
   * - ElectrumX lags daemon height
     - RPC backlog or insufficient daemon cache
     - Check ``electrumx_rpc getinfo`` and daemon load; tune Core first, then
       revisit ``CACHE_MB``.
   * - Frequent client request timeouts
     - Busy daemon under concurrent requests
     - Keep LAN profile defaults; increase Core RPC capacity; raise
       ``REQUEST_TIMEOUT`` only when required.
   * - Startup failure loading PEPEPOW hashes
     - Missing SPH shared objects or missing ``blake3`` dependency
     - Verify all ``libsph_*.so`` files and install
       ``pip install -e ".[pepepow]"``.
   * - Unexpected reorg handling limits
     - Inconsistent ``REORG_LIMIT`` override
     - Keep ``REORG_LIMIT=1000`` unless you have chain-specific reasons to
       change it.
