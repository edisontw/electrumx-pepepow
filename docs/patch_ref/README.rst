===============================================
ElectrumX for PEPEPOW
===============================================

This repository packages a customized ElectrumX server that understands
`PEPEPOW <https://github.com/MattF42/PePe-core>`_.  It includes the bespoke
memehash pipeline (SIMD → ECHO → CubeHash → SHAvite → triple SHA256) used on
older blocks and the new Xelis v2 hashing path that activates at height
1,930,000.  The goal is to give exchanges, explorers, and power users a
drop-in daemon that can index the full chain while staying compatible with
standard Electrum clients.

Key Features
============

* Full Electrum protocol implementation backed by ``aiorpcX``.
* Dual hashing logic for PEPEPOW (memehash + Xelis v2).
* Optional ``PepepowBlockProcessor`` for custom block validation flows.
* Python 3.8+ support with asynchronous networking.
* Packaging of the required SPH reference implementations as shared objects so
  the server works on clean deployments.

Quick Start
===========

1. Create and activate a virtual environment.

   .. code-block:: bash

      python -m venv .venv
      source .venv/bin/activate
      pip install -U pip wheel

2. Install ElectrumX (in editable mode if you plan to hack on it).

   .. code-block:: bash

      pip install -e .

3. Point the server at a synced ``PePe`` node and launch the daemon.

   .. code-block:: bash

      electrumx_server

   Important environment variables:

   * ``DAEMON_URL`` – RPC endpoint for the PEPEPOW full node.
   * ``DB_DIRECTORY`` – Where ElectrumX stores its LevelDB history.
   * ``SSL_CERTFILE`` / ``SSL_KEYFILE`` – Enable TLS for public servers.

PEPEPOW-Specific Notes
======================

* **SPH libraries** – We ship prebuilt ``libsph_simd.so``, ``libsph_echo.so``,
  ``libsph_cubehash.so`` and ``libsph_shavite.so`` under ``electrumx/lib``.
  Packaging workflows must keep these files alongside ``coins.py`` so
  ``ctypes`` can find them at runtime.
* **Xelis v2 hash** – Implemented directly in Python with Blake3, ChaCha20, AES
  rounds and the scratchpad logic from the reference implementation.
  Installing the ``blake3`` wheel is **highly recommended** for performance.
* **Block processor** – ``PepepowBlockProcessor`` lives in
  ``electrumx/server/block_processor.py``.  Set
  ``Pepepow.BLOCK_PROCESSOR`` accordingly if you need custom block handling.

Testing
=======

Run the unit suite before deploying changes:

.. code-block:: bash

   python -m pytest tests

Contributions
=============

Pull requests are welcome!  Open an issue if you run into integration problems
with the PEPEPOW core node or need help extending the hashing pipeline.

License
=======

MIT License.  See ``LICENCE`` for the full text.
