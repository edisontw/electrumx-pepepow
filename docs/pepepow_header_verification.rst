.. _pepepow_header_verification:

============================
PEPEPOW Header Verification
============================

This guide documents the correct way to verify ElectrumX block headers against
PEPEPOW Core.

Key rule
========

Do not use Bitcoin-style double-SHA256 as the correctness check for PEPEPOW block
hashes.

PEPEPOW uses PEPEPOW-specific header hashing. The correct verification path is
ElectrumX's PEPEPOW coin logic:

.. code-block:: python

   env.coin.header_hash_for_height(header, height)

This selects the correct era-specific hashing path for the requested block
height.

Why double-SHA256 fails
=======================

A raw Electrum protocol header can be double-SHA256 hashed, but that result is
not the PEPEPOW daemon block hash. For PEPEPOW, double-SHA256 is only useful as a
negative control showing that the chain is not Bitcoin-style.

Representative verification result at height 1:

.. list-table::
   :header-rows: 1

   * - Source
     - Hash
   * - PEPEPOW daemon ``getblockhash``
     - ``00000add89b915d985d20a9b8983a3fb3a96516733f4d032f4e4c9da1e7d6223``
   * - Electrum header double-SHA256
     - ``ef246967b54a72bc08356328d4ca3dc20bdc7f15d3a720ddc77718325692abd1``
   * - Electrum header PEPEPOW hash
     - ``00000add89b915d985d20a9b8983a3fb3a96516733f4d032f4e4c9da1e7d6223``

The PEPEPOW hash matches the daemon. The double-SHA256 hash does not.

Verification tools
==================

Two repository tools are available.

1. Verify stored ElectrumX DB headers against PEPEPOW Core:

.. code-block:: bash

   cd /home/ubuntu/electrumx-pepepow
   source .venv/bin/activate
   python contrib/pepepow/verify_block_hashes.py \
     --cli /home/ubuntu/PEPEPOW-cli \
     --samples 30

2. Verify live Electrum TCP headers against PEPEPOW Core:

.. code-block:: bash

   cd /home/ubuntu/electrumx-pepepow
   source .venv/bin/activate
   python contrib/pepepow/verify_electrum_tcp_headers.py \
     --cli /home/ubuntu/PEPEPOW-cli \
     --include-fixed \
     --samples 30

The TCP verifier performs the Electrum ``server.version`` handshake before
requesting ``blockchain.block.header``. This avoids protocol errors from servers
that require ``server.version`` as the first message on a connection.

Recommended fixed heights
=========================

When checking manually or debugging, include heights around known PEPEPOW eras
and previous operational incidents:

.. code-block:: text

   1
   1000
   1930000
   1930001
   4380117
   4380118
   current_tip - 100
   current_tip - 20

Expected result
===============

A healthy PEPEPOW ElectrumX server should show:

* PEPEPOW daemon height equals or closely tracks ElectrumX DB height.
* Random PEPEPOW-specific header hash samples match daemon ``getblockhash``.
* Fixed-height PEPEPOW-specific header hash samples match daemon ``getblockhash``.
* No traceback, exception, or header mismatch appears in recent ElectrumX logs.

Example successful result
=========================

A completed verification run on ``pepepow-nm3-ub1`` showed:

.. list-table::
   :header-rows: 1

   * - Item
     - Result
   * - Daemon tip
     - ``4641333``
   * - ElectrumX daemon height
     - ``4641333``
   * - ElectrumX DB height
     - ``4641333``
   * - ``db_flush_count``
     - ``590``
   * - Random TCP header samples
     - ``30 / 30 PASS``
   * - Fixed-height TCP header samples
     - ``PASS``

Conclusion: ElectrumX DB/header index matched the PEPEPOW daemon when headers
were hashed with PEPEPOW's actual block hash algorithm.

Failure handling
================

If a PEPEPOW-specific header hash mismatch occurs:

1. Do not rebuild the DB immediately.
2. Capture the failed height, daemon hash, ElectrumX hash, and raw header hex.
3. Check recent logs:

   .. code-block:: bash

      sudo journalctl -u electrumx -n 300 --no-pager -l | \
        egrep -i 'traceback|error|exception|hash|header|block|db|flush|daemon|rpc|timeout'

4. Inspect the daemon block:

   .. code-block:: bash

      /home/ubuntu/PEPEPOW-cli getblockhash <height>
      /home/ubuntu/PEPEPOW-cli getblock "$(/home/ubuntu/PEPEPOW-cli getblockhash <height>)" 1 | head -120

5. Only consider code or DB repair after confirming a reproducible mismatch.
