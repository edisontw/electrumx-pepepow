.. _pepepow_deployment:

==========================
PEPEPOW Deployment Runbook
==========================

This guide documents a production-oriented PEPEPOW ElectrumX deployment. It is
written for operators who want a fast path from a synchronized PEPEPOW full node
to a working ElectrumX service.

Current deployment assumptions
==============================

The examples below use the following layout:

.. list-table::
   :header-rows: 1

   * - Item
     - Value
   * - Repository
     - ``/home/ubuntu/electrumx-pepepow``
   * - Python venv
     - ``/home/ubuntu/electrumx-pepepow/.venv``
   * - ElectrumX server
     - ``/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_server``
   * - ElectrumX RPC client
     - ``/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc``
   * - ElectrumX DB
     - ``/var/lib/electrumx-pepepow``
   * - systemd service
     - ``/etc/systemd/system/electrumx.service``
   * - systemd environment file
     - ``/etc/electrumx-pepepow.conf``

PEPEPOW port map
================

Do not confuse PEPEPOW P2P and JSON-RPC ports.

.. list-table::
   :header-rows: 1

   * - Port
     - Service
     - Purpose
   * - ``8833``
     - PEPEPOW daemon P2P
     - Blockchain peer traffic
   * - ``8834``
     - PEPEPOW daemon RPC
     - JSON-RPC endpoint used by ElectrumX ``DAEMON_URL``
   * - ``50001``
     - ElectrumX TCP
     - Electrum wallet or application access
   * - ``8000``
     - ElectrumX LocalRPC
     - Local admin RPC, such as ``getinfo`` and ``stop``

``DAEMON_URL`` must use ``127.0.0.1:8834``. Port ``8833`` is the PEPEPOW P2P
port and must not be used as the ElectrumX daemon RPC endpoint.

Architecture and hash cutover
=============================

PEPEPOW block header hashing is dual-path:

* Legacy path before cutover:
  ``BLAKE512 -> SIMD512 -> ECHO512 -> CUBEHASH512 -> SHAVITE512 -> SHA256^3``
* Xelis v2 path from height ``1,930,000`` onward

The PEPEPOW hash implementation lives in:

* ``src/electrumx/lib/pepepow_hash.py``
* ``src/electrumx/lib/coins.py`` (``class Pepepow``)

SPH shared libraries required by the legacy path:

* ``src/electrumx/lib/libsph_blake.so``
* ``src/electrumx/lib/libsph_simd.so``
* ``src/electrumx/lib/libsph_echo.so``
* ``src/electrumx/lib/libsph_cubehash.so``
* ``src/electrumx/lib/libsph_shavite.so``

Install dependencies
====================

From the repository root:

.. code-block:: bash

   cd /home/ubuntu/electrumx-pepepow
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip wheel setuptools
   pip install -e ".[pepepow]"

Recommended PEPEPOW.conf
========================

ElectrumX quality is strongly coupled to PEPEPOW Core JSON-RPC stability and
capacity. Use this PEPEPOW daemon baseline as a starting point:

.. code-block:: ini

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

Notes:

* ``txindex=1`` is strongly recommended for ElectrumX reliability.
* Keep RPC local on ``127.0.0.1`` unless you have a hardened, isolated RPC
  network design.
* ``dbcache=768`` is a stable baseline; tune upward with RAM headroom.
* If ElectrumX logs repeated RPC timeouts, tune PEPEPOW Core RPC capacity first.

Create the ElectrumX DB directory
=================================

.. code-block:: bash

   sudo mkdir -p /var/lib/electrumx-pepepow
   sudo chown -R ubuntu:ubuntu /var/lib/electrumx-pepepow
   sudo chmod 750 /var/lib/electrumx-pepepow

Use a dedicated service user for hardened deployments when file ownership and
permissions are ready. For small community servers, running as ``ubuntu`` may be
acceptable during initial deployment because the repository, venv, and DB are
usually already owned by that user.

Create the ElectrumX environment file
=====================================

Create ``/etc/electrumx-pepepow.conf``.

This file is read by systemd through ``EnvironmentFile=``. Use plain
``KEY=value`` lines. Do not use ``export``.

.. code-block:: ini

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

Secure the file because it contains RPC credentials:

.. code-block:: bash

   sudo chown ubuntu:ubuntu /etc/electrumx-pepepow.conf
   sudo chmod 600 /etc/electrumx-pepepow.conf

A template is available at:

.. code-block:: text

   contrib/pepepow/electrumx-pepepow.conf.example

Create the systemd service
==========================

Create ``/etc/systemd/system/electrumx.service``:

