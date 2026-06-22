.. _pepepow_operations:

====================================
PEPEPOW ElectrumX Operations Guide
====================================

This guide is for day-to-day operation of a PEPEPOW ElectrumX server after the
initial deployment is complete. It focuses on fast checks, safe maintenance,
application usage, and common failure recovery.

Quick reference
===============

.. list-table::
   :header-rows: 1

   * - Purpose
     - Command or file
   * - Service name
     - ``electrumx``
   * - Environment file
     - ``/etc/electrumx-pepepow.conf``
   * - Service file
     - ``/etc/systemd/system/electrumx.service``
   * - Repository
     - ``/home/ubuntu/electrumx-pepepow``
   * - DB directory
     - ``/var/lib/electrumx-pepepow``
   * - ElectrumX RPC
     - ``/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000``
   * - PEPEPOW P2P port
     - ``8833``
   * - PEPEPOW RPC port
     - ``8834``
   * - Electrum TCP port
     - ``50001``
   * - ElectrumX LocalRPC port
     - ``8000``

The most important rule: ``DAEMON_URL`` uses the PEPEPOW daemon RPC port
``8834``. Port ``8833`` is for PEPEPOW P2P traffic.

Daily health checks
===================

Check systemd service status:

.. code-block:: bash

   sudo systemctl status electrumx --no-pager -l

Check ElectrumX runtime state:

.. code-block:: bash

   /home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo

Watch sync state live:

.. code-block:: bash

   watch -n 10 '/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo | egrep "daemon height|db height|db_flush_count|uptime"'

Healthy signs:

* ``daemon height`` equals or closely tracks ``db height``.
* ``uptime`` keeps increasing.
* ``sessions`` are within expected limits.
* ``db_flush_count`` is far below ``65535``.
* No repeated traceback or RPC timeout messages appear in the logs.

Port checks
===========

.. code-block:: bash

   sudo ss -lntp | egrep ':8833|:8834|:8000|:50001'

Expected roles:

.. list-table::
   :header-rows: 1

   * - Port
     - Expected binding
     - Owner
     - Meaning
   * - ``8833``
     - ``0.0.0.0`` and/or ``[::]``
     - ``PEPEPOWd``
     - PEPEPOW blockchain P2P
   * - ``8834``
     - ``127.0.0.1``
     - ``PEPEPOWd``
     - PEPEPOW JSON-RPC
   * - ``50001``
     - ``0.0.0.0`` or ``127.0.0.1``
     - ``electrumx_server``
     - Electrum TCP service
   * - ``8000``
     - ``127.0.0.1``
     - ``electrumx_server``
     - ElectrumX LocalRPC

Use ``0.0.0.0:50001`` only when public Electrum wallet access is intended. Keep
``8000`` local-only.

Service operations
==================

Restart ElectrumX:

.. code-block:: bash

   sudo systemctl restart electrumx
   sudo systemctl status electrumx --no-pager -l

Stop ElectrumX gracefully:

.. code-block:: bash

   /home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 stop

Start ElectrumX:

.. code-block:: bash

   sudo systemctl start electrumx

Reload systemd after service edits:

.. code-block:: bash

   sudo systemctl daemon-reload
   sudo systemd-analyze verify /etc/systemd/system/electrumx.service

Enable at boot:

.. code-block:: bash

   sudo systemctl enable electrumx

Disable at boot:

.. code-block:: bash

   sudo systemctl disable electrumx

Log checks
==========

Recent logs:

.. code-block:: bash

   sudo journalctl -u electrumx -n 200 --no-pager -l

Follow logs live:

.. code-block:: bash

   sudo journalctl -u electrumx -f

Filter important errors:

.. code-block:: bash

   sudo journalctl -u electrumx -n 500 --no-pager -l | \
     egrep -i 'traceback|error|exception|failed|assert|db|flush|permission|denied|daemon|rpc|timeout'

Configuration checks
====================

Show the active systemd service:

.. code-block:: bash

   sudo systemctl cat electrumx

Confirm the active environment file:

.. code-block:: bash

   sudo systemctl cat electrumx | grep EnvironmentFile

Expected output:

.. code-block:: ini

   EnvironmentFile=/etc/electrumx-pepepow.conf

Print the environment file without exposing the RPC password:

.. code-block:: bash

   sudo sed -E 's#(DAEMON_URL=http://[^:]+:)[^@]+@#\1[REDACTED]@#' /etc/electrumx-pepepow.conf

Confirm the daemon RPC settings:

.. code-block:: bash

   grep -R -E 'rpcuser|rpcpassword|rpcport|port=' ~/.pepe* -n 2>/dev/null || true

Expected daemon port meaning:

.. code-block:: ini

   rpcport=8834
   port=8833

Application usage
=================

Wallets or applications that need Electrum protocol access should connect to the
ElectrumX TCP service.

Local application on the same host:

.. code-block:: text

   127.0.0.1:50001

External application or wallet when public binding is enabled:

.. code-block:: text

   <server-public-ip-or-domain>:50001

Do not expose or publish the ElectrumX LocalRPC endpoint:

.. code-block:: text

   127.0.0.1:8000

LocalRPC is for operator commands such as ``getinfo`` and ``stop``.

Recommended monitoring script
=============================

Create a small helper command:

.. code-block:: bash

   sudo tee /usr/local/bin/pepew-electrumx-watch >/dev/null <<'EOF'
   #!/usr/bin/env bash
   watch -n 10 '/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo | egrep "daemon height|db height|db_flush_count|uptime|version"'
   EOF
   sudo chmod +x /usr/local/bin/pepew-electrumx-watch