.. code-block:: ini

   [Unit]
   Description=PEPEPOW ElectrumX Server
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=ubuntu
   Group=ubuntu
   WorkingDirectory=/home/ubuntu/electrumx-pepepow
   EnvironmentFile=/etc/electrumx-pepepow.conf
   ExecStart=/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_server
   ExecStop=/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 stop
   Restart=always
   RestartSec=10
   TimeoutStopSec=120
   LimitNOFILE=65535

   [Install]
   WantedBy=multi-user.target

A template is available at:

.. code-block:: text

   contrib/pepepow/electrumx.service.example

Validate and start the service
==============================

.. code-block:: bash

   sudo systemctl daemon-reload
   sudo systemd-analyze verify /etc/systemd/system/electrumx.service
   sudo systemctl enable electrumx
   sudo systemctl restart electrumx
   sudo systemctl status electrumx --no-pager -l

Check that the expected ports are listening:

.. code-block:: bash

   sudo ss -lntp | egrep ':8833|:8834|:8000|:50001'

Expected roles:

* ``8833``: PEPEPOW daemon P2P
* ``8834``: PEPEPOW daemon RPC
* ``50001``: ElectrumX TCP
* ``8000``: ElectrumX LocalRPC

Verification workflow
=====================

Check ElectrumX runtime state:

.. code-block:: bash

   /home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo

Healthy output should show:

* ``daemon height`` equal or close to ``db height``
* ``uptime`` increasing
* ``db_flush_count`` far below ``65535``
* ``version`` equal to the expected ElectrumX version

Monitor sync height:

.. code-block:: bash

   watch -n 10 '/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo | egrep "daemon height|db height|db_flush_count|uptime"'

Verify header hashes against PEPEPOW Core:

.. code-block:: bash

   python contrib/pepepow/verify_block_hashes.py --help

Run Electrum protocol smoke checks:

.. code-block:: bash

   python contrib/pepepow/electrum_smoke.py --help

Run PEPEPOW transaction parser smoke checks:

.. code-block:: bash

   python contrib/pepepow/tx_parser_smoke.py --help

Service exposure options
========================

Private or LAN-only deployment:

.. code-block:: ini

   SERVICES=tcp://127.0.0.1:50001,rpc://127.0.0.1:8000

Public Electrum TCP deployment:

.. code-block:: ini

   SERVICES=tcp://0.0.0.0:50001,rpc://127.0.0.1:8000

Keep ``rpc://127.0.0.1:8000`` local-only. Do not expose ElectrumX LocalRPC to the
public internet.

Capacity and memory notes
=========================

PEPEPOW Core and ElectrumX share host resources. Tune both sides together:

* PEPEPOW Core ``dbcache`` controls daemon-side index/cache pressure.
* ElectrumX ``CACHE_MB`` controls address, UTXO, and history cache behavior.

Practical starting values:

* PEPEPOW Core ``dbcache=768``
* ElectrumX ``CACHE_MB=1200``
* ElectrumX ``MAX_SESSIONS=256``
* ElectrumX ``REQUEST_TIMEOUT=60``

If sync stalls with frequent RPC timeouts, increase Core RPC capacity first
(``rpcthreads``, ``rpcworkqueue``, ``dbcache``), then revisit ElectrumX.

Troubleshooting matrix
======================

.. list-table::
   :header-rows: 1

   * - Symptom
     - Likely cause
     - Action
   * - ``systemctl start electrumx`` fails with missing environment file
     - ``EnvironmentFile`` points to the wrong path
     - Use ``EnvironmentFile=/etc/electrumx-pepepow.conf`` and run
       ``sudo systemctl daemon-reload``.
   * - ``systemd-analyze verify`` says binary does not exist
     - ``ExecStart`` points outside the venv
     - Use ``/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_server``.
   * - ElectrumX cannot connect to daemon
     - Wrong ``DAEMON_URL`` port or credentials
     - Confirm that ``DAEMON_URL`` uses ``127.0.0.1:8834`` and matches
       ``rpcuser`` / ``rpcpassword``.
   * - ElectrumX lags daemon height
     - RPC backlog or insufficient daemon cache
     - Check ``getinfo``, daemon load, and Core RPC settings.
   * - Repeated client request timeouts
     - Busy daemon under concurrent requests
     - Increase Core RPC capacity; raise ``REQUEST_TIMEOUT`` only when required.
   * - Startup failure loading PEPEPOW hashes
     - Missing SPH shared objects or missing ``blake3`` dependency
     - Verify all ``libsph_*.so`` files and install with
       ``pip install -e ".[pepepow]"``.
   * - Crash near ``db_flush_count`` 65535
     - ElectrumX history DB flush counter overflow risk
     - Stop service and perform compaction before the counter approaches the limit.

Daily maintenance
=================

See :ref:`pepepow_operations` for daily monitoring commands, log checks,
compaction notes, backup recommendations, and application usage examples.