Use it:

.. code-block:: bash

   pepew-electrumx-watch

Optional alert check
====================

This command exits non-zero if ElectrumX is far behind the daemon or if the flush
count approaches the known danger zone.

.. code-block:: bash

   python3 - <<'PY'
   import json
   import subprocess
   import sys

   cmd = ['/home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc', '-p', '8000', 'getinfo']
   info = json.loads(subprocess.check_output(cmd, text=True))
   daemon_h = int(info.get('daemon height', 0))
   db_h = int(info.get('db height', 0))
   flush = int(info.get('db_flush_count', 0))
   lag = daemon_h - db_h

   print(f'daemon_height={daemon_h} db_height={db_h} lag={lag} db_flush_count={flush}')

   if lag > 100:
       print('ALERT: ElectrumX DB height is lagging daemon height by more than 100 blocks')
       sys.exit(2)
   if flush >= 60000:
       print('ALERT: db_flush_count is approaching 65535; schedule compaction')
       sys.exit(3)
   PY

Database maintenance and compaction
===================================

ElectrumX stores history and index data in its DB directory. For this deployment:

.. code-block:: text

   /var/lib/electrumx-pepepow

A previous operational failure was caused by the history DB ``flush_count``
approaching the 16-bit limit ``65535``. Monitor ``db_flush_count`` regularly.
When it approaches ``60000``, schedule a maintenance window and compact before it
reaches the limit.

Check the counter:

.. code-block:: bash

   /home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo | grep db_flush_count

Before any DB maintenance:

* Confirm the service is stopped.
* Confirm there is enough free disk space.
* Take a snapshot or backup if the host platform supports it.
* Do not delete the DB unless corruption is confirmed and a rebuild is accepted.

Disk and file checks:

.. code-block:: bash

   df -h
   df -i
   sudo du -sh /var/lib/electrumx-pepepow
   ls -la /var/lib/electrumx-pepepow | head

Backup recommendations
======================

At minimum, back up configuration files before edits:

.. code-block:: bash

   ts=$(date +%Y%m%d-%H%M%S)
   sudo cp -a /etc/electrumx-pepepow.conf /etc/electrumx-pepepow.conf.bak.$ts
   sudo cp -a /etc/systemd/system/electrumx.service /etc/systemd/system/electrumx.service.bak.$ts

Do not commit real RPC credentials to GitHub. Repository examples must use
placeholders such as ``<rpcuser>`` and ``<rpcpassword>``.

Safe update workflow
====================

Use this workflow when updating code or documentation:

.. code-block:: bash

   cd /home/ubuntu/electrumx-pepepow
   git status --short
   git pull --ff-only
   source .venv/bin/activate
   pip install -e ".[pepepow]"
   python -m pytest tests/lib/test_pepepow.py tests/lib/test_tx_pepepow.py
   sudo systemctl restart electrumx
   /home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo

Troubleshooting checklist
=========================

Service will not start
----------------------

.. code-block:: bash

   sudo systemctl status electrumx --no-pager -l
   sudo journalctl -u electrumx -n 200 --no-pager -l
   sudo systemd-analyze verify /etc/systemd/system/electrumx.service

Common fixes:

* Missing environment file: set ``EnvironmentFile=/etc/electrumx-pepepow.conf``.
* Wrong binary path: use the venv binary under ``.venv/bin``.
* Permission issue: check ownership of repository, venv, and DB directory.
* Wrong RPC port: use ``127.0.0.1:8834`` in ``DAEMON_URL``.

Daemon height moves but DB height does not
------------------------------------------

.. code-block:: bash

   /home/ubuntu/electrumx-pepepow/.venv/bin/electrumx_rpc -p 8000 getinfo
   sudo journalctl -u electrumx -n 500 --no-pager -l | \
     egrep -i 'traceback|error|exception|block|hash|header|daemon|rpc|timeout'

Check the next block if a specific height is stuck:

.. code-block:: bash

   pepepow-cli getblockhash <height>
   pepepow-cli getblock "$(pepepow-cli getblockhash <height>)" 1 | head -120

Do not rebuild the DB until logs show clear corruption or an unrecoverable index
state.

RPC credentials changed
-----------------------

Update ``DAEMON_URL`` in ``/etc/electrumx-pepepow.conf`` and restart:

.. code-block:: bash

   sudo sed -E 's#(DAEMON_URL=http://[^:]+:)[^@]+@#\1[REDACTED]@#' /etc/electrumx-pepepow.conf
   sudo systemctl restart electrumx

Public wallet cannot connect
----------------------------

Check whether the Electrum TCP service is public or local-only:

.. code-block:: bash

   sudo ss -lntp | grep ':50001'

For public access, ``SERVICES`` should include:

.. code-block:: ini

   SERVICES=tcp://0.0.0.0:50001,rpc://127.0.0.1:8000

Also check firewall, cloud security groups, DNS, and client-side network access.

Security notes
==============

* Keep ``/etc/electrumx-pepepow.conf`` at ``chmod 600``.
* Keep PEPEPOW daemon RPC bound to ``127.0.0.1``.
* Keep ElectrumX LocalRPC bound to ``127.0.0.1``.
* Expose ``50001`` publicly only if public wallet access is intended.
* Do not publish real RPC usernames or passwords in docs, issues, commits, or logs.
* Prefer a dedicated service user for hardened deployments once file ownership is
  cleaned up.
